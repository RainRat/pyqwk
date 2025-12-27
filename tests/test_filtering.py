
import pytest
import logging
from dataclasses import replace
from qwk import process_file, ProcessingSettings, ParsedMessage, MessageHeader, load_data, parse_messages

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_filtering")

@pytest.fixture
def mock_messages():
    header_template = MessageHeader(
        status=' ', msgnum=1, msgdate='', msgtime='', msgto='', msgfrom='',
        msgsubject='', msgpassword='', refnum=None, numblocks=1,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )

    msgs = []
    # Conf 1: General
    msgs.append(ParsedMessage(
        text="Msg 1 in Conf 1",
        msgnum=1, refnum=None, confnum=1,
        header=replace(header_template, confnum=1, msgnum=1)
    ))
    # Conf 2: Tech
    msgs.append(ParsedMessage(
        text="Msg 2 in Conf 2",
        msgnum=2, refnum=None, confnum=2,
        header=replace(header_template, confnum=2, msgnum=2)
    ))
    # Conf 3: Python
    msgs.append(ParsedMessage(
        text="Msg 3 in Conf 3",
        msgnum=3, refnum=None, confnum=3,
        header=replace(header_template, confnum=3, msgnum=3)
    ))
    # Private message
    msgs.append(ParsedMessage(
        text="Private Message",
        msgnum=4, refnum=None, confnum=1,
        header=replace(header_template, confnum=1, msgnum=4, status='*')
    ))
    # Password protected message
    msgs.append(ParsedMessage(
        text="Password Protected",
        msgnum=5, refnum=None, confnum=1,
        header=replace(header_template, confnum=1, msgnum=5, status='%')
    ))
    return msgs

@pytest.fixture
def mock_board_dict():
    return {
        1: "General",
        2: "Tech Talk",
        3: "Python Dev"
    }

def test_excludes_private_messages_by_default(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Private Message" not in content

def test_includes_private_messages_when_requested(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Private Message" in content

def test_always_excludes_password_protected_messages(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    # Even with private=True, password protected should be skipped
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Password Protected" not in content

def test_filtering_by_id(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        conferences=["2"]
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Msg 2 in Conf 2" in content
    assert "Msg 1 in Conf 1" not in content
    assert "Msg 3 in Conf 3" not in content

def test_filtering_by_name_exact(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        conferences=["Python Dev"]
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Msg 3 in Conf 3" in content
    assert "Msg 1 in Conf 1" not in content

def test_filtering_by_name_substring_case_insensitive(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        conferences=["tech"] # Should match "Tech Talk"
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Msg 2 in Conf 2" in content
    assert "Msg 1 in Conf 1" not in content

def test_filtering_multiple_criteria(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        conferences=["1", "python"]
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Msg 1 in Conf 1" in content # Match by ID "1"
    assert "Msg 3 in Conf 3" in content # Match by name "python"
    assert "Msg 2 in Conf 2" not in content

def test_filtering_numeric_fallback_when_names_missing(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    # Empty board dict (no control.dat)
    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        conferences=["2"]
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Msg 2 in Conf 2" in content
    assert "Msg 1 in Conf 1" not in content

def test_filtering_no_matches(tmp_path, mock_messages, mock_board_dict, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("qwk.load_data", fake_load_data)
    monkeypatch.setattr("qwk.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        conferences=["NonExistent"]
    )

    process_file("dummy.qwk", settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content == ""
