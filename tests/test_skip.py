
import pytest
import logging
from dataclasses import replace
from pyqwk.core import process_file, ProcessingSettings, ParsedMessage, MessageHeader

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_skip")

@pytest.fixture
def mock_messages():
    header_template = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00', msgto='Everyone', msgfrom='Alice',
        msgsubject='Subject', msgpassword='', refnum=None, numblocks=2,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )

    msgs = []
    for i in range(1, 11):
        msgs.append(ParsedMessage(
            text=f"Msg:{i:02d}",
            msgnum=i, refnum=None, confnum=1,
            header=replace(header_template, msgnum=i)
        ))
    return msgs

def test_skip_ignores_first_n_messages(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    skip = 5
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        skip=skip
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    # Should NOT contain Message 1 to 5
    assert "Msg:01" not in content
    assert "Msg:05" not in content
    # Should contain Message 6 to 10
    assert "Msg:06" in content
    assert "Msg:10" in content

def test_skip_and_limit_together(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    skip = 2
    limit = 3
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        skip=skip,
        limit=limit
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    # Should skip 1, 2. Process 3, 4, 5. Stop before 6.
    assert "Msg:01" not in content
    assert "Msg:02" not in content
    assert "Msg:03" in content
    assert "Msg:04" in content
    assert "Msg:05" in content
    assert "Msg:06" not in content

def test_skip_exceeds_total(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        skip=20
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content == ""

def test_skip_with_unique(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    # Create duplicates: 1, 1, 2, 2, 3, 3...
    duplicated_msgs = []
    for m in mock_messages:
        duplicated_msgs.append(m)
        duplicated_msgs.append(m)

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from duplicated_msgs

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Unique should reduce to 1, 2, 3, 4, 5...
    # Skip 2 should skip 1 and 2.
    # Limit 2 should give 3 and 4.
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        unique=True,
        skip=2,
        limit=2
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Msg:01" not in content
    assert "Msg:02" not in content
    assert "Msg:03" in content
    assert "Msg:04" in content
    assert "Msg:05" not in content
