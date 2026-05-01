import datetime
import email
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    _message_from_email,
    _generate_safe_filename,
    _parse_qwk_date,
    MessageHeader,
    ProcessingSettings,
    ParsedMessage,
    _parse_markdown_messages,
    load_data,
    matches_filters,
    process_merged_files,
    _write_text,
    BBSInfo,
    ConferenceMap
)

def test_message_from_email_multipart_no_text_plain():
    msg = email.message.EmailMessage()
    msg['From'] = 'alice@example.com'
    msg['To'] = 'bob@example.com'
    msg['Subject'] = 'No Text'
    msg.add_attachment(b'fake image data', maintype='image', subtype='png')

    parsed = _message_from_email(msg)
    assert parsed.text == ""

def test_message_from_email_invalid_date_fallback():
    msg = email.message.EmailMessage()
    msg['Date'] = 'Invalid Date String'
    parsed = _message_from_email(msg)
    assert parsed.header.msgdate == "01-01-70"
    assert parsed.header.msgtime == "00:00"

def test_generate_safe_filename_append_extension():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, None, " ", 1, 0, "")
    msg = ParsedMessage("", 1, None, 1, header)
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='file',
        output_path='.', encoding='cp437', filename_pattern="custom_name"
    )
    filename = _generate_safe_filename(msg, settings, 1)
    assert filename == "custom_name.txt"

def test_parse_qwk_date_iso_format():
    dt = _parse_qwk_date("2024-05-20T15:30:00", "")
    assert dt == datetime.datetime(2024, 5, 20, 15, 30, 0)

def test_parse_qwk_date_sliding_window_1900s():
    dt = _parse_qwk_date("01-01-85", "12:00")
    assert dt.year == 1985

def test_message_header_format_oneline_highlight():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "Recipient", "Author", "Subject", "", None, None, " ", 1, 0, "")
    line = header.format_oneline({}, use_colors=True, highlight_term="Author")
    assert "\x1b[7mAuthor\x1b[0m" in line

def test_markdown_import_complex_chunking(tmp_path):
    content = (
        "Archive Title\n"
        "---\n"
        "## First Message\n"
        "- **Date:** 01-01-24\n"
        "\n"
        "Body 1\n"
        "---\n"
        "Extra noise between messages\n"
        "---\n"
        "## Second Message\n"
        "\n"
        "Body 2\n"
    )
    md_file = tmp_path / "test.md"
    md_file.write_text(content)

    messages = _parse_markdown_messages(str(md_file))
    assert len(messages) == 2
    assert messages[0].header.msgsubject == "First Message"
    # The chunker appends non-header chunks to the current message
    assert "Extra noise" in messages[0].text

def test_markdown_import_empty_date_parts(tmp_path):
    content = "## Subj\n- **Date:** \n\nBody"
    md_file = tmp_path / "test.md"
    md_file.write_text(content)
    messages = _parse_markdown_messages(str(md_file))
    assert messages[0].header.msgdate == "01-01-70"

def test_load_data_messages_dat_case_insensitive_control(tmp_path):
    messages_dat = tmp_path / "MESSAGES.DAT"
    messages_dat.write_bytes(b'Produced ' + b' ' * 119)
    control_dat = tmp_path / "control.dat" # Lowercase
    control_dat.write_bytes(b'BBS Name\n' + b'Line\n' * 20)

    with patch('pyqwk.core._parse_control_dat') as mock_parse:
        mock_parse.return_value = ConferenceMap()
        load_data(str(messages_dat), MagicMock())
        assert mock_parse.called

def test_matches_filters_has_attachments_no_text():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, None, " ", 1, 0, "")
    msg = ParsedMessage(text="", msgnum=1, refnum=None, confnum=1, header=header)
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437', has_attachments=True
    )
    assert matches_filters(msg, settings, set()) is False

def test_process_merged_files_sort_reversal_only(tmp_path):
    output_path = tmp_path / "out.txt"
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='text', separator='none',
        output_mode='file', output_path=str(output_path), encoding='cp437',
        sort=None, reverse=True
    )

    h1 = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj1", "", None, None, " ", 1, 0, "")
    m1 = ParsedMessage("Msg1", 1, None, 1, h1)
    h2 = MessageHeader(" ", 2, "01-01-24", "12:01", "To", "From", "Subj2", "", None, None, " ", 1, 0, "")
    m2 = ParsedMessage("Msg2", 2, None, 1, h2)

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), ConferenceMap())
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.return_value = iter([m1, m2])
            process_merged_files(['fake.qwk'], settings, MagicMock())

    content = output_path.read_text().replace('\r\n', '\n')
    assert content == "Msg2\nMsg1\n"

def test_write_text_include_toc_minimal_bbs_info(tmp_path):
    output_path = tmp_path / "out.txt"
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, merge=True,
        binaries_removal=False, redact_pii=False, format='text', separator='none',
        output_mode='file', output_path=str(output_path), encoding='cp437',
        include_toc=True
    )

    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, None, " ", 1, 0, "")
    msg = ParsedMessage("Body", 1, None, 1, header, confname="General")
    bbs_info = BBSInfo(name="MyBBS") # Other fields empty

    _write_text([msg], str(output_path), 'cp437', settings, bbs_info)
    content = output_path.read_text()
    assert "MyBBS Archive" in content
    assert "SysOp:" not in content
