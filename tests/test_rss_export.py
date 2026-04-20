import os
import xml.etree.ElementTree as ET
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, write_messages, BBSInfo

def test_rss_export(tmp_path):
    output_path = tmp_path / "test.rss"

    msg1 = ParsedMessage(
        text="Hello World",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=MessageHeader(
            status=" ",
            msgnum=1,
            msgdate="01-01-24",
            msgtime="12:00",
            msgto="Everyone",
            msgfrom="Sysop",
            msgsubject="Test Message",
            msgpassword="",
            refnum=None,
            numblocks=None,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        ),
        confname="General",
        bbs_name="Test BBS"
    )

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
        format='rss',
        separator='none',
        output_mode='file',
        output_path=str(output_path),
        encoding='utf-8',
    )

    bbs_info = BBSInfo(name="Test BBS")

    write_messages([msg1], str(output_path), settings, bbs_info=bbs_info)

    assert output_path.exists()

    tree = ET.parse(output_path)
    root = tree.getroot()

    assert root.tag == 'rss'
    assert root.attrib['version'] == '2.0'

    channel = root.find('channel')
    assert channel is not None
    assert channel.find('title').text == "Test BBS Archive"

    items = channel.findall('item')
    assert len(items) == 1

    item = items[0]
    assert item.find('title').text == "Test Message"
    assert item.find('author').text == "Sysop"
    assert item.find('description').text == "Hello World"
    # Guid should be present
    assert item.find('guid').text == "1.1@qwk"
