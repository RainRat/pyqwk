import pytest
from unittest.mock import patch
from pyqwk.core import _write_markdown, _write_html, MessageHeader, ProcessedMessage, ProcessingSettings

def create_test_message(attachments=None):
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
    return ProcessedMessage(
        text='Hello World',
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        depth=0,
        thread_id='1',
        parent_msgnum=None,
        confname='General',
        bbs_name='MyBBS',
        source_file='archive.qwk',
        attachments=attachments
    )

def test_enhanced_markdown_metadata():
    message = create_test_message()
    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_markdown([message], None)
        content = mock_write.call_args[0][0]

        assert "- **Conference:** General (1)" in content
        assert "- **BBS:** MyBBS" in content
        assert "- **Source:** archive.qwk" in content

def test_enhanced_markdown_attachments():
    message = create_test_message(attachments=['test.jpg'])
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format='markdown',
        separator='none', output_mode='stdout', output_path=None,
        encoding='cp437', extract_attachments=True
    )

    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_markdown([message], None, settings=settings)
        content = mock_write.call_args[0][0]

        assert "- **Attachments:** [test.jpg](attachments/test.jpg)" in content

def test_enhanced_html_metadata():
    message = create_test_message()
    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_html([message], None)
        content = mock_write.call_args[0][0]

        assert "<strong>Conference:</strong> General (1)" in content
        assert "<strong>BBS:</strong> MyBBS" in content
        assert "<strong>Source:</strong> archive.qwk" in content

def test_enhanced_html_attachments():
    message = create_test_message(attachments=['test.jpg'])
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format='html',
        separator='none', output_mode='stdout', output_path=None,
        encoding='cp437', extract_attachments=True
    )

    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_html([message], None, settings=settings)
        content = mock_write.call_args[0][0]

        assert '<strong>Attachments:</strong> <a href="attachments/test.jpg">test.jpg</a>' in content
