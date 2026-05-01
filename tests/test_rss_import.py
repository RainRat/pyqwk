import logging
from pyqwk.core import load_data

def test_rss_roundtrip(tmp_path):
    # Create a dummy message
    from pyqwk.core import MessageHeader, ParsedMessage, _write_rss

    header = MessageHeader(
        status=' ',
        msgnum=123,
        msgdate='05-20-24',
        msgtime='14:30',
        msgto='All',
        msgfrom='Tester',
        msgsubject='Test RSS',
        msgpassword='',
        refnum=None,
        numblocks=None,
        msgflag=' ',
        confnum=10,
        lognum=0,
        nettag=' ',
    )

    msg = ParsedMessage(
        text='This is a test message for RSS roundtrip.',
        msgnum=123,
        refnum=None,
        confnum=10,
        header=header,
        confname='Test Conference',
        bbs_name='Test BBS',
    )

    from pyqwk.core import BBSInfo
    rss_file = tmp_path / "test.rss"
    _write_rss([msg], str(rss_file), bbs_info=BBSInfo(name='Test BBS'))

    # Load it back
    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(rss_file), logger)

    assert len(messages) == 1
    loaded_msg = messages[0]

    assert loaded_msg.text == msg.text
    assert loaded_msg.msgnum == msg.msgnum
    assert loaded_msg.confnum == msg.confnum
    assert loaded_msg.header.msgfrom.strip() == msg.header.msgfrom.strip()
    assert loaded_msg.header.msgsubject.strip() == msg.header.msgsubject.strip()
    # RSS format uses RFC 822 for dates, so precision might differ but should be close
    assert loaded_msg.header.msgdate == msg.header.msgdate
    assert loaded_msg.header.msgtime == msg.header.msgtime
    assert loaded_msg.bbs_name == 'Test BBS'
    assert loaded_msg.confname == 'Test Conference'

def test_rss_import_from_cli_generated_file(tmp_path):
    # Use an actual test archive to generate RSS and read it back
    import subprocess
    import sys

    input_zip = "testdata/test1_qwk.zip"
    rss_output = tmp_path / "output.rss"

    # Run cli to generate rss
    subprocess.run([sys.executable, "qwk.py", input_zip, "--format", "rss", "-o", str(rss_output)], check=True)

    # Read it back with load_data
    logger = logging.getLogger("test")
    messages, board_dict = load_data(str(rss_output), logger)

    assert len(messages) > 0
    assert messages[0].header.msgsubject.startswith("Re: Fujitsu hard drive")
    assert messages[0].bbs_name == "Benden Weyr, Pern, Sagittarius Sector"
