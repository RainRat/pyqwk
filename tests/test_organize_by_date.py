import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    matches_filters,
)

def _make_settings(**kwargs):
    defaults = dict(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='text', separator='none', output_mode='file',
        output_path=None, encoding='cp437',
        organize=False, organize_by_date=False,
        extract_attachments=False, include_toc=True
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)

def test_organize_by_date_only(tmp_path):
    output_dir = tmp_path / "output_date"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = _make_settings(output_path=str(output_dir), organize_by_date=True)

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # Expected path: output_date/2024/05/001-00001-test.txt
    expected_dir = output_dir / "2024" / "05"
    assert expected_dir.is_dir()
    assert (expected_dir / "001-00001-test.txt").exists()

def test_organize_by_conf_and_date(tmp_path):
    output_dir = tmp_path / "output_both"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = _make_settings(output_path=str(output_dir), organize=True, organize_by_date=True)

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # Expected path: output_both/001-general/2024/05/001-00001-test.txt
    expected_dir = output_dir / "001-general" / "2024" / "05"
    assert expected_dir.is_dir()
    assert (expected_dir / "001-00001-test.txt").exists()

def test_relative_attachment_prefix_nested(tmp_path):
    output_dir = tmp_path / "output_attach"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    # Message with binary attachment
    msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
    msg = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    # Use HTML format to see the relative prefix in <a href="...">
    settings = _make_settings(
        output_path=str(output_dir),
        organize=True,
        organize_by_date=True,
        extract_attachments=True,
        format='html'
    )

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # Depth is 3 (conf, year, month), so prefix should be ../../../attachments/
    expected_file = output_dir / "001-general" / "2024" / "05" / "001-00001-test.html"
    assert expected_file.exists()

    with open(expected_file, 'r') as f:
        content = f.read()
        assert 'href="../../../attachments/file.txt"' in content

def test_relative_attachment_prefix_date_only(tmp_path):
    output_dir = tmp_path / "output_attach_date"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
    msg = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = _make_settings(
        output_path=str(output_dir),
        organize_by_date=True,
        extract_attachments=True,
        format='markdown'
    )

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # Depth is 2 (year, month), so prefix should be ../../attachments/
    expected_file = output_dir / "2024" / "05" / "001-00001-test.md"
    assert expected_file.exists()

    with open(expected_file, 'r') as f:
        content = f.read()
        assert '(../../attachments/file.txt)' in content

def test_organize_by_date_dry_run(tmp_path):
    output_dir = tmp_path / "output_dry"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = _make_settings(output_path=str(output_dir), organize_by_date=True, dry_run=True)

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # In dry run, directories should NOT be created
    expected_dir = output_dir / "2024" / "05"
    assert not expected_dir.exists()

def test_extract_attachments_dry_run(tmp_path):
    output_dir = tmp_path / "output_attach_dry"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
    msg = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = _make_settings(
        output_path=str(output_dir),
        extract_attachments=True,
        dry_run=True
    )

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # Attachments directory should NOT be created
    attach_dir = output_dir / "attachments"
    assert not attach_dir.exists()

def test_extract_attachments_none_found(tmp_path):
    output_dir = tmp_path / "output_no_attach"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    # Message with NO binary attachment
    msg = ParsedMessage(text="Just some text", msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = _make_settings(
        output_path=str(output_dir),
        extract_attachments=True
    )

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, MagicMock())

    # Attachments directory should NOT be created if none found
    attach_dir = output_dir / "attachments"
    assert not attach_dir.exists()

def test_matches_filters_password_protected():
    header = MessageHeader(
        status='%', # Password protected
        msgnum=1, msgdate='05-20-24', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=header)
    settings = _make_settings(private=True)

    assert matches_filters(msg, settings, set()) is False
