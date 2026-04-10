
import pytest
import logging
from dataclasses import replace
from pyqwk.core import process_merged_files, ProcessingSettings, ParsedMessage, MessageHeader

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_to_filtering")

@pytest.fixture
def mock_messages():
    header_template = MessageHeader(
        status=' ', msgnum=1, msgdate='', msgtime='', msgto='', msgfrom='',
        msgsubject='', msgpassword='', refnum=None, numblocks=1,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )

    msgs = []
    # Alice to Bob
    msgs.append(ParsedMessage(
        text="Hello Bob",
        msgnum=1, refnum=None, confnum=1,
        header=replace(header_template, msgnum=1, msgfrom="Alice", msgto="Bob", msgsubject="Greeting")
    ))
    # Bob to Alice
    msgs.append(ParsedMessage(
        text="Hello Alice",
        msgnum=2, refnum=None, confnum=1,
        header=replace(header_template, msgnum=2, msgfrom="Bob", msgto="Alice", msgsubject="Reply")
    ))
    # Charlie to Dave
    msgs.append(ParsedMessage(
        text="Secret message",
        msgnum=3, refnum=None, confnum=1,
        header=replace(header_template, msgnum=3, msgfrom="Charlie", msgto="Dave", msgsubject="Top Secret")
    ))
    return msgs

def test_filtering_by_recipient_single(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        recipients=["Bob"]
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Hello Bob" in content
    assert "Hello Alice" not in content
    assert "Secret message" not in content

def test_filtering_by_recipient_multiple(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        recipients=["Bob", "Dave"]
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Hello Bob" in content
    assert "Secret message" in content
    assert "Hello Alice" not in content

def test_filtering_by_recipient_case_insensitive(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        recipients=["alice"] # lowercase
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Hello Alice" in content
    assert "Hello Bob" not in content

def test_search_includes_recipient(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    # Searching for "Dave" should find the message where he is the recipient
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        search_term="Dave"
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Secret message" in content
    assert "Hello Bob" not in content
    assert "Hello Alice" not in content
