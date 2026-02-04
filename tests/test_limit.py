
import pytest
import logging
from dataclasses import replace
from pyqwk.core import process_file, ProcessingSettings, ParsedMessage, MessageHeader

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_limit")

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
            text=f"Message {i}",
            msgnum=i, refnum=None, confnum=1,
            header=replace(header_template, msgnum=i)
        ))
    return msgs

def test_limit_restricts_output(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    limit = 3
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        limit=limit
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    # Should contain Message 1, 2, 3 but not 4
    assert "Message 1" in content
    assert "Message 2" in content
    assert "Message 3" in content
    assert "Message 4" not in content

    # Check number of messages (since separator is none, we just check strings)
    # But wait, our process_message adds a newline.
    # Actually, the best way is to check the length of the list if we can.
    # But we are testing the end-to-end file output.

def test_limit_zero(tmp_path, mock_messages, mock_logger, monkeypatch):
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
        limit=0
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content == ""

def test_limit_higher_than_total(tmp_path, mock_messages, mock_logger, monkeypatch):
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
        limit=20
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Message 10" in content
