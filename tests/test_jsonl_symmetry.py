import logging
import os
from pyqwk.core import load_data, write_messages, ProcessingSettings, ParsedMessage, MessageHeader

def test_jsonl_symmetry():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")

    # Create a dummy message
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="10:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=""
    )
    msg = ParsedMessage(
        text="Hello world\nThis is a test.",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="TestBBS"
    )

    messages = [msg]
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="jsonl",
        separator="none", output_mode="file", output_path="test.jsonl",
        encoding="utf-8"
    )

    print("Writing messages to test.jsonl...")
    write_messages(messages, "test.jsonl", settings)

    print("Loading messages from test.jsonl...")
    loaded_messages, board_dict = load_data("test.jsonl", logger)

    print(f"Loaded {len(loaded_messages)} messages.")
    assert len(loaded_messages) == 1
    loaded_msg = loaded_messages[0]
    assert loaded_msg.header.msgsubject == "Test Subject"
    assert loaded_msg.text.strip() == "Hello world\nThis is a test.".strip()
    assert loaded_msg.bbs_name == "TestBBS"
    assert board_dict[1] == "General"

    print("JSONL Symmetry test passed!")

if __name__ == "__main__":
    try:
        test_jsonl_symmetry()
    finally:
        if os.path.exists("test.jsonl"):
            os.remove("test.jsonl")
