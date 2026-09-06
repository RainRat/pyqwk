import json
import logging
import pytest
from unittest.mock import patch

from pyqwk.core import (
    ConferenceMap,
    ProcessingSettings,
    show_list_msg_links,
)
from pyqwk.cli import main


def make_settings(fmt="json", output_path=None):
    return ProcessingSettings(
        verbose=False,
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
        output_mode="file" if output_path else "stdout",
        output_path=output_path,
        encoding="cp437",
        quiet=True,
    )


@pytest.fixture
def sample_messages_with_msg_links(message_factory):
    msg1 = message_factory(101, 0, "Discussion on Retro Tech")
    msg1.text = "Check out msg #42 for details on the new BBS setup."
    msg1.header.msgfrom = "Alice"
    msg1.header.msgdate = "01-15-2024"
    msg1.header.msgtime = "10:00"

    msg2 = message_factory(102, 101, "Re: Discussion on Retro Tech")
    msg2.text = "Also see message 42 and msg#99 for archived logs."
    msg2.header.msgfrom = "Bob"
    msg2.header.msgdate = "01-16-2024"
    msg2.header.msgtime = "11:30"

    board = ConferenceMap()
    board[1] = "General"
    return [msg1, msg2], board


def test_show_list_msg_links_formats(mocker, tmp_path, sample_messages_with_msg_links):
    msgs, board = sample_messages_with_msg_links
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board))
    logger = logging.getLogger("test")

    # Test Text Output
    settings_text = make_settings(fmt="text")
    show_list_msg_links(["dummy.qwk"], settings_text, logger)

    # Test JSON Output
    json_path = str(tmp_path / "msg_links.json")
    settings_json = make_settings(fmt="json", output_path=json_path)
    show_list_msg_links(["dummy.qwk"], settings_json, logger)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 3
        msg42 = next(item for item in data if item["msg_link"].lower() in ("msg #42", "message 42"))
        assert msg42["message_count"] == 1

    # Test HTML Output
    html_path = str(tmp_path / "msg_links.html")
    settings_html = make_settings(fmt="html", output_path=html_path)
    show_list_msg_links(["dummy.qwk"], settings_html, logger)
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        assert "<h1>Extracted Message Links</h1>" in html_content
        assert "msg #42" in html_content or "message 42" in html_content

    # Test Markdown Output
    md_path = str(tmp_path / "msg_links.md")
    settings_md = make_settings(fmt="markdown", output_path=md_path)
    show_list_msg_links(["dummy.qwk"], settings_md, logger)
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
        assert "# Extracted Message Links" in md_content

    # Test CSV Output
    csv_path = str(tmp_path / "msg_links.csv")
    settings_csv = make_settings(fmt="csv", output_path=csv_path)
    show_list_msg_links(["dummy.qwk"], settings_csv, logger)
    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()
        assert "msg_link,message_count,authors_count" in csv_content


def test_show_list_msg_links_empty(mocker, message_factory):
    msg_no_links = message_factory(1, 0, "Subject")
    msg_no_links.text = "Hello world without references."
    msg_no_links.header.msgfrom = "Charlie"
    board = ConferenceMap()

    mocker.patch("pyqwk.core.load_data", return_value=([msg_no_links], board))
    logger = logging.getLogger("test")

    settings = make_settings(fmt="text")
    show_list_msg_links(["dummy.qwk"], settings, logger)


def test_cli_list_msg_links(mocker, tmp_path, sample_messages_with_msg_links):
    msgs, board = sample_messages_with_msg_links
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board))
    mocker.patch("sys.argv", ["qwk", "dummy.qwk", "--list-msg-links"])

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
