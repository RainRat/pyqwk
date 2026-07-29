import sys
import json
import logging
import pytest
from unittest.mock import patch
from pyqwk.cli import main

def test_cli_validate_success_tty(tmp_path, monkeypatch, caplog):
    p = tmp_path / "archive.json"
    msg_data = {
        "type": "qwk_archive",
        "messages": [
            {
                "header": {
                    "msgfrom": "Bob",
                    "msgto": "Alice",
                    "msgsubject": "Hi",
                    "msgnum": 1,
                    "confnum": 1,
                    "status": " ",
                    "msgflag": " "
                },
                "text": "Hello World"
            }
        ]
    }
    p.write_text(json.dumps(msg_data))

    monkeypatch.setattr(sys, "argv", ["qwk", str(p), "--validate"])

    with patch.object(sys.stdout, "isatty", return_value=True), caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    assert len(caplog.records) > 0
    message_texts = [r.message for r in caplog.records]
    assert any("File:" in msg for msg in message_texts)
    assert any("\x1b[1;32mVALID" in msg for msg in message_texts)


def test_cli_validate_success_non_tty(tmp_path, monkeypatch, caplog):
    p = tmp_path / "archive.json"
    msg_data = {
        "type": "qwk_archive",
        "messages": [
            {
                "header": {
                    "msgfrom": "Bob",
                    "msgto": "Alice",
                    "msgsubject": "Hi",
                    "msgnum": 1,
                    "confnum": 1,
                    "status": " ",
                    "msgflag": " "
                },
                "text": "Hello World"
            }
        ]
    }
    p.write_text(json.dumps(msg_data))

    monkeypatch.setattr(sys, "argv", ["qwk", str(p), "--validate"])

    with patch.object(sys.stdout, "isatty", return_value=False), caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    assert len(caplog.records) > 0
    message_texts = [r.message for r in caplog.records]
    assert any("File:" in msg for msg in message_texts)
    assert any("messages) - [VALID]" in msg for msg in message_texts)
    assert all("\x1b[1;32m" not in msg for msg in message_texts)


def test_cli_validate_failure(tmp_path, monkeypatch, caplog):
    p = tmp_path / "archive.json"
    p.write_text("invalid json")

    monkeypatch.setattr(sys, "argv", ["qwk", str(p), "--validate"])

    with patch.object(sys.stdout, "isatty", return_value=False), caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    assert len(caplog.records) > 0
    message_texts = [r.message for r in caplog.records]
    assert any("File:" in msg for msg in message_texts)
    assert any("[INVALID]" in msg for msg in message_texts)
    assert any("- [Error]" in msg for msg in message_texts)


def test_cli_validate_warnings_and_errors(tmp_path, monkeypatch, caplog):
    p = tmp_path / "archive.json"
    msg_data = {
        "type": "qwk_archive",
        "messages": [
            {
                "header": {
                    "msgfrom": "Bob",
                    "msgto": "Alice",
                    # msgsubject and some other fields are missing
                    "msgnum": 1,
                    "confnum": 1,
                },
                "text": "Hello World"
            }
        ]
    }
    p.write_text(json.dumps(msg_data))

    monkeypatch.setattr(sys, "argv", ["qwk", str(p), "--validate"])

    with patch.object(sys.stdout, "isatty", return_value=False), caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0  # Missing fields produce warnings but valid is still True if it meets schema

    assert len(caplog.records) > 0
    message_texts = [r.message for r in caplog.records]
    assert any("File:" in msg for msg in message_texts)
    assert any("messages) - [VALID]" in msg for msg in message_texts)
    assert any("- [Warning]" in msg for msg in message_texts)


def test_cli_validate_multiple_archives(tmp_path, monkeypatch, caplog):
    p_good = tmp_path / "archive1.json"
    msg_data = {
        "type": "qwk_archive",
        "messages": []
    }
    p_good.write_text(json.dumps(msg_data))

    p_bad = tmp_path / "archive2.json"
    p_bad.write_text("bad json")

    monkeypatch.setattr(sys, "argv", ["qwk", str(p_good), str(p_bad), "--validate"])

    with patch.object(sys.stdout, "isatty", return_value=False), caplog.at_level(logging.INFO):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    assert len(caplog.records) > 0
    message_texts = [r.message for r in caplog.records]
    assert any(str(p_good) in msg for msg in message_texts)
    assert any(str(p_bad) in msg for msg in message_texts)
