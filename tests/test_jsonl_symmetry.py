import logging
import os
from pyqwk.core import (
    load_data,
    write_messages,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)


def test_jsonl_symmetry(tmp_path):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    test_jsonl = os.path.join(tmp_path, "test.jsonl")

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
        nettag="",
    )
    msg = ParsedMessage(
        text="Hello world\nThis is a test.",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="TestBBS",
    )

    messages = [msg]
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="jsonl",
        separator="none",
        output_mode="file",
        output_path=test_jsonl,
        encoding="utf-8",
    )

    print(f"Writing messages to {test_jsonl}...")
    write_messages(messages, test_jsonl, settings)

    print(f"Loading messages from {test_jsonl}...")
    loaded_messages, board_dict = load_data(test_jsonl, logger)

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


def test_qwk_jsonl_qwk_round_trip_preserves_body_and_header_fields(tmp_path):
    """Round-trip a synthetic QWK message through JSONL and compare supported fields."""
    import logging

    from pyqwk.core import BBSInfo, _write_qwk, parse_messages

    logger = logging.getLogger("test_jsonl_round_trip")
    source_qwk = tmp_path / "source.qwk"
    jsonl_path = tmp_path / "messages.jsonl"
    roundtrip_qwk = tmp_path / "roundtrip.qwk"

    header = MessageHeader(
        status="*",
        msgnum=42,
        msgdate="10-12-23",
        msgtime="23:59",
        msgto="Recipient",
        msgfrom="Sender",
        msgsubject="Synthetic round trip",
        msgpassword="secret",
        refnum=7,
        numblocks=2,
        msgflag="+",
        confnum=3,
        lognum=4,
        nettag="N",
    )
    message = ParsedMessage(
        text="Line one\nLine two",
        msgnum=42,
        refnum=7,
        confnum=3,
        header=header,
        confname="General",
        bbs_name="Synthetic BBS",
        bbs_id="SYNTH",
    )
    _write_qwk(
        [message],
        str(source_qwk),
        bbs_info=BBSInfo(name="Synthetic BBS", bbs_id="SYNTH"),
        board_dict={3: "General"},
    )

    def settings(fmt: str, output: str) -> ProcessingSettings:
        return ProcessingSettings(
            verbose=True,
            private=True,
            no_header=False,
            truncate_signatures=False,
            cut_quoting=False,
            individual_files=False,
            threaded=False,
            binaries_removal=False,
            redact_pii=False,
            format=fmt,
            separator="none",
            output_mode="file",
            output_path=output,
            encoding="cp437",
            quiet=True,
        )

    from pyqwk.core import process_merged_files

    process_merged_files([str(source_qwk)], settings("jsonl", str(jsonl_path)), logger)
    jsonl_messages, _ = load_data(str(jsonl_path), logger)
    assert len(jsonl_messages) == 1

    process_merged_files(
        [str(jsonl_path)], settings("qwk", str(roundtrip_qwk)), logger
    )
    roundtrip_data, _ = load_data(str(roundtrip_qwk), logger)
    roundtrip_messages = list(parse_messages(roundtrip_data, None))
    assert len(roundtrip_messages) == 1

    original_data, _ = load_data(str(source_qwk), logger)
    original = list(parse_messages(original_data, None))[0]
    restored = roundtrip_messages[0]

    assert original.text == "Line one\r\nLine two\r\n"
    assert restored.text == original.text
    for field in (
        "status",
        "msgnum",
        "msgdate",
        "msgtime",
        "msgto",
        "msgfrom",
        "msgsubject",
        "msgpassword",
        "refnum",
        "msgflag",
        "confnum",
        "lognum",
        "nettag",
    ):
        assert getattr(restored.header, field) == getattr(original.header, field), field
