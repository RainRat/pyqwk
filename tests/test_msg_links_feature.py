import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters, _get_message_mapping

def test_msg_links_filtering():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="Author", msgsubject="Test",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )

    msg_with_link = ParsedMessage(text="Check msg #123 for details.", msgnum=1, refnum=None, confnum=1, header=header)
    msg_without_link = ParsedMessage(text="No links here.", msgnum=2, refnum=None, confnum=1, header=header)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        has_msg_links=True
    )

    assert matches_filters(msg_with_link, settings, set()) is True
    assert matches_filters(msg_without_link, settings, set()) is False

def test_msg_links_template_variables():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="Author", msgsubject="Test",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )

    text = "See msg #10 and message 20."
    msg = ParsedMessage(text=text, msgnum=1, refnum=None, confnum=1, header=header)

    mapping = _get_message_mapping(msg, 1)

    assert mapping["msg_link_count"] == 2
    assert "msg #10" in mapping["msg_links"]
    assert "message 20" in mapping["msg_links"]

def test_cli_has_msg_links_flag(capsys, monkeypatch):
    import pyqwk.cli
    import json
    import os

    # Create a dummy jsonl file with two messages
    test_file = "test_msg_links.jsonl"
    with open(test_file, "w") as f:
        f.write(json.dumps({
            "header": {"msgfrom": "A", "msgto": "B", "msgsubject": "S", "msgdate": "01-01-23", "msgtime": "12:00", "confnum": 1, "status": " ", "msgnum": 1},
            "text": "Link to msg #100"
        }) + "\n")
        f.write(json.dumps({
            "header": {"msgfrom": "A", "msgto": "B", "msgsubject": "S", "msgdate": "01-01-23", "msgtime": "12:00", "confnum": 1, "status": " ", "msgnum": 2},
            "text": "No link"
        }) + "\n")

    try:
        monkeypatch.setattr("sys.argv", ["qwk", test_file, "--has-msg-links", "--oneline"])
        pyqwk.cli.main()

        out, err = capsys.readouterr()
        assert "Successfully processed 1 of 2 messages." in out

        monkeypatch.setattr("sys.argv", ["qwk", test_file, "--oneline-pattern", "{msg_link_count} links: {msg_links}"])
        pyqwk.cli.main()
        out, err = capsys.readouterr()
        assert "1 links: msg #100" in out
        assert "0 links: " in out

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
