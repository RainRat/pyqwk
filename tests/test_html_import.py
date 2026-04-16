import os
import logging
from pyqwk.core import (
    ParsedMessage, MessageHeader, process_merged_files, ProcessingSettings,
    load_data, expand_paths
)

def test_html_import_roundtrip(tmp_path):
    """Test that messages exported to HTML can be imported back correctly."""
    output_html = tmp_path / "test.html"

    # Setup test messages
    h1 = MessageHeader(
        status=' ', msgnum=101, msgdate='05-20-23', msgtime='14:30',
        msgto='Alice', msgfrom='Bob', msgsubject='Hello HTML', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    msg1 = ParsedMessage(
        text="This is a test message body.",
        msgnum=101, refnum=None, confnum=1, header=h1,
        confname="General", bbs_name="TestBBS", source_file="original.qwk"
    )

    h2 = MessageHeader(
        status=' ', msgnum=102, msgdate='05-20-23', msgtime='14:35',
        msgto='Bob', msgfrom='Alice', msgsubject='Re: Hello HTML', msgpassword='',
        refnum=101, numblocks=1, msgflag='', confnum=1, lognum=2, nettag=''
    )
    # Child message for threading
    msg2 = ParsedMessage(
        text="This is a reply.",
        msgnum=102, refnum=101, confnum=1, header=h2,
        confname="General", bbs_name="TestBBS", source_file="original.qwk",
        depth=1
    )

    messages = [msg1, msg2]

    # 1. Export to HTML
    settings_export = ProcessingSettings(
        verbose=True, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=True, merge=True,
        binaries_removal=False, redact_pii=False, format='html', separator='none',
        output_mode='file', output_path=str(output_html), encoding='utf-8',
        include_toc=True, quiet=True
    )

    import unittest.mock
    mock_logger = unittest.mock.MagicMock()

    # We need to mock load_data to return our test messages during process_merged_files
    with unittest.mock.patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (messages, {1: "General"})
        process_merged_files(['fake.qwk'], settings_export, mock_logger)

    assert os.path.exists(output_html)

    # 2. Import back from HTML
    logger = logging.getLogger("test")
    imported_messages, board_dict = load_data(str(output_html), logger)

    assert len(imported_messages) == 2

    # Check Message 1
    im1 = imported_messages[0]
    assert im1.msgnum == 101
    assert im1.header.msgfrom == "Bob"
    assert im1.header.msgto == "Alice"
    assert im1.header.msgsubject == "Hello HTML"
    assert im1.confnum == 1
    assert im1.confname == "General"
    assert im1.bbs_name == "TestBBS"
    assert "test message body" in im1.text
    assert im1.depth == 0

    # Check Message 2
    im2 = imported_messages[1]
    assert im2.msgnum == 102
    assert im2.header.msgfrom == "Alice"
    assert im2.header.msgto == "Bob"
    assert im2.header.msgsubject == "Re: Hello HTML"
    assert im2.depth == 1
    assert "reply" in im2.text

def test_html_individual_files_import(tmp_path):
    """Test importing from a directory of individual HTML message files."""
    output_dir = tmp_path / "individual"
    output_dir.mkdir()

    h1 = MessageHeader(
        status=' ', msgnum=50, msgdate='01-01-23', msgtime='10:00',
        msgto='All', msgfrom='Sysop', msgsubject='Welcome', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=0, lognum=1, nettag=''
    )
    msg1 = ParsedMessage(
        text="Welcome to the BBS",
        msgnum=50, refnum=None, confnum=0, header=h1,
        confname="Public", bbs_name="MyBBS"
    )

    settings_export = ProcessingSettings(
        verbose=True, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, format='html', separator='none',
        output_mode='file', output_path=str(output_dir), encoding='utf-8',
        quiet=True
    )

    import unittest.mock
    mock_logger = unittest.mock.MagicMock()

    with unittest.mock.patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = ([msg1], {0: "Public"})
        process_merged_files(['fake.qwk'], settings_export, mock_logger)

    # Find the generated HTML file (ignoring index.html)
    html_files = [f for f in os.listdir(output_dir) if f.endswith(".html") and f != "index.html"]
    assert len(html_files) == 1
    msg_file_path = output_dir / html_files[0]

    # Import it back
    imported, _ = load_data(str(msg_file_path), mock_logger)
    assert len(imported) == 1
    assert imported[0].msgnum == 50
    assert imported[0].header.msgsubject == "Welcome"
    assert imported[0].bbs_name == "MyBBS"
    assert "Welcome to the BBS" in imported[0].text

def test_expand_paths_html():
    """Verify that expand_paths finds .html and .htm files."""
    files = expand_paths(["tests"])
    # This should be true now, but let's test with a controlled environment if possible
    # For simplicity, we just check if any .html file would be found in a mock structure
    import unittest.mock
    with unittest.mock.patch('os.path.isdir', return_value=True):
        with unittest.mock.patch('os.walk') as mock_walk:
            mock_walk.return_value = [
                ('/fake', ('subdir',), ('msg1.html', 'msg2.htm', 'other.txt')),
            ]
            found = expand_paths(['/fake'])
            assert '/fake/msg1.html' in found
            assert '/fake/msg2.htm' in found
            assert '/fake/other.txt' not in found
