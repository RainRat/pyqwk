import os
import logging
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    ProcessingSettings,
    MessageHeader,
    ParsedMessage,
    organize_by_year,
    process_merged_files,
)


def _make_msg(
    msgnum=1,
    confnum=1,
    msgdate="01-01-23",
    msgtime="12:00",
    msgfrom="Author",
    msgto="Recipient",
    msgsubject="Subject",
    text="Body",
):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=confnum,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text=text, msgnum=msgnum, refnum=None, confnum=confnum, header=header
    )


def test_organize_by_year_standalone(tmp_path):
    qwk_file = tmp_path / "test.qwk"
    qwk_file.write_bytes(b"dummy")

    logger = logging.getLogger("test")
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        organize_by_year=True,
    )

    msg = _make_msg(msgdate="05-20-24")

    with (
        patch("pyqwk.core.load_data", return_value=([msg], {})),
        patch("shutil.move") as mock_move,
        patch("os.makedirs") as mock_makedirs,
        patch("os.path.exists", return_value=False),
    ):
        organize_by_year([str(qwk_file)], settings, logger)

        mock_makedirs.assert_called_once_with("2024")
        mock_move.assert_called_once_with(
            str(qwk_file), os.path.join("2024", "test.qwk")
        )


def test_organize_by_year_standalone_unknown(tmp_path):
    qwk_file = tmp_path / "nodate.qwk"
    qwk_file.write_bytes(b"dummy")

    logger = logging.getLogger("test")
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        organize_by_year=True,
    )

    with (
        patch("pyqwk.core.load_data", return_value=([], {})),
        patch("shutil.move") as mock_move,
        patch("os.makedirs") as mock_makedirs,
        patch("os.path.exists", return_value=False),
    ):
        organize_by_year([str(qwk_file)], settings, logger)

        mock_makedirs.assert_called_once_with("Unknown_Year")
        mock_move.assert_called_once_with(
            str(qwk_file), os.path.join("Unknown_Year", "nodate.qwk")
        )


def test_organize_by_year_dry_run(tmp_path):
    qwk_file = tmp_path / "dryrun.qwk"
    qwk_file.write_bytes(b"dummy")

    logger = logging.getLogger("test")
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        organize_by_year=True,
        dry_run=True,
    )

    msg = _make_msg(msgdate="05-20-24")

    with (
        patch("pyqwk.core.load_data", return_value=([msg], {})),
        patch("shutil.move") as mock_move,
        patch("os.makedirs") as mock_makedirs,
    ):
        organize_by_year([str(qwk_file)], settings, logger)

        mock_makedirs.assert_not_called()
        mock_move.assert_not_called()


def test_organize_by_year_exception(tmp_path, caplog):
    qwk_file = tmp_path / "error.qwk"
    qwk_file.write_bytes(b"dummy")

    logger = logging.getLogger("test")
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        organize_by_year=True,
    )

    with patch("pyqwk.core.load_data", side_effect=ValueError("Boom")):
        with caplog.at_level(logging.ERROR):
            organize_by_year([str(qwk_file)], settings, logger)

        assert "Error organizing" in caplog.text
        assert "Boom" in caplog.text


def test_organize_by_year_export_individual_files(tmp_path):
    output_dir = tmp_path / "export_year"
    output_dir.mkdir()

    msg = _make_msg(msgdate="05-20-24", msgsubject="YearTest", confnum=1)
    msg.confname = "General"

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_dir),
        encoding="cp437",
        organize_by_year=True,
    )

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert (output_dir / "2024" / "001-00001-yeartest.txt").exists()
