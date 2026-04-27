import os
import zipfile
import tempfile
import logging
import pytest
import struct
from pyqwk.core import load_data, MessageHeader, ParsedMessage, ConferenceMap, BBSInfo

def test_zip_batch_nested_qwk_bytes_coverage():
    """Cover lines 1759-1763: Parsing nested QWK bytes during batch merge."""
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a messages.dat style content
        # 128 bytes BBS ID + 128 bytes Header + body blocks
        bbs_id = b"TEST_BBS".ljust(128)

        # numblocks 2 means 1 header block + 1 text block
        header = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
            msgto="To", msgfrom="From", msgsubject="Subj", msgpassword="",
            refnum=0, numblocks=2, msgflag=" ", confnum=1, lognum=1, nettag=" "
        )
        header_bytes = header.to_bytes()
        body = b"Test message body".ljust(128, b" ") # 1 block

        qwk_content = bbs_id + header_bytes + body

        # In batch mode, load_data(nested.qwk) will be called.
        # It needs to return a ConferenceMap to avoid AttributeError on b_dict.bbs_info
        # .qwk files are handled as classic QWK by the final else block in load_data.
        # But for .qwk, it doesn't automatically look for control.dat unless it's named MESSAGES.DAT.

        # To ensure load_data returns a ConferenceMap, we can use a format that does: e.g. .json
        # But we want to test line 1759 which requires data to be a bytearray.
        # The only way to get bytearray is the final else block.
        # The final else block in load_data (lines 1774-1785) returns (file_data, board_dict)
        # where board_dict is initialized at line 1568.

        qwk_path = os.path.join(tmpdir, "nested.qwk")
        with open(qwk_path, "wb") as f:
            f.write(qwk_content)

        other_path = os.path.join(tmpdir, "other.json")
        with open(other_path, "w") as f:
            f.write("[]")

        zip_path = os.path.join(tmpdir, "batch_qwk.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(qwk_path, arcname="nested.qwk")
            zf.write(other_path, arcname="other.json")

        # We need to monkeypatch load_data's return for nested.qwk to have a bbs_info-compatible board_dict
        # Or just fix the code if it's a bug. The prompt says I CAN fix bugs.
        # "If your testing reveals a definitive, non-debatable bug... you are authorized to fix the source code"
        # It IS a bug because board_dict: dict = {} doesn't have bbs_info, but the merging logic assumes it does.

        # Let's try to verify if it's a bug by running it. (Already did, it failed with AttributeError)

        messages, board_dict = load_data(zip_path, logger)
        assert len(messages) == 1
        assert messages[0].header.msgfrom.strip() == "From"

def test_zip_batch_merge_bbs_info_no_name_coverage():
    """Cover line 1750: Merging BBS info when first has no name."""
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # File 1: BBS info with no name
        json1_path = os.path.join(tmpdir, "1.json")
        with open(json1_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A", "msgsubject": "S", "confnum": 1}, "text": "B", "bbs_name": ""}]')

        # File 2: BBS info with name
        json2_path = os.path.join(tmpdir, "2.json")
        with open(json2_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A2", "msgsubject": "S2", "confnum": 2}, "text": "B2", "bbs_name": "RealBBS"}]')

        zip_path = os.path.join(tmpdir, "bbs_merge.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(json1_path, arcname="1.json")
            zf.write(json2_path, arcname="2.json")

        messages, board_dict = load_data(zip_path, logger)

        assert board_dict.bbs_info.name == "RealBBS"

def test_zip_batch_exception_handling_coverage(caplog):
    """Cover lines 1766-1767: Exception handling during batch load."""
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Valid file
        json_path = os.path.join(tmpdir, "valid.json")
        with open(json_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A", "msgsubject": "S", "confnum": 1}, "text": "B"}]')

        # Invalid "supported" file (invalid JSON)
        corrupt_path = os.path.join(tmpdir, "corrupt.json")
        with open(corrupt_path, "w") as f:
            f.write("invalid json {")

        zip_path = os.path.join(tmpdir, "corrupt.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(json_path, arcname="valid.json")
            zf.write(corrupt_path, arcname="corrupt.json")

        with caplog.at_level(logging.WARNING):
            messages, board_dict = load_data(zip_path, logger)

        assert len(messages) == 1
        assert "Skipping file corrupt.json in ZIP due to error" in caplog.text

def test_zip_batch_no_messages_error_coverage():
    """Cover line 1770: ValueError when no messages found in ZIP."""
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Files that yield no messages
        json_path = os.path.join(tmpdir, "empty.json")
        with open(json_path, "w") as f:
            f.write("[]")

        zip_path = os.path.join(tmpdir, "empty.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(json_path, arcname="empty.json")

        with pytest.raises(ValueError, match="No messages could be loaded from ZIP archive"):
            load_data(zip_path, logger)
