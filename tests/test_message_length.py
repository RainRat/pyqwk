import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters, process_merged_files
from pyqwk.cli import main
import sys
import io
import os
import tempfile
import json

def test_length_filtering_unit():
    header = MessageHeader(' ', 1, '01-01-90', '12:00', 'To', 'From', 'Subj', '', None, 1, ' ', 1, 1, '')
    msg_short = ParsedMessage("Short", 1, None, 1, header)
    msg_long = ParsedMessage("A very long message body indeed", 2, None, 1, header)

    # Defaults
    settings = ProcessingSettings(verbose=False, private=True, no_header=True, truncate_signatures=False,
                                 cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
                                 redact_pii=False, format='text', separator='none', output_mode='stdout',
                                 output_path=None, encoding='cp437')

    assert matches_filters(msg_short, settings, set()) is True
    assert matches_filters(msg_long, settings, set()) is True

    # Min length
    settings.min_length = 10
    assert matches_filters(msg_short, settings, set()) is False
    assert matches_filters(msg_long, settings, set()) is True

    # Max length
    settings.min_length = None
    settings.max_length = 10
    assert matches_filters(msg_short, settings, set()) is True
    assert matches_filters(msg_long, settings, set()) is False

    # Both
    settings.min_length = 5
    settings.max_length = 10
    assert matches_filters(msg_short, settings, set()) is True
    assert matches_filters(msg_long, settings, set()) is False

def test_sorting_by_length(monkeypatch):
    header = MessageHeader(' ', 1, '01-01-90', '12:00', 'To', 'From', 'Subj', '', None, 1, ' ', 1, 1, '')
    msg1 = ParsedMessage("Medium length", 1, None, 1, header)
    msg2 = ParsedMessage("Short", 2, None, 1, header)
    msg3 = ParsedMessage("Very long message body text", 3, None, 1, header)

    messages = [msg1, msg2, msg3]

    # Mock load_data to return our messages
    def mock_load_data(path, logger, encoding):
        return messages, {1: "General"}

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)

    settings = ProcessingSettings(verbose=False, private=True, no_header=True, truncate_signatures=False,
                                 cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
                                 redact_pii=False, format='json', separator='none', output_mode='stdout',
                                 output_path=None, encoding='cp437', sort='length', quiet=True)

    # Capture stdout
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    process_merged_files(["dummy.qwk"], settings, None)

    results = json.loads(stdout.getvalue())
    assert results[0]['text'].strip() == "Short"
    assert results[1]['text'].strip() == "Medium length"
    assert results[2]['text'].strip() == "Very long message body text"

def test_cli_length_args(monkeypatch, tmp_path):
    # Create a dummy JSON archive
    archive_path = tmp_path / "test.json"
    data = [
        {"header": {"confnum": 1, "msgnum": 1, "msgsubject": "Short"}, "text": "Short"},
        {"header": {"confnum": 1, "msgnum": 2, "msgsubject": "Long"}, "text": "A much longer message body"}
    ]
    archive_path.write_text(json.dumps(data))

    # Test --min-length
    test_args = ["qwk.py", str(archive_path), "--min-length", "10", "--json", "--quiet", "--noheader", "--private"]
    monkeypatch.setattr(sys, "argv", test_args)

    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    main()

    # Note: main() might call sys.exit(0)

    results = json.loads(stdout.getvalue())
    assert len(results) == 1
    assert results[0]['text'].strip() == "A much longer message body"

    # Test --max-length
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    test_args = ["qwk.py", str(archive_path), "--max-length", "10", "--json", "--quiet", "--noheader", "--private"]
    monkeypatch.setattr(sys, "argv", test_args)

    main()

    results = json.loads(stdout.getvalue())
    assert len(results) == 1
    assert results[0]['text'].strip() == "Short"

def test_filename_pattern_length(monkeypatch, tmp_path):
    header = MessageHeader(' ', 1, '01-01-90', '12:00', 'To', 'From', 'Subj', '', None, 1, ' ', 1, 1, '')
    msg = ParsedMessage("Body", 1, None, 1, header)

    # Mock load_data
    monkeypatch.setattr("pyqwk.core.load_data", lambda p, l, e: ([msg], {1: "General"}))

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    settings = ProcessingSettings(verbose=False, private=True, no_header=True, truncate_signatures=False,
                                 cut_quoting=False, individual_files=True, threaded=False, binaries_removal=False,
                                 redact_pii=False, format='text', separator='none', output_mode='file',
                                 output_path=str(output_dir), encoding='cp437',
                                 filename_pattern="{msgnum}_{length}")

    process_merged_files(["dummy.qwk"], settings, None)

    expected_file = output_dir / "1_4.txt"
    assert expected_file.exists()
