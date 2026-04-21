import os
import xml.etree.ElementTree as ET
import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, write_messages, BBSInfo

def test_rss_export(tmp_path):
    # Setup sample data with all required MessageHeader fields
    header = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="01-01-24",
        msgtime="12:00:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Hello RSS",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(
        text="This is a test message for RSS export.",
        msgnum=101,
        refnum=0,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="The BBS",
        bbs_id="THEBBS",
    )
    messages = [msg]

    settings = ProcessingSettings(
        verbose=False,
        private=False,
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
        output_path=str(tmp_path / "test.rss"),
        encoding='cp437'
    )
    bbs_info = BBSInfo(name="The BBS", bbs_id="THEBBS")

    # Write RSS
    write_messages(messages, settings.output_path, settings, bbs_info=bbs_info)

    # Verify file existence
    rss_file = tmp_path / "test.rss"
    assert rss_file.exists()

    # Parse and verify content
    tree = ET.parse(rss_file)
    root = tree.getroot()

    assert root.tag == 'rss'
    assert root.attrib['version'] == '2.0'

    channel = root.find('channel')
    assert channel is not None
    assert channel.find('title').text == "The BBS Archive"

    item = channel.find('item')
    assert item is not None
    assert item.find('title').text == "Hello RSS"
    assert item.find('author').text == "Alice"
    assert item.find('description').text == "This is a test message for RSS export."
    assert item.find('category').text == "General"
    assert item.find('guid').text == "1.101@qwk"

    # Check pubDate format (RFC 822)
    pub_date = item.find('pubDate').text
    # Should look like: Mon, 01 Jan 2024 12:00:00 -0000 (or similar)
    assert "2024" in pub_date
    assert "Jan" in pub_date

if __name__ == "__main__":
    pytest.main([__file__])
