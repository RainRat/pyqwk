import json
import logging
from pyqwk.core import load_data, ConferenceMap, ProcessingSettings, process_merged_files

def test_json_load_missing_optional_metadata(tmp_path):
    logger = logging.getLogger("test")

    # JSON with type qwk_archive but missing optional fields
    data = {
        "type": "qwk_archive",
        "messages": []
    }
    json_path = tmp_path / "test.json"
    json_path.write_text(json.dumps(data))

    msgs, bd = load_data(str(json_path), logger)
    assert msgs == []
    assert bd.bbs_info is None
    assert len(bd) == 0

def test_jsonl_load_missing_optional_metadata(tmp_path):
    logger = logging.getLogger("test")

    # JSONL with metadata but missing optional fields
    metadata = {"type": "metadata"}
    jsonl_path = tmp_path / "test.jsonl"
    jsonl_path.write_text(json.dumps(metadata) + "\n")

    msgs, bd = load_data(str(jsonl_path), logger)
    assert msgs == []
    assert bd.bbs_info is None
    assert len(bd) == 0

def test_text_import_whitespace_date(tmp_path):
    logger = logging.getLogger("test")
    # Date line with just whitespace
    content = """Conference: General (1)
From: Me
To: You
Subject: Hello
Date:
Status:

Body
"""
    txt_path = tmp_path / "test.txt"
    txt_path.write_text(content)

    msgs, bd = load_data(str(txt_path), logger)
    assert len(msgs) == 1
    # Default values from core.py
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

def test_text_import_date_only(tmp_path):
    logger = logging.getLogger("test")
    # Date line with just date, no time
    content = """Conference: General (1)
From: Me
To: You
Subject: Hello
Date: 01-01-2024
Status:

Body
"""
    txt_path = tmp_path / "test.txt"
    txt_path.write_text(content)

    msgs, bd = load_data(str(txt_path), logger)
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-2024"
    assert msgs[0].header.msgtime == "00:00"
