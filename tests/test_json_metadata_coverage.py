import json
import logging
import pytest
from pyqwk.core import load_data

@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

def test_json_metadata_missing_fields(tmp_path, logger):
    """Test JSON loading when optional metadata fields are missing."""
    data = {
        "type": "qwk_archive",
        "messages": [
            {
                "header": {"msgfrom": "Alice", "msgto": "Bob", "msgsubject": "Hi", "confnum": 1},
                "text": "Hello"
            }
        ]
    }
    json_path = tmp_path / "missing_meta.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    messages, board_dict = load_data(str(json_path), logger)
    assert len(messages) == 1
    assert board_dict.bbs_info is None
    assert 1 not in board_dict

def test_jsonl_metadata_missing_fields(tmp_path, logger):
    """Test JSONL loading when optional metadata fields are missing."""
    jsonl_path = tmp_path / "missing_meta.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "metadata"}) + "\n")
        f.write(json.dumps({
            "header": {"msgfrom": "Alice", "msgto": "Bob", "msgsubject": "Hi", "confnum": 1},
            "text": "Hello"
        }) + "\n")

    messages, board_dict = load_data(str(jsonl_path), logger)
    assert len(messages) == 1
    assert board_dict.bbs_info is None
    assert 1 not in board_dict
