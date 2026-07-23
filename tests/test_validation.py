import os
import json
import logging
import pytest
from pyqwk.core import validate_archive, BLOCK_SIZE
from pyqwk.cli import main
import sys
from unittest.mock import patch

def test_validate_nonexistent_file():
    res = validate_archive("does_not_exist_at_all.qwk")
    assert res["status"] == "FAILED"
    assert "does_not_exist" in res["errors"][0]

def test_validate_empty_file(tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_bytes(b"")
    res = validate_archive(str(empty_file))
    assert res["status"] == "FAILED"
    assert "empty" in res["errors"][0]

def test_validate_valid_json_file(tmp_path):
    valid_file = tmp_path / "valid.json"
    message_data = [
        {
            "text": "Hello world",
            "msgnum": 1,
            "refnum": 0,
            "confnum": 1,
            "header": {
                "status": " ",
                "msgnum": 1,
                "msgdate": "10-12-23",
                "msgtime": "12:00",
                "msgto": "Alice",
                "msgfrom": "Bob",
                "msgsubject": "Test",
                "msgpassword": "",
                "refnum": 0,
                "numblocks": 1,
                "msgflag": "",
                "confnum": 1,
                "lognum": 1,
                "nettag": ""
            }
        }
    ]
    valid_file.write_text(json.dumps(message_data), encoding="utf-8")
    res = validate_archive(str(valid_file))
    assert res["status"] == "PASSED"
    assert res["message_count"] == 1
    assert len(res["errors"]) == 0
    assert len(res["warnings"]) == 0

def test_validate_json_missing_fields(tmp_path):
    invalid_file = tmp_path / "missing_fields.json"
    message_data = [
        {
            "text": "Hello \x00 world",  # Has null byte
            "msgnum": 1,
            "refnum": 0,
            "confnum": 1,
            "header": {
                "status": " ",
                "msgnum": 1,
                "msgdate": "",  # Empty date
                "msgtime": "12:00",
                "msgto": " ",  # Empty to
                "msgfrom": "",  # Empty from
                "msgsubject": "Test",
                "msgpassword": "",
                "refnum": 0,
                "numblocks": 1,
                "msgflag": "",
                "confnum": 1,
                "lognum": 1,
                "nettag": ""
            }
        }
    ]
    invalid_file.write_text(json.dumps(message_data), encoding="utf-8")
    res = validate_archive(str(invalid_file))
    assert res["status"] == "WARNING"
    assert res["message_count"] == 1
    assert len(res["warnings"]) > 0
    warnings_str = " ".join(res["warnings"])
    assert "null bytes" in warnings_str
    assert "Author field" in warnings_str
    assert "Recipient field" in warnings_str
    assert "Date field" in warnings_str

def test_validate_misaligned_qwk_file(tmp_path):
    misaligned_file = tmp_path / "messages.dat"
    # Write 100 bytes (BLOCK_SIZE is 128)
    misaligned_file.write_bytes(b"a" * 100)
    res = validate_archive(str(misaligned_file))
    assert res["status"] in ("FAILED", "WARNING")  # Size check warning/error and failed parse
    warnings_str = " ".join(res["warnings"])
    assert "multiple of 128" in warnings_str

def test_validate_cli_passed(tmp_path, capsys):
    valid_file = tmp_path / "valid.json"
    message_data = []
    valid_file.write_text(json.dumps(message_data), encoding="utf-8")

    test_args = ["qwk", "--validate", str(valid_file)]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ARCHIVE VALIDATION REPORT" in captured.out
    assert "Status: PASSED" in captured.out

def test_validate_cli_failed(capsys):
    test_args = ["qwk", "--validate", "nonexistent.qwk"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ARCHIVE VALIDATION REPORT" in captured.out
    assert "Status: FAILED" in captured.out
