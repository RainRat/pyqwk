import os
import logging
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)

def test_organize_by_date_structure(tmp_path):
    output_dir = tmp_path / "output_date"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-23', msgtime='12:34:56',
        msgto='To', msgfrom='From', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    # _parse_qwk_date handles 05-20-23 as MM-DD-YY
    msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='text', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize_by_date=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, logger)

    # Expected path: output_date / 2023 / 05 / 001-00001-subject.txt
    target_file = output_dir / "2023" / "05" / "001-00001-subject.txt"
    assert target_file.exists()

def test_organize_combined_with_attachments(tmp_path):
    output_dir = tmp_path / "output_combined"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-23', msgtime='12:34:56',
        msgto='To', msgfrom='From', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    # Body with a UUE block to trigger attachment extraction
    uue_body = "begin 644 test.txt\n#0V%T\n`\nend\n"
    msg = ParsedMessage(text=uue_body, msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='html', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize=True,
        organize_by_date=True,
        extract_attachments=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {1: "General"})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, logger)

    # relative_sub_path: 001-general / 2023 / 05
    # target_dir: output_combined / 001-general / 2023 / 05
    target_dir = output_dir / "001-general" / "2023" / "05"
    assert target_dir.is_dir()

    target_file = target_dir / "001-00001-subject.html"
    assert target_file.exists()

    # Check for extracted attachment
    attach_file = output_dir / "attachments" / "test.txt"
    assert attach_file.exists()

    # Check if the HTML contains the correct relative path to the attachment
    # depth is 3, so prefix should be ../../../attachments/
    content = target_file.read_text(encoding='utf-8')
    assert 'href="../../../attachments/test.txt"' in content

def test_organize_by_date_only_attachments(tmp_path):
    # Test just organize_by_date=True (depth 2)
    output_dir = tmp_path / "output_date_attach"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-20-23', msgtime='12:34:56',
        msgto='To', msgfrom='From', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    uue_body = "begin 644 test.txt\n#0V%T\n`\nend\n"
    msg = ParsedMessage(text=uue_body, msgnum=1, refnum=None, confnum=1, header=header)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='markdown', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize_by_date=True,
        extract_attachments=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), {})), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, logger)

    target_file = output_dir / "2023" / "05" / "001-00001-subject.md"
    assert target_file.exists()

    # Check for extracted attachment
    attach_file = output_dir / "attachments" / "test.txt"
    assert attach_file.exists()

    # depth is 2 (2023/05), so prefix should be ../../attachments/
    content = target_file.read_text(encoding='utf-8')
    assert '](../../attachments/test.txt)' in content
