import sys
import logging
import pytest
from unittest.mock import patch, MagicMock
from pyqwk.cli import main


def test_cli_validate_success_no_colors(caplog):
    mock_res = {
        "valid": True,
        "format": "qwk",
        "messages_count": 10,
        "errors": [],
        "warnings": [],
    }

    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = False

    with patch("pyqwk.cli.validate_archive", return_value=mock_res), \
         patch("sys.stdout", mock_stdout), \
         patch("sys.argv", ["qwk", "dummy.qwk", "--validate"]), \
         caplog.at_level(logging.INFO):

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 0
        assert len(caplog.records) == 1
        assert "File: dummy.qwk (qwk, 10 messages) - [VALID]" in caplog.records[0].message


def test_cli_validate_success_with_colors(caplog):
    mock_res = {
        "valid": True,
        "format": "qwk",
        "messages_count": 5,
        "errors": [],
        "warnings": [],
    }

    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = True

    with patch("pyqwk.cli.validate_archive", return_value=mock_res), \
         patch("sys.stdout", mock_stdout), \
         patch("sys.argv", ["qwk", "dummy.qwk", "--validate"]), \
         caplog.at_level(logging.INFO):

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 0
        assert len(caplog.records) == 1
        assert "File: dummy.qwk (qwk, 5 messages) - [\033[1;32mVALID\033[0m]" in caplog.records[0].message


def test_cli_validate_failure_with_errors_and_warnings(caplog):
    mock_res = {
        "valid": False,
        "format": "rep",
        "messages_count": 0,
        "errors": ["Missing essential headers", "Corrupted block"],
        "warnings": ["Non-standard character encoding used"],
    }

    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = False

    with patch("pyqwk.cli.validate_archive", return_value=mock_res), \
         patch("sys.stdout", mock_stdout), \
         patch("sys.argv", ["qwk", "invalid.rep", "--validate"]), \
         caplog.at_level(logging.INFO):

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
        # Expect 1 main log, 2 error logs, and 1 warning log = 4 records
        assert len(caplog.records) == 4
        assert "File: invalid.rep (rep, 0 messages) - [INVALID]" in caplog.records[0].message
        assert "  - [Error] Missing essential headers" in caplog.records[1].message
        assert "  - [Error] Corrupted block" in caplog.records[2].message
        assert "  - [Warning] Non-standard character encoding used" in caplog.records[3].message


def test_cli_validate_multiple_files_mixed_results(caplog):
    def mock_validate(path, logger, encoding):
        if path == "valid.qwk":
            return {
                "valid": True,
                "format": "qwk",
                "messages_count": 4,
                "errors": [],
                "warnings": [],
            }
        else:
            return {
                "valid": False,
                "format": "rep",
                "messages_count": 2,
                "errors": ["Bad checksum"],
                "warnings": ["Warning flag"],
            }

    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = False

    with patch("pyqwk.cli.validate_archive", side_effect=mock_validate), \
         patch("sys.stdout", mock_stdout), \
         patch("sys.argv", ["qwk", "valid.qwk", "invalid.rep", "--validate"]), \
         caplog.at_level(logging.INFO):

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
        messages = [r.message for r in caplog.records]
        assert "File: valid.qwk (qwk, 4 messages) - [VALID]" in messages
        assert "File: invalid.rep (rep, 2 messages) - [INVALID]" in messages
        assert "  - [Error] Bad checksum" in messages
        assert "  - [Warning] Warning flag" in messages


def test_cli_validate_multiple_files_all_success(caplog):
    mock_res = {
        "valid": True,
        "format": "json",
        "messages_count": 8,
        "errors": [],
        "warnings": [],
    }

    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = False

    with patch("pyqwk.cli.validate_archive", return_value=mock_res), \
         patch("sys.stdout", mock_stdout), \
         patch("sys.argv", ["qwk", "f1.json", "f2.json", "--validate"]), \
         caplog.at_level(logging.INFO):

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 0
        messages = [r.message for r in caplog.records]
        assert "File: f1.json (json, 8 messages) - [VALID]" in messages
        assert "File: f2.json (json, 8 messages) - [VALID]" in messages
