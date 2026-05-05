import xml.etree.ElementTree as ET
import logging
from pyqwk.core import (
    _parse_rss_messages,
    _write_rss,
    _parse_html_messages,
    _order_messages_by_thread,
    MessageHeader,
    ParsedMessage,
    BBSInfo,
)


def test_parse_rss_messages_malformed_guid():
    xml_data = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    <channel>
        <item>
            <title>Malformed GUID</title>
            <guid>too.many.dots.here@qwk</guid>
        </item>
        <item>
            <title>No dots</title>
            <guid>nodots@qwk</guid>
        </item>
    </channel>
    </rss>
    """
    root = ET.fromstring(xml_data)
    messages = _parse_rss_messages(root)
    assert len(messages) == 2
    assert messages[0].confnum == 0
    assert messages[0].msgnum is None
    assert messages[1].confnum == 0
    assert messages[1].msgnum is None


def test_write_rss_no_bbs_info(tmp_path):
    header = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header)
    rss_file = tmp_path / "test_no_bbs.rss"

    _write_rss([msg], str(rss_file), bbs_info=None)
    with open(rss_file, "r") as f:
        content = f.read()
        assert "<title>QWK Message Archive</title>" in content


def test_write_rss_empty_bbs_name(tmp_path):
    header = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header)
    rss_file = tmp_path / "test_empty_bbs.rss"

    _write_rss([msg], str(rss_file), bbs_info=BBSInfo(name=""))
    with open(rss_file, "r") as f:
        content = f.read()
        assert "<title>QWK Message Archive</title>" in content


def test_write_rss_no_confname(tmp_path):
    header = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header, confname=None)
    rss_file = tmp_path / "test_no_conf.rss"

    _write_rss([msg], str(rss_file))
    with open(rss_file, "r") as f:
        content = f.read()
        assert "<category>" not in content


def test_parse_html_messages_non_reply_div(tmp_path):
    html_content = """
    <div class="other">
        <div class="message" id="msg-0">
            <div class="header"><strong>Number:</strong> 1</div>
            <pre class="body">Body</pre>
        </div>
    </div>
    """
    html_file = tmp_path / "other_div.html"
    html_file.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 1
    assert messages[0].depth == 0


def test_order_messages_by_thread_cycle_reported_branch(caplog):
    def make_msg(num, ref):
        h = MessageHeader(
            status=" ",
            msgnum=num,
            msgdate="01-01-23",
            msgtime="10:00",
            msgto="All",
            msgfrom="User",
            msgsubject="Cycle",
            msgpassword="",
            refnum=ref,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=num,
            nettag="",
        )
        return ParsedMessage(text=str(num), msgnum=num, refnum=ref, confnum=1, header=h)

    messages = [make_msg(1, 2), make_msg(2, 1)]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(messages)

    assert any("Circular reference detected" in r.message for r in caplog.records)


def test_parse_rss_messages_invalid_guid_parts():
    xml_data = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><item><guid>onlyonepart@qwk</guid></item></channel></rss>
    """
    root = ET.fromstring(xml_data)
    messages = _parse_rss_messages(root)
    assert len(messages) == 1
    assert messages[0].confnum == 0
    assert messages[0].msgnum is None
