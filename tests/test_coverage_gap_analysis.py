import json
import logging
import pytest
import subprocess
from unittest.mock import MagicMock, patch, mock_open
from pyqwk.core import (
    MessageHeader,
    load_data,
    ProcessingSettings,
    process_merged_files,
    show_info,
    show_stats
)
from dataclasses import replace

@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.tests.coverage_gap")

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )

def test_message_header_from_dict_invalid_int():
    # Reconstruct MessageHeader with invalid numeric strings to test error handling in to_int helper
    data = {
        "msgnum": "not-an-int",
        "confnum": 1,
        "status": " "
    }
    header = MessageHeader.from_dict(data)
    assert header.msgnum is None
    assert header.confnum == 1

def test_load_data_invalid_json_format(tmp_path, logger):
    # Ensure load_data raises ValueError when JSON archive is not a list
    json_file = tmp_path / "invalid.json"
    json_file.write_text(json.dumps({"not": "a list"}))

    with pytest.raises(ValueError, match="JSON archive must be a list of messages."):
        load_data(str(json_file), logger)

def test_load_data_json_with_bbs_name(tmp_path, logger):
    # Ensure BBS name is correctly loaded from a JSON message archive
    msg_dict = {
        "header": {
            "status": " ", "msgnum": 1, "msgdate": "01-01-23", "msgtime": "12:00",
            "msgto": "All", "msgfrom": "User1", "msgsubject": "Subj1",
            "msgpassword": "", "refnum": None, "numblocks": 2, "msgflag": " ",
            "confnum": 1, "lognum": 1, "nettag": ""
        },
        "text": "Body",
        "conference": "General",
        "bbs_name": "Test BBS"
    }
    json_file = tmp_path / "archive.json"
    json_file.write_text(json.dumps([msg_dict]))
    _, board_dict = load_data(str(json_file), logger)
    assert board_dict.bbs_info.name == "Test BBS"

def test_load_data_unzip_fallback_reply_dat(logger):
    # Verify fallback to system 'unzip' when built-in zipfile fails, specifically for REPLY.DAT
    with patch("zipfile.is_zipfile", return_value=True):
        with patch("zipfile.ZipFile", side_effect=RuntimeError("Test error")):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                with patch("os.listdir", return_value=["REPLY.DAT"]):
                    with patch("os.path.exists", return_value=True):
                        with patch("builtins.open", mock_open(read_data=b"dummy")):
                            load_data("dummy.zip", logger)

def test_load_data_unzip_fallback_failure(logger):
    # Verify load_data raises RuntimeError when system 'unzip' returns a non-zero exit code
    with patch("zipfile.is_zipfile", return_value=True):
        with patch("zipfile.ZipFile", side_effect=RuntimeError("Test error")):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=2, stderr="Unzip error")
                with pytest.raises(RuntimeError, match="unzip failed with return code 2"):
                    load_data("dummy.zip", logger)

def test_load_data_unzip_fallback_called_process_error(logger):
    # Verify load_data handles CalledProcessError during 'unzip' fallback
    with patch("zipfile.is_zipfile", return_value=True):
        with patch("zipfile.ZipFile", side_effect=RuntimeError("Test error")):
            with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "unzip", stderr="Failure")):
                with pytest.raises(RuntimeError, match="Failed to extract older ZIP archive using 'unzip'"):
                    load_data("dummy.zip", logger)

def test_show_stats_progress_bar_raw_data(tmp_path, default_settings, logger):
    # Verify progress bar logic in show_stats when processing raw QWK data (bytearray)
    dummy_qwk = tmp_path / "test.qwk"
    dummy_qwk.write_bytes(b"Produced " + b" " * 119)

    settings = replace(default_settings, quiet=False)
    with patch("pyqwk.core.load_data", return_value=(bytearray(b"Produced " + b" " * 119), {1: "General"})):
        show_stats([str(dummy_qwk)], settings, logger)

def test_json_archive_isinstance_list_branches(tmp_path, default_settings, logger, capsys):
    # Verify processing branches (process_merged_files, show_info, show_stats) when archive is already a list (JSON)
    msg_dict = {
        "header": {
            "status": " ", "msgnum": 1, "msgdate": "01-01-23", "msgtime": "12:00",
            "msgto": "All", "msgfrom": "User1", "msgsubject": "Subj1",
            "msgpassword": "", "refnum": None, "numblocks": 2, "msgflag": " ",
            "confnum": 1, "lognum": 1, "nettag": ""
        },
        "text": "Body",
        "conference": "General"
    }
    json_file = tmp_path / "archive.json"
    json_file.write_text(json.dumps([msg_dict]))

    settings = replace(default_settings, format='json', quiet=False)
    with patch("pyqwk.core._write_json"):
        process_merged_files([str(json_file)], settings, logger)

    info_settings = replace(settings, format='text')
    show_info([str(json_file)], info_settings, logger)
    captured = capsys.readouterr()
    assert "Total Messages: 1" in captured.out

    show_stats([str(json_file)], info_settings, logger)
    captured = capsys.readouterr()
    assert "Messages: 1 matching / 1 total" in captured.out
