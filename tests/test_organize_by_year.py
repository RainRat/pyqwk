import logging
import os
import pytest
from pyqwk.core import (
    organize_by_year,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    ConferenceMap,
    _get_organization_subpath,
)
from pyqwk.cli import main


@pytest.fixture
def mock_logger():
    return logging.getLogger("test_organize_by_year")


def create_test_settings(**kwargs):
    defaults = {
        "verbose": False,
        "private": False,
        "no_header": False,
        "truncate_signatures": False,
        "cut_quoting": False,
        "individual_files": False,
        "threaded": False,
        "merge": False,
        "binaries_removal": False,
        "redact_pii": False,
        "strip_ansi": False,
        "quiet": True,
        "headers_only": False,
        "unique": False,
        "organize": False,
        "organize_by_date": False,
        "organize_by_year": True,
        "organize_by_bbs": False,
        "organize_by_author": False,
        "organize_by_to": False,
        "organize_by_subject": False,
        "include_toc": False,
        "extract_attachments": False,
        "embed_attachments": False,
        "organize_attachments": False,
        "format": "text",
        "separator": "auto",
        "output_mode": "stdout",
        "output_path": None,
        "encoding": "cp437",
        "dry_run": False,
    }
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def make_msg(date_str="03-15-21", time_str="10:00"):
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate=date_str,
        msgtime=time_str,
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )
    return ParsedMessage(text="Sample", msgnum=1, refnum=None, confnum=1, header=header)


def test_organize_by_year_moves_file(tmp_path, monkeypatch, mock_logger):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "test.json"
    file_path.write_text(
        '{"type": "qwk_archive", "messages": [{"header": {"msgdate": "05-20-22", "msgtime": "12:00", "msgnum": 1, "confnum": 1}, "text": "Hello"}]}',
        encoding="utf-8",
    )

    settings = create_test_settings()
    organize_by_year([str(file_path)], settings, mock_logger)

    target_path = tmp_path / "2022" / "test.json"
    assert target_path.exists()
    assert not file_path.exists()


def test_organize_by_year_dry_run(tmp_path, monkeypatch, mock_logger):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "test.json"
    file_path.write_text(
        '{"type": "qwk_archive", "messages": [{"header": {"msgdate": "05-20-22", "msgtime": "12:00", "msgnum": 1, "confnum": 1}, "text": "Hello"}]}',
        encoding="utf-8",
    )

    settings = create_test_settings(dry_run=True)
    organize_by_year([str(file_path)], settings, mock_logger)

    assert file_path.exists()
    target_path = tmp_path / "2022" / "test.json"
    assert not target_path.exists()


def test_organize_by_year_unknown_date_fallback(tmp_path, monkeypatch, mock_logger):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "test.json"
    file_path.write_text(
        '{"type": "qwk_archive", "messages": [{"header": {"msgdate": "", "msgtime": "", "msgnum": 1, "confnum": 1}, "text": "Hello"}]}',
        encoding="utf-8",
    )

    settings = create_test_settings()
    organize_by_year([str(file_path)], settings, mock_logger)

    target_path = tmp_path / "Unknown_Date" / "test.json"
    assert target_path.exists()


def test_organize_by_year_skips_non_file_and_unsupported(tmp_path, mock_logger):
    dir_path = tmp_path / "sub_dir"
    dir_path.mkdir()
    unsupported_path = tmp_path / "test.xyz"
    unsupported_path.write_text("dummy")

    settings = create_test_settings()
    organize_by_year([str(dir_path), str(unsupported_path)], settings, mock_logger)

    assert unsupported_path.exists()


def test_organize_by_year_error_handling(tmp_path, monkeypatch, mock_logger, mocker):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "corrupt.json"
    file_path.write_text("invalid json content")

    mocker.patch("pyqwk.core.load_data", side_effect=ValueError("Corrupt file"))

    settings = create_test_settings()
    organize_by_year([str(file_path)], settings, mock_logger)

    assert file_path.exists()


def test_cli_organize_by_year_dispatch(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "test.json"
    file_path.write_text(
        '{"type": "qwk_archive", "messages": [{"header": {"msgdate": "05-20-22", "msgtime": "12:00", "msgnum": 1, "confnum": 1}, "text": "Hello"}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr("sys.argv", ["qwk", str(file_path), "--organize-by-year"])

    mock_org = mocker.patch("pyqwk.cli.organize_by_year")
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    mock_org.assert_called_once()


def test_organize_by_year_bytearray_under_block_size(tmp_path, monkeypatch, mock_logger, mocker):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "test.qwk"
    file_path.write_bytes(b"short")

    mocker.patch("pyqwk.core.load_data", return_value=(bytearray(b"short"), ConferenceMap()))

    settings = create_test_settings()
    organize_by_year([str(file_path)], settings, mock_logger)

    target_path = tmp_path / "Unknown_Date" / "test.qwk"
    assert target_path.exists()


def test_organize_by_year_bytearray_with_messages(tmp_path, monkeypatch, mock_logger, mocker):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "test.qwk"
    file_path.write_bytes(b"x" * 512)

    fake_msg = make_msg("03-15-21", "10:00")
    mocker.patch("pyqwk.core.load_data", return_value=(bytearray(b"x" * 512), ConferenceMap()))
    mocker.patch("pyqwk.core.parse_messages", return_value=[fake_msg])

    settings = create_test_settings()
    organize_by_year([str(file_path)], settings, mock_logger)

    target_path = tmp_path / "2021" / "test.qwk"
    assert target_path.exists()


def test_subpath_organize_by_year():
    msg = make_msg("05-20-22", "12:00")
    settings = create_test_settings(organize_by_year=True)
    subpath = _get_organization_subpath(msg, settings)
    assert subpath == "2022"
