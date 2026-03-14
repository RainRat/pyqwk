from unittest.mock import patch
from pyqwk.core import _write_markdown, MessageHeader, ProcessedMessage

def test_write_markdown_output():
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate='01-01-90',
        msgtime='12:00',
        msgto='User',
        msgfrom='Sysop',
        msgsubject='Welcome',
        msgpassword='',
        refnum=None,
        numblocks=1,
        msgflag='',
        confnum=1,
        lognum=1,
        nettag=''
    )
    message = ProcessedMessage(
        text='Hello World',
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        depth=0,
        thread_id='1',
        parent_msgnum=None
    )

    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_markdown([message], None)

        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]

        assert "# QWK Messages" in content
        assert "## Welcome" in content
        assert "- **From:** Sysop" in content
        assert "Hello World" in content
        assert "---" in content

def test_write_markdown_threaded():
    header1 = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='All', msgfrom='Sysop', msgsubject='Topic',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=1, nettag=''
    )
    header2 = MessageHeader(
        status=' ', msgnum=2, msgdate='01-01-90', msgtime='12:05',
        msgto='Sysop', msgfrom='User', msgsubject='Re: Topic',
        msgpassword='', refnum=1, numblocks=1, msgflag='',
        confnum=1, lognum=2, nettag=''
    )

    msg1 = ProcessedMessage(
        text='Parent message', msgnum=1, refnum=None, confnum=1,
        header=header1, depth=0, thread_id='1', parent_msgnum=None
    )
    msg2 = ProcessedMessage(
        text='Child message', msgnum=2, refnum=1, confnum=1,
        header=header2, depth=1, thread_id='1', parent_msgnum=1
    )

    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_markdown([msg1, msg2], None)

        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]

        # Check for child message with blockquote
        assert "> ## Re: Topic" in content
        assert "> - **From:** User" in content
        assert "> Child message" in content
        assert "> ---" in content

        # Ensure parent is NOT blockquoted
        assert "\n## Topic" in content
