import os
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)

def test_organize_subfolders(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Mocking data
    header1 = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='Alice', msgfrom='Bob', msgsubject='Hello',
        msgpassword='', refnum=None, numblocks=2, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    msg1 = ParsedMessage(text="Hello world", msgnum=1, refnum=None, confnum=1, header=header1)

    header2 = MessageHeader(
        status=' ', msgnum=2, msgdate='01-01-23', msgtime='12:05',
        msgto='Bob', msgfrom='Alice', msgsubject='Re: Hello',
        msgpassword='', refnum=1, numblocks=2, msgflag='',
        confnum=2, lognum=0, nettag=''
    )
    msg2 = ParsedMessage(text="Reply here", msgnum=2, refnum=1, confnum=2, header=header2)

    board_dict = {1: "General Chat", 2: "Tech Talk"}

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='text', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), board_dict)), \
         patch('pyqwk.core.parse_messages', return_value=[msg1, msg2]):
        process_merged_files(['dummy.qwk'], settings, logger)

    # Check if subfolders were created
    conf1_dir = output_dir / "001-general_chat"
    conf2_dir = output_dir / "002-tech_talk"

    assert conf1_dir.is_dir()
    assert conf2_dir.is_dir()

    # Check if files are in subfolders
    files1 = list(conf1_dir.glob("*.txt"))
    files2 = list(conf2_dir.glob("*.txt"))

    assert len(files1) == 1
    assert len(files2) == 1
    assert "001-00001-hello.txt" in files1[0].name
    assert "002-00002-re_hello.txt" in files2[0].name

def test_organize_unknown_conference(tmp_path):
    output_dir = tmp_path / "output_unknown"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=10, msgdate='01-01-23', msgtime='12:00',
        msgto='Alice', msgfrom='Bob', msgsubject='Secret',
        msgpassword='', refnum=None, numblocks=2, msgflag='',
        confnum=999, lognum=0, nettag=''
    )
    msg = ParsedMessage(text="Hello", msgnum=10, refnum=None, confnum=999, header=header)

    board_dict = {} # No conference names

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='text', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), board_dict)), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, logger)

    conf_dir = output_dir / "999-unknown"
    assert conf_dir.is_dir()
    assert (conf_dir / "999-00010-secret.txt").exists()
