import pytest
import logging
from dataclasses import replace
from pyqwk.core import (
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)


@pytest.fixture
def mock_logger():
    return logging.getLogger("test_search")


@pytest.fixture
def mock_messages():
    header_template = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject="",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )

    msgs = []
    # Alice, Hello World, "The quick brown fox"
    msgs.append(
        ParsedMessage(
            text="The quick brown fox jumps over the lazy dog.",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=replace(
                header_template,
                confnum=1,
                msgnum=1,
                msgfrom="Alice",
                msgsubject="Hello World",
            ),
        )
    )
    # Bob, Tech Stuff, "Python is a programming language"
    msgs.append(
        ParsedMessage(
            text="Python is a programming language.",
            msgnum=2,
            refnum=None,
            confnum=2,
            header=replace(
                header_template,
                confnum=2,
                msgnum=2,
                msgfrom="Bob",
                msgsubject="Tech Stuff",
            ),
        )
    )
    # Charlie, Python Rules, "BBS systems are cool"
    msgs.append(
        ParsedMessage(
            text="BBS systems are cool.",
            msgnum=3,
            refnum=None,
            confnum=3,
            header=replace(
                header_template,
                confnum=3,
                msgnum=3,
                msgfrom="Charlie",
                msgsubject="Python Rules",
            ),
        )
    )
    return msgs


def test_search_in_author(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        search_term="alice",
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "The quick brown fox" in content
    assert "Python is a programming language" not in content


def test_search_in_subject(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        search_term="tech",
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Python is a programming language" in content
    assert "The quick brown fox" not in content


def test_search_in_body(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        search_term="bbs",
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "BBS systems are cool" in content
    assert "Python is a programming language" not in content


def test_search_combined_with_filters(
    tmp_path, mock_messages, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Search "Python" AND Conference 2
    # Message 2 has "Python" in body and Conf 2 -> Match
    # Message 3 has "Python" in subject but Conf 3 -> No Match
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        search_term="python",
        conferences=["2"],
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Python is a programming language" in content
    assert "BBS systems are cool" not in content


def test_search_no_match(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        search_term="nonexistent",
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content == ""
