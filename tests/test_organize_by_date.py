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

    # Mocking data with a specific date
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='10-27-23', msgtime='14:30',
        msgto='Alice', msgfrom='Bob', msgsubject='Hello',
        msgpassword='', refnum=None, numblocks=2, msgflag='',
        confnum=1, lognum=0, nettag=''
    )
    # The message body contains a UUE block so it has an attachment to extract
    msg_text = "Hello\nbegin 644 test.txt\nM1&AI<R!I<R!A('1E<W0@96YE;V1I;F<@=&5X=.\nend\n"
    msg = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header)

    board_dict = {1: "General"}

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='html', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize_by_date=True,
        extract_attachments=True,
        quiet=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), board_dict)), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, logger)

    # Check if YYYY/MM structure was created
    year_month_dir = output_dir / "2023" / "10"
    assert year_month_dir.is_dir()

    # Check if message file exists
    msg_files = list(year_month_dir.glob("*.html"))
    assert len(msg_files) == 1

    # Check if attachment was extracted to the root attachments folder
    attach_dir = output_dir / "attachments"
    assert attach_dir.is_dir()
    assert (attach_dir / "test.txt").exists()

    # Verify attachment_prefix in the HTML file
    # It should be "../../attachments/" (2 levels deep)
    content = msg_files[0].read_text()
    assert 'href="../../attachments/test.txt"' in content

def test_organize_by_conf_and_date(tmp_path):
    output_dir = tmp_path / "output_nested"
    output_dir.mkdir()

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='05-15-95', msgtime='09:00',
        msgto='Alice', msgfrom='Bob', msgsubject='Old School',
        msgpassword='', refnum=None, numblocks=2, msgflag='',
        confnum=42, lognum=0, nettag=''
    )
    msg_text = "Old message\nbegin 644 old.txt\nM1&%T80==\nend\n"
    msg = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=42, header=header)

    board_dict = {42: "Retro"}

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format='markdown', separator='none', output_mode='file',
        output_path=str(output_dir), encoding='cp437',
        organize=True,
        organize_by_date=True,
        extract_attachments=True,
        quiet=True
    )

    logger = MagicMock()

    with patch('pyqwk.core.load_data', return_value=(bytearray(), board_dict)), \
         patch('pyqwk.core.parse_messages', return_value=[msg]):
        process_merged_files(['dummy.qwk'], settings, logger)

    # Check structure: Conf/YYYY/MM
    nested_dir = output_dir / "042-retro" / "1995" / "05"
    assert nested_dir.is_dir()

    msg_files = list(nested_dir.glob("*.md"))
    assert len(msg_files) == 1

    # Check attachment prefix: should be "../../../attachments/" (3 levels deep)
    content = msg_files[0].read_text()
    assert '](../../../attachments/old.txt)' in content
