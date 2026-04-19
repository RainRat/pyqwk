import os
import xml.etree.ElementTree as ET
import logging
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    _write_rss,
    BBSInfo,
    ConferenceMap
)

def test_write_rss(tmp_path):
    output_path = os.path.join(tmp_path, "test.rss")

    header = MessageHeader(
        status=" ",
        msgnum=123,
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
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="TestBBS"
    )

    bbs_info = BBSInfo(name="TestBBS")
    board_dict = ConferenceMap({1: "General"})
    board_dict.bbs_info = bbs_info

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format='rss',
        separator='none', output_mode='file', output_path=output_path,
        encoding='utf-8'
    )

    _write_rss([msg], output_path, settings=settings, bbs_info=bbs_info, board_dict=board_dict)

    assert os.path.exists(output_path)

    tree = ET.parse(output_path)
    root = tree.getroot()

    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"

    channel = root.find("channel")
    assert channel is not None
    assert channel.find("title").text == "TestBBS Feed"

    items = channel.findall("item")
    assert len(items) == 1

    item = items[0]
    assert item.find("title").text == "[General] Test Subject"
    assert item.find("description").text == "Hello world\nThis is a test."
    assert item.find("author").text == "Author"
    assert item.find("guid").text == "1.123@qwk"
