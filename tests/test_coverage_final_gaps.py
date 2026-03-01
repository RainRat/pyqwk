import os
import json
import logging
import pytest
import hashlib
import html
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from pyqwk.core import (
    show_stats,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    _write_sqlite,
    _write_html,
    _write_markdown,
    _order_messages_by_thread,
    _decode_yenc,
    _write_xml
)
from dataclasses import replace

@pytest.fixture
def logger():
    return logging.getLogger("pyqwk.tests.coverage")

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )

def test_show_stats_with_attachments_reporting(capsys, monkeypatch, default_settings, logger):
    # Coverage for line 2665
    h1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="User1", msgsubject="Subj1",
        msgpassword="", refnum=None, numblocks=2, msgflag=" ",
        confnum=1, lognum=1, nettag="",
    )
    # yEnc attachment
    msg_text = "=ybegin name=test.bin\n*+,/\n=yend\n"
    msgs = [ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=h1)]

    import pyqwk.core as qwk
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced '), {1: "General"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(msgs))

    # Force format to text to see printed output
    settings = replace(default_settings, format='text')
    show_stats(["dummy.qwk"], settings, logger)

    captured = capsys.readouterr()
    assert "1 files detected" in captured.out

def test_xml_attachments_metadata_coverage(message_factory):
    # Coverage for line 1603
    msg = message_factory(1, None, "Test")
    msg.attachments = ["file1.txt", "file2.jpg"]
    msg.text = "Body"

    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_xml([msg], None)
        content = mock_write.call_args[0][0]
        assert "<attachments>" in content
        assert "<attachment>file1.txt</attachment>" in content
        assert "<attachment>file2.jpg</attachment>" in content

def test_html_markdown_search_results_title_coverage(message_factory, default_settings):
    # Coverage for lines 1815 and 1895
    msg = message_factory(1, None, "Test")
    msg.text = "Body"
    settings = replace(default_settings, search_term="needle")

    with patch('pyqwk.core._write_text_output') as mock_write_html:
        _write_html([msg], None, settings=settings)
        content_html = mock_write_html.call_args[0][0]
        # needle is escaped in HTML title
        assert html.escape("Search Results for 'needle'") in content_html

    with patch('pyqwk.core._write_text_output') as mock_write_md:
        _write_markdown([msg], None, settings=settings)
        content_md = mock_write_md.call_args[0][0]
        assert "Search Results for 'needle'" in content_md

def test_individual_files_output_path_not_dir_error(tmp_path, default_settings, logger):
    # Coverage for line 1148
    output_file = tmp_path / "not_a_dir.txt"
    output_file.write_text("I am a file")

    settings = replace(
        default_settings,
        individual_files=True,
        output_mode='file',
        output_path=str(output_file)
    )

    with pytest.raises(ValueError, match="must be a folder"):
        process_merged_files(["dummy.qwk"], settings, logger)

def test_filename_collision_safety_break_coverage(tmp_path, default_settings, logger):
    # Coverage for line 1365
    output_dir = tmp_path / "collision_break"
    output_dir.mkdir()

    exists_count = 0
    def mock_exists(path):
        nonlocal exists_count
        exists_count += 1
        return exists_count <= 110 # Enough to hit break (> 100)

    with patch('os.path.exists', side_effect=mock_exists):
        h = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
            msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
            refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
        )
        msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=h)

        settings = replace(
            default_settings,
            individual_files=True,
            output_mode='file',
            output_path=str(output_dir)
        )

        import pyqwk.core
        with patch('pyqwk.core.load_data', return_value=(bytearray(b'Produced '), {1: "General"})):
            with patch('pyqwk.core.parse_messages', return_value=[msg]):
                with patch('pyqwk.core.open', mock_open()):
                    # Should finish because of the safety break
                    process_merged_files(["dummy.qwk"], settings, logger)

    assert exists_count > 100

def test_decode_yenc_exception_coverage():
    # Coverage for line 215-216
    assert _decode_yenc(None) == b""

def test_eml_serialize_no_from_header_coverage(message_factory):
    # Coverage for line 2062
    from pyqwk.core import _serialize_message_eml

    msg = message_factory(1, None, "Test")
    msg.text = "Body"

    with patch('pyqwk.core._serialize_message_mbox', return_value="Just headers\nBody"):
        result = _serialize_message_eml(msg)
        assert result == "Just headers\nBody"

def test_oneline_html_markdown_text_content_coverage(message_factory, default_settings, logger):
    # Coverage for line 1396
    msg = message_factory(1, None, "Test")
    msg.text = "Body"

    settings = replace(
        default_settings,
        oneline=True,
        format='html',
        output_mode='stdout'
    )

    import pyqwk.core
    with patch('pyqwk.core.load_data', return_value=(bytearray(b'Produced '), {1: "General"})):
        with patch('pyqwk.core.parse_messages', return_value=[msg]):
            with patch('pyqwk.core._write_html') as mock_html:
                process_merged_files(["dummy.qwk"], settings, logger)
                messages = mock_html.call_args[0][0]
                assert "Body" in messages[0].text

def test_html_markdown_attachments_no_prefix_coverage(message_factory, default_settings):
    # Coverage for lines 1701 and 1774
    msg = message_factory(1, None, "Test")
    msg.attachments = ["file1.txt"]
    msg.text = "Body"

    # settings with extract_attachments=False (default)

    with patch('pyqwk.core._write_text_output') as mock_write_html:
        _write_html([msg], None, settings=default_settings)
        content_html = mock_write_html.call_args[0][0]
        # Should contain filename but not as a link with attachments/ prefix
        assert "file1.txt" in content_html
        assert 'href="attachments/' not in content_html

    with patch('pyqwk.core._write_text_output') as mock_write_md:
        _write_markdown([msg], None, settings=default_settings)
        content_md = mock_write_md.call_args[0][0]
        assert "file1.txt" in content_md
        assert "](attachments/" not in content_md
