import os
import json
import logging
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    BBSInfo,
    ConferenceMap,
    _write_json,
    _write_jsonl,
    load_data,
    ProcessingSettings
)

def test_json_symmetry(tmp_path):
    logger = logging.getLogger("test")

    # 1. Setup sample data
    bbs_info = BBSInfo(
        name="Test BBS",
        location="Test City",
        sysop="Sysop Name",
        bbs_id="TESTBBS"
    )
    board_dict = ConferenceMap({1: "General", 2: "Tech"})
    board_dict.bbs_info = bbs_info

    msg1 = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
            msgto="All", msgfrom="Alice", msgsubject="Hello",
            msgpassword="", refnum=0, numblocks=1, msgflag=" ",
            confnum=1, lognum=0, nettag=" "
        ),
        confname="General",
        bbs_name="Test BBS"
    )

    messages = [msg1]

    json_path = os.path.join(tmp_path, "test.json")
    jsonl_path = os.path.join(tmp_path, "test.jsonl")

    # 2. Test JSON Export/Import
    _write_json(messages, json_path, bbs_info=bbs_info, board_dict=board_dict)

    # Verify file content structure
    with open(json_path, "r") as f:
        data = json.load(f)
        assert data["type"] == "qwk_archive"
        assert data["bbs_info"]["name"] == "Test BBS"
        assert data["conferences"]["1"] == "General"
        assert len(data["messages"]) == 1

    # Test Import
    imported_messages, imported_board_dict = load_data(json_path, logger)
    assert len(imported_messages) == 1
    assert imported_messages[0].text == "Hello world"
    assert imported_board_dict.bbs_info.name == "Test BBS"
    assert imported_board_dict[1] == "General"
    assert imported_board_dict[2] == "Tech"

    # 3. Test JSONL Export/Import
    _write_jsonl(messages, jsonl_path, bbs_info=bbs_info, board_dict=board_dict)

    # Verify file content structure
    with open(jsonl_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
        metadata = json.loads(lines[0])
        assert metadata["type"] == "metadata"
        assert metadata["bbs_info"]["bbs_id"] == "TESTBBS"

        msg_data = json.loads(lines[1])
        assert msg_data["header"]["msgfrom"] == "Alice"

    # Test Import
    imported_messages_l, imported_board_dict_l = load_data(jsonl_path, logger)
    assert len(imported_messages_l) == 1
    assert imported_messages_l[0].header.msgfrom == "Alice"
    assert imported_board_dict_l.bbs_info.bbs_id == "TESTBBS"
    assert imported_board_dict_l[2] == "Tech"

    # 4. Test Backward Compatibility (Plain list)
    plain_json_path = os.path.join(tmp_path, "plain.json")
    with open(plain_json_path, "w") as f:
        json.dump([{"text": "legacy", "header": msg1.header.as_dict}], f)

    imp_msgs, imp_bd = load_data(plain_json_path, logger)
    assert len(imp_msgs) == 1
    assert imp_msgs[0].text == "legacy"
    # Reconstructed from messages
    assert imp_bd[1] == "Conference 1"

if __name__ == "__main__":
    import sys
    from pathlib import Path

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_json_symmetry(tmp)
        print("Symmetry test passed!")
