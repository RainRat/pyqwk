import os
import json
import logging
import pytest
from unittest.mock import patch
from pyqwk.core import validate_archive

@pytest.fixture
def logger():
    return logging.getLogger("test_validation_gaps")

def test_validate_archive_json_missing_messages(tmp_path, logger):
    p = tmp_path / "missing_messages.json"
    p.write_text(json.dumps({"type": "qwk_archive"}))
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert "JSON dictionary format lacks 'messages' field." in res["errors"]

def test_validate_archive_json_invalid_top_level(tmp_path, logger):
    p = tmp_path / "invalid_top.json"
    p.write_text("12345")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert "JSON data must be a list of messages or a structured dictionary." in res["errors"]

def test_validate_archive_json_message_not_dict(tmp_path, logger):
    p = tmp_path / "not_dict.json"
    p.write_text(json.dumps([123, {"header": {"msgfrom": "A", "msgto": "B", "msgsubject": "S", "msgnum": 1}}]))
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert "Message at index 0 is not a valid JSON object." in res["errors"]

def test_validate_archive_json_message_missing_header(tmp_path, logger):
    p = tmp_path / "missing_hdr.json"
    p.write_text(json.dumps([{"text": "Hello"}]))
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert "Message at index 0 is missing 'header' metadata." in res["warnings"]

def test_validate_archive_json_message_header_not_dict(tmp_path, logger):
    p = tmp_path / "hdr_not_dict.json"
    p.write_text(json.dumps([{"header": "not_a_dict"}]))
    res = json.loads(p.read_text())
    # The validate_archive has:
    # if not isinstance(hdr, dict):
    #     result["valid"] = False
    #     result["errors"].append(f"Message at index {i} has invalid 'header' type (expected dictionary).")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert "Message at index 0 has invalid 'header' type (expected dictionary)." in res["errors"]

def test_validate_archive_json_generic_exception(tmp_path, logger):
    p = tmp_path / "gen_exc.json"
    p.write_text(json.dumps([{"header": {"msgfrom": "A", "msgto": "B", "msgsubject": "S", "msgnum": 1}}]))
    with patch("json.load", side_effect=RuntimeError("Unexpected load error")):
        res = validate_archive(str(p), logger)
        assert res["valid"] is False
        assert "JSON schema validation failed: Unexpected load error" in res["errors"]

def test_validate_archive_jsonl_empty_lines_and_not_dict(tmp_path, logger):
    p = tmp_path / "gaps.jsonl"
    p.write_text("\n\n12345\n\n")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert "JSONL line 3 is not a valid object." in res["errors"]

def test_validate_archive_jsonl_missing_header_and_warnings(tmp_path, logger):
    p = tmp_path / "warns.jsonl"
    p.write_text('{"text": "Hello"}\n')
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert "JSONL line 1 is missing 'header' metadata." in res["warnings"]

def test_validate_archive_jsonl_syntax_error(tmp_path, logger):
    p = tmp_path / "syntax.jsonl"
    p.write_text('{"header": {"msgfrom": "A"}\n')
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("JSONL syntax error on line 1" in err for err in res["errors"])

def test_validate_archive_jsonl_generic_exception(tmp_path, logger):
    p = tmp_path / "exc.jsonl"
    p.write_text('{"header": {"msgfrom": "A"}}\n')
    with patch("builtins.open", side_effect=RuntimeError("Unexpected file open error")):
        res = validate_archive(str(p), logger)
        assert res["valid"] is False
        assert "JSONL validation failed: Unexpected file open error" in res["errors"]

def test_validate_archive_csv_generic_exception(tmp_path, logger):
    p = tmp_path / "exc.csv"
    p.write_text("msgfrom,msgto,msgsubject,text\nBob,Alice,Hi,Hello\n")
    with patch("builtins.open", side_effect=RuntimeError("Unexpected open error")):
        res = validate_archive(str(p), logger)
        assert res["valid"] is False
        assert "CSV validation failed: Unexpected open error" in res["errors"]

def test_validate_archive_xml_missing_header_warning(tmp_path, logger):
    p = tmp_path / "missing_hdr.xml"
    p.write_text("<messages><message><text>Hello</text></message></messages>")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert "XML message 1 is missing '<header>' metadata." in res["warnings"]

def test_validate_archive_xml_syntax_error(tmp_path, logger):
    p = tmp_path / "syntax.xml"
    p.write_text("<messages><message>")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("XML parsing failed" in err for err in res["errors"])

def test_validate_archive_xml_generic_exception(tmp_path, logger):
    p = tmp_path / "exc.xml"
    p.write_text("<messages><message><text>Hello</text></message></messages>")
    with patch("xml.etree.ElementTree.parse", side_effect=RuntimeError("XML failure")):
        res = validate_archive(str(p), logger)
        assert res["valid"] is False
        assert "XML schema validation error: XML failure" in res["errors"]

def test_validate_archive_sqlite_validation_failed(tmp_path, logger):
    p = tmp_path / "corrupt.db"
    p.write_text("not a sqlite database")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("SQLite validation failed" in err for err in res["errors"])

def test_validate_archive_format_validation_failed(tmp_path, logger):
    p = tmp_path / "exc.html"
    p.write_text("<html></html>")
    with patch("pyqwk.core.load_data", side_effect=RuntimeError("Load error")):
        res = validate_archive(str(p), logger)
        assert res["valid"] is False
        assert "Format validation failed for html: Load error" in res["errors"]

def test_validate_archive_unsupported_compressed(tmp_path, logger):
    p = tmp_path / "unsupported.tar.bz2"
    p.write_text("some random dummy content")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert "Unsupported or corrupted compressed archive format." in res["errors"]
