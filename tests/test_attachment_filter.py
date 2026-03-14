import json
import io
from pyqwk.core import (
    MessageHeader, ParsedMessage, ProcessingSettings,
    matches_filters, process_merged_files, _message_to_dict
)
from unittest.mock import MagicMock

def test_attachment_filter_logic():
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )

    # Message with attachment
    msg_with_attach = ParsedMessage(
        text="begin 644 file.txt\n#0V%T\n`\nend\n",
        msgnum=1, refnum=None, confnum=1, header=header
    )

    # Message without attachment
    msg_no_attach = ParsedMessage(
        text="Hello world",
        msgnum=2, refnum=None, confnum=1, header=header
    )

    settings_filter_on = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437',
        has_attachments=True
    )

    settings_filter_off = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437',
        has_attachments=False
    )

    # Test filtering
    assert matches_filters(msg_with_attach, settings_filter_on, set()) is True
    assert msg_with_attach.attachments == ["file.txt"]

    assert matches_filters(msg_no_attach, settings_filter_on, set()) is False

    assert matches_filters(msg_with_attach, settings_filter_off, set()) is True
    assert matches_filters(msg_no_attach, settings_filter_off, set()) is True

def test_attachment_metadata_in_json():
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    message = ParsedMessage(
        text="begin 644 file.txt\n#0V%T\n`\nend\n",
        msgnum=1, refnum=None, confnum=1, header=header,
        attachments=["file.txt"]
    )

    d = _message_to_dict(message)
    assert "attachments" in d
    assert d["attachments"] == ["file.txt"]

    json_out = json.dumps(d)
    assert '"attachments": ["file.txt"]' in json_out

def test_attachment_metadata_in_csv():
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    message = ParsedMessage(
        text="Text", msgnum=1, refnum=None, confnum=1, header=header,
        attachments=["file1.zip", "file2.jpg"]
    )

    import pyqwk.core
    output = io.StringIO()
    # We need to call _write_csv but it writes to a file if output_path is set.
    # We can mock _write_text_output to capture it.

    original_write_text_output = pyqwk.core._write_text_output
    captured_content = []
    pyqwk.core._write_text_output = lambda content, *a, **k: captured_content.append(content)

    try:
        pyqwk.core._write_csv([message], None)
        csv_data = captured_content[0]
        assert "attachments" in csv_data
        assert "file1.zip;file2.jpg" in csv_data
    finally:
        pyqwk.core._write_text_output = original_write_text_output

def test_has_attachments_cli_integration(monkeypatch, capsys):
    # Mock data loading to return one message with and one without attachment
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    msg1 = ParsedMessage(text="begin 644 file.txt\n#0V%T\n`\nend\n", msgnum=1, refnum=None, confnum=1, header=header)
    msg2 = ParsedMessage(text="Just text", msgnum=2, refnum=None, confnum=1, header=header)

    import pyqwk.core
    monkeypatch.setattr(pyqwk.core, "load_data", lambda *a: (bytearray(), {1: "General"}))
    monkeypatch.setattr(pyqwk.core, "parse_messages", lambda *a, **k: [msg1, msg2])

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437',
        has_attachments=True,
        quiet=True
    )

    process_merged_files(["test.qwk"], settings, MagicMock())

    captured = capsys.readouterr()
    # Should only contain msg1 content
    assert "begin 644 file.txt" in captured.out
    assert "Just text" not in captured.out
