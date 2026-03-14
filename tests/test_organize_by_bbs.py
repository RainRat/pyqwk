import os
import logging
import pytest
from unittest.mock import patch
from pyqwk.core import organize_by_bbs, ProcessingSettings, ConferenceMap, BBSInfo

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
        organize_by_bbs=True,
    )

@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.test_organize_by_bbs")

def test_organize_by_bbs_success(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    board_dict = ConferenceMap()
    board_dict.bbs_info = BBSInfo(name="My Awesome BBS")

    with patch("pyqwk.core.load_data", return_value=(bytearray(), board_dict)), \
         patch("shutil.move") as mock_move, \
         patch("os.makedirs") as mock_makedirs:

        organize_by_bbs([str(qwk_file)], mock_settings, logger)

        mock_makedirs.assert_called_once_with("My Awesome BBS")
        mock_move.assert_called_once_with(str(qwk_file), os.path.join("My Awesome BBS", "TEST.QWK"))

def test_organize_by_bbs_with_id(tmp_path, mock_settings, logger):
    json_file = tmp_path / "archive.json"
    json_file.write_text("[]")

    board_dict = ConferenceMap()
    board_dict.bbs_info = BBSInfo(name="The Board", bbs_id="BOARDID")

    with patch("pyqwk.core.load_data", return_value=([], board_dict)), \
         patch("shutil.move") as mock_move, \
         patch("os.makedirs") as mock_makedirs:

        organize_by_bbs([str(json_file)], mock_settings, logger)

        expected_folder = "The Board (BOARDID)"
        mock_makedirs.assert_called_once_with(expected_folder)
        mock_move.assert_called_once_with(str(json_file), os.path.join(expected_folder, "archive.json"))

def test_organize_by_bbs_only_id(tmp_path, mock_settings, logger):
    db_file = tmp_path / "archive.db"
    db_file.write_text("sqlite")

    board_dict = ConferenceMap()
    board_dict.bbs_info = BBSInfo(name="", bbs_id="ONLYID")

    with patch("pyqwk.core.load_data", return_value=([], board_dict)), \
         patch("shutil.move") as mock_move, \
         patch("os.makedirs") as mock_makedirs:

        organize_by_bbs([str(db_file)], mock_settings, logger)

        expected_folder = "Unknown BBS (ONLYID)"
        mock_makedirs.assert_called_once_with(expected_folder)
        mock_move.assert_called_once_with(str(db_file), os.path.join(expected_folder, "archive.db"))

def test_organize_by_bbs_dry_run(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")
    mock_settings.dry_run = True

    board_dict = ConferenceMap()
    board_dict.bbs_info = BBSInfo(name="My Awesome BBS")

    with patch("pyqwk.core.load_data", return_value=(bytearray(), board_dict)), \
         patch("shutil.move") as mock_move, \
         patch("os.makedirs") as mock_makedirs:

        organize_by_bbs([str(qwk_file)], mock_settings, logger)

        mock_makedirs.assert_not_called()
        mock_move.assert_not_called()

def test_organize_by_bbs_missing_bbs_info(tmp_path, mock_settings, logger, caplog):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    board_dict = ConferenceMap() # No BBSInfo

    with patch("pyqwk.core.load_data", return_value=(bytearray(), board_dict)), \
         patch("shutil.move") as mock_move:

        with caplog.at_level(logging.WARNING):
            organize_by_bbs([str(qwk_file)], mock_settings, logger)

        assert "Could not find BBS information" in caplog.text
        mock_move.assert_not_called()

def test_organize_by_bbs_supported_extensions(tmp_path, mock_settings, logger):
    extensions = ['.qwk', '.rep', '.json', '.csv', '.xml', '.db', '.sqlite', '.mbox', '.eml']

    for ext in extensions:
        test_file = tmp_path / f"test{ext}"
        test_file.write_text("dummy")

        board_dict = ConferenceMap()
        board_dict.bbs_info = BBSInfo(name="BBS")

        with patch("pyqwk.core.load_data", return_value=([], board_dict)), \
             patch("shutil.move") as mock_move, \
             patch("os.makedirs"):

            organize_by_bbs([str(test_file)], mock_settings, logger)
            mock_move.assert_called_once()

def test_organize_by_bbs_invalid_extension(tmp_path, mock_settings, logger):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("not supported")

    with patch("pyqwk.core.load_data") as mock_load:
        organize_by_bbs([str(txt_file)], mock_settings, logger)
        mock_load.assert_not_called()

def test_organize_by_bbs_file_not_found(mock_settings, logger):
    with patch("pyqwk.core.load_data") as mock_load:
        organize_by_bbs(["non_existent.qwk"], mock_settings, logger)
        mock_load.assert_not_called()

def test_organize_by_bbs_exception_handling(tmp_path, mock_settings, logger, caplog):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    with patch("pyqwk.core.load_data", side_effect=ValueError("Boom")), \
         patch("shutil.move") as mock_move:

        with caplog.at_level(logging.ERROR):
            organize_by_bbs([str(qwk_file)], mock_settings, logger)

        assert "Error organizing" in caplog.text
        assert "Boom" in caplog.text
        mock_move.assert_not_called()

def test_organize_by_bbs_unsafe_name(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    board_dict = ConferenceMap()
    # Name with unsafe characters
    board_dict.bbs_info = BBSInfo(name="BBS / With \\ Unsafe? * Chars")

    with patch("pyqwk.core.load_data", return_value=(bytearray(), board_dict)), \
         patch("shutil.move") as mock_move, \
         patch("os.makedirs") as mock_makedirs:

        organize_by_bbs([str(qwk_file)], mock_settings, logger)

        # Should be sanitized: "BBS  With  Unsafe  Chars" (stripping / \ ? *)
        expected_name = "BBS  With  Unsafe  Chars"
        mock_makedirs.assert_called_once_with(expected_name)
        mock_move.assert_called_once_with(str(qwk_file), os.path.join(expected_name, "TEST.QWK"))

def test_organize_by_bbs_empty_safe_name(tmp_path, mock_settings, logger):
    qwk_file = tmp_path / "TEST.QWK"
    qwk_file.write_text("dummy content")

    board_dict = ConferenceMap()
    # Name that becomes empty after sanitization
    board_dict.bbs_info = BBSInfo(name="!!!")

    with patch("pyqwk.core.load_data", return_value=(bytearray(), board_dict)), \
         patch("shutil.move") as mock_move, \
         patch("os.makedirs") as mock_makedirs:

        organize_by_bbs([str(qwk_file)], mock_settings, logger)

        mock_makedirs.assert_called_once_with("Unknown_BBS")
        mock_move.assert_called_once_with(str(qwk_file), os.path.join("Unknown_BBS", "TEST.QWK"))
