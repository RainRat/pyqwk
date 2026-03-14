import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import process_merged_files, ProcessingSettings, ParsedMessage, MessageHeader
import hashlib

def test_deduplication_by_msgnum(tmp_path):
    output_path = tmp_path / "output.txt"
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='text', separator='none',
        output_mode='file', output_path=str(output_path), encoding='cp437',
        unique=True, strip_ansi=False, quiet=True, headers_only=False
    )

    # Message 1
    h1 = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='User1', msgsubject='Subj1', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=100, lognum=1, nettag=''
    )

    msg1 = ParsedMessage(text="Message 1", msgnum=1, refnum=None, confnum=100, header=h1)

    # Message 2 (Duplicate of 1 by msgnum)
    h2 = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='User1', msgsubject='Subj1', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=100, lognum=1, nettag=''
    )

    msg2 = ParsedMessage(text="Message 1 Duplicate", msgnum=1, refnum=None, confnum=100, header=h2)

    # Message 3 (Different msgnum)
    h3 = MessageHeader(
        status=' ', msgnum=2, msgdate='01-01-23', msgtime='12:05',
        msgto='All', msgfrom='User1', msgsubject='Subj2', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=100, lognum=1, nettag=''
    )

    msg3 = ParsedMessage(text="Message 2", msgnum=2, refnum=None, confnum=100, header=h3)

    mock_logger = MagicMock()

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), {})
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.side_effect = [[msg1, msg2, msg3]]

            process_merged_files(['archive.qwk'], settings, mock_logger)

    content = output_path.read_text()
    assert "Message 1" in content
    assert "Message 2" in content
    assert "Message 1 Duplicate" not in content
    # Should only have two messages
    assert content.count("\n") == 2

def test_deduplication_by_content_hash(tmp_path):
    output_path = tmp_path / "output.txt"
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='text', separator='none',
        output_mode='file', output_path=str(output_path), encoding='cp437',
        unique=True, strip_ansi=False, quiet=True, headers_only=False
    )

    # Message 1 (No msgnum)
    h1 = MessageHeader(
        status=' ', msgnum=None, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='User1', msgsubject='Subj1', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=100, lognum=1, nettag=''
    )

    msg1 = ParsedMessage(text="Message Content", msgnum=None, refnum=None, confnum=100, header=h1)

    # Message 2 (Same content, no msgnum)
    h2 = MessageHeader(
        status=' ', msgnum=None, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='User1', msgsubject='Subj1', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=100, lognum=1, nettag=''
    )

    msg2 = ParsedMessage(text="Message Content", msgnum=None, refnum=None, confnum=100, header=h2)

    # Message 3 (Different content)
    h3 = MessageHeader(
        status=' ', msgnum=None, msgdate='01-01-23', msgtime='12:05',
        msgto='All', msgfrom='User1', msgsubject='Subj2', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=100, lognum=1, nettag=''
    )

    msg3 = ParsedMessage(text="Different Content", msgnum=None, refnum=None, confnum=100, header=h3)

    mock_logger = MagicMock()

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), {})
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.side_effect = [[msg1, msg2, msg3]]

            process_merged_files(['archive.qwk'], settings, mock_logger)

    content = output_path.read_text()
    assert content.count("Message Content") == 1
    assert "Different Content" in content
