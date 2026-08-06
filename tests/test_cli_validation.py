import sys
import pytest
import logging
from unittest.mock import MagicMock
from pyqwk.cli import main


def test_cli_validate_success(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["qwk", "dummy_archive.zip", "--validate"])

    mock_validate = MagicMock(return_value={
        "valid": True,
        "format": "ZIP",
        "messages_count": 42,
        "errors": [],
        "warnings": ["Some minor warning"]
    })

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "validate_archive", mock_validate)

    mock_isatty = MagicMock(return_value=False)
    monkeypatch.setattr(sys.stdout, "isatty", mock_isatty)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 0
    assert mock_validate.call_count == 1
    args, kwargs = mock_validate.call_args
    assert args[0] == "dummy_archive.zip"
    assert args[2] == "cp437"

    assert any("dummy_archive.zip" in r.message for r in caplog.records)
    assert any("VALID" in r.message for r in caplog.records)
    assert any("Some minor warning" in r.message for r in caplog.records)


def test_cli_validate_success_colorized(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["qwk", "dummy_archive.zip", "--validate"])

    mock_validate = MagicMock(return_value={
        "valid": True,
        "format": "ZIP",
        "messages_count": 42,
        "errors": [],
        "warnings": []
    })

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "validate_archive", mock_validate)

    mock_isatty = MagicMock(return_value=True)
    monkeypatch.setattr(sys.stdout, "isatty", mock_isatty)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 0
    assert any("\033[1;32mVALID\033[0m" in r.message for r in caplog.records)


def test_cli_validate_failure_colorized(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["qwk", "bad_archive.zip", "--validate"])

    mock_validate = MagicMock(return_value={
        "valid": False,
        "format": "ZIP",
        "messages_count": 10,
        "errors": ["Corrupted block header"],
        "warnings": ["Empty block detected"]
    })

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "validate_archive", mock_validate)

    mock_isatty = MagicMock(return_value=True)
    monkeypatch.setattr(sys.stdout, "isatty", mock_isatty)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
    assert any("\033[1;31mINVALID\033[0m" in r.message for r in caplog.records)
    assert any("Corrupted block header" in r.message for r in caplog.records)
    assert any("Empty block detected" in r.message for r in caplog.records)


def test_cli_validate_multiple_archives_one_invalid(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["qwk", "archive1.zip", "archive2.zip", "--validate"])

    validation_results = {
        "archive1.zip": {
            "valid": True,
            "format": "ZIP",
            "messages_count": 5,
            "errors": [],
            "warnings": []
        },
        "archive2.zip": {
            "valid": False,
            "format": "TAR",
            "messages_count": 0,
            "errors": ["Invalid TAR checksum"],
            "warnings": []
        }
    }

    def mock_validate_archive(input_path, logger, encoding="cp437"):
        return validation_results[input_path]

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "validate_archive", mock_validate_archive)

    mock_isatty = MagicMock(return_value=False)
    monkeypatch.setattr(sys.stdout, "isatty", mock_isatty)

    with caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
    assert any("archive1.zip" in r.message for r in caplog.records)
    assert any("VALID" in r.message for r in caplog.records)
    assert any("archive2.zip" in r.message for r in caplog.records)
    assert any("INVALID" in r.message for r in caplog.records)
    assert any("Invalid TAR checksum" in r.message for r in caplog.records)
