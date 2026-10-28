import os
import logging
import pytest
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    organize_by_year,
    ProcessingSettings,
    ConferenceMap,
    ParsedMessage,
    MessageHeader,
    _get_organization_subpath,
)


@pytest.fixture
def mock_settings():
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
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        organize_by_year=True,
    )


@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.test_organize_by_year")


def test_organize_by_year_success(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    msg = MagicMock(spec=ParsedMessage)
    msg.header = MagicMock(spec=MessageHeader)
    msg.header.msgdate = "10-15-95"
    msg.header.msgtime = "14:30"

    board_dict = ConferenceMap()

    with (
        patch("pyqwk.core.load_data", return_value=([msg], board_dict)),
        patch("shutil.move") as mock_move,
        patch("os.makedirs") as mock_makedirs,
    ):
        organize_by_year([str(qwk_file)], mock_settings, logger)

        mock_makedirs.assert_called_once_with("1995")
        mock_move.assert_called_once_with(
            str(qwk_file), os.path.join("1995", "TEST.QWK")
        )


def test_organize_by_year_no_valid_dates(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    msg = MagicMock(spec=ParsedMessage)
    msg.header = MagicMock(spec=MessageHeader)
    msg.header.msgdate = ""
    msg.header.msgtime = ""

    board_dict = ConferenceMap()

    with (
        patch("pyqwk.core.load_data", return_value=([msg], board_dict)),
        patch("shutil.move") as mock_move,
        patch("os.makedirs") as mock_makedirs,
    ):
        organize_by_year([str(qwk_file)], mock_settings, logger)

        mock_makedirs.assert_called_once_with("Unknown_Year")
        mock_move.assert_called_once_with(
            str(qwk_file), os.path.join("Unknown_Year", "TEST.QWK")
        )


def test_organize_by_year_dry_run(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")
    mock_settings.dry_run = True

    msg = MagicMock(spec=ParsedMessage)
    msg.header = MagicMock(spec=MessageHeader)
    msg.header.msgdate = "05-20-98"
    msg.header.msgtime = "10:00"

    board_dict = ConferenceMap()

    with (
        patch("pyqwk.core.load_data", return_value=([msg], board_dict)),
        patch("shutil.move") as mock_move,
        patch("os.makedirs") as mock_makedirs,
    ):
        organize_by_year([str(qwk_file)], mock_settings, logger)

        mock_makedirs.assert_not_called()
        mock_move.assert_not_called()


def test_organize_by_year_file_not_found(mock_settings, logger):
    with patch("pyqwk.core.load_data") as mock_load:
        organize_by_year(["non_existent.qwk"], mock_settings, logger)
        mock_load.assert_not_called()


def test_organize_by_year_invalid_extension(tmp_path, mock_settings, logger):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("not supported")

    with patch("pyqwk.core.load_data") as mock_load:
        organize_by_year([str(txt_file)], mock_settings, logger)
        mock_load.assert_not_called()


def test_organize_by_year_exception_handling(tmp_path, mock_settings, logger, caplog):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    with (
        patch("pyqwk.core.load_data", side_effect=ValueError("Test Error")),
        patch("shutil.move") as mock_move,
    ):
        with caplog.at_level(logging.ERROR):
            organize_by_year([str(qwk_file)], mock_settings, logger)

        assert "Error organizing" in caplog.text
        assert "Test Error" in caplog.text
        mock_move.assert_not_called()


def test_get_organization_subpath_by_year(mock_settings):
    mock_settings.organize_by_year = True
    msg = MagicMock(spec=ParsedMessage)
    msg.header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="03-15-94",
        msgtime="12:00",
        msgto="All",
        msgfrom="Alice",
        msgsubject="Hello",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    subpath = _get_organization_subpath(msg, mock_settings)
    assert subpath == "1994"


def test_cli_organize_by_year_dispatch(tmp_path):
    from pyqwk.cli import main

    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy")

    with (
        patch("sys.argv", ["qwk", str(qwk_file), "--organize-by-year"]),
        patch("pyqwk.cli.organize_by_year") as mock_org,
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 0
    mock_org.assert_called_once()
