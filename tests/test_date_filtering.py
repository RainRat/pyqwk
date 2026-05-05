import pytest
import datetime
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
    return logging.getLogger("test_date_filtering")


@pytest.fixture
def mock_messages_with_dates():
    header_template = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="",
        msgtime="12:00",
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
    # Old message: 1990-01-01
    msgs.append(
        ParsedMessage(
            text="Old Message",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=replace(header_template, msgdate="01-01-90", msgsubject="Old"),
        )
    )
    # Middle message: 2000-01-01
    msgs.append(
        ParsedMessage(
            text="Middle Message",
            msgnum=2,
            refnum=None,
            confnum=1,
            header=replace(header_template, msgdate="01-01-00", msgsubject="Middle"),
        )
    )
    # New message: 2020-01-01
    msgs.append(
        ParsedMessage(
            text="New Message",
            msgnum=3,
            refnum=None,
            confnum=1,
            header=replace(header_template, msgdate="01-01-20", msgsubject="New"),
        )
    )
    return msgs


@pytest.fixture
def mock_board_dict():
    return {1: "General"}


def test_filter_after(
    tmp_path, mock_messages_with_dates, mock_board_dict, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages_with_dates

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Filter after 1995-01-01 (Should exclude Old Message)
    after_date = datetime.datetime(1995, 1, 1)

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
        after=after_date,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Old Message" not in content
    assert "Middle Message" in content
    assert "New Message" in content


def test_filter_before(
    tmp_path, mock_messages_with_dates, mock_board_dict, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages_with_dates

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Filter before 2010-01-01.
    # To simulate CLI "end of day" behavior, we set before_date manually to end of day.
    before_date = datetime.datetime(2010, 1, 1, 23, 59, 59)

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
        before=before_date,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Old Message" in content
    assert "Middle Message" in content
    assert "New Message" not in content


def test_filter_range(
    tmp_path, mock_messages_with_dates, mock_board_dict, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages_with_dates

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Filter between 1995 and 2010 (Should keep only Middle Message)
    after_date = datetime.datetime(1995, 1, 1)
    before_date = datetime.datetime(2010, 1, 1, 23, 59, 59)

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
        after=after_date,
        before=before_date,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Old Message" not in content
    assert "Middle Message" in content
    assert "New Message" not in content


def test_filter_exact_boundary(
    tmp_path, mock_messages_with_dates, mock_board_dict, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages_with_dates

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Filter after 2000-01-01. Middle Message is exactly on this date (at 12:00)
    after_date = datetime.datetime(2000, 1, 1)

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
        after=after_date,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Middle Message" in content  # 2000-01-01 is >= 2000-01-01


def test_filter_before_boundary_inclusive(
    tmp_path, mock_messages_with_dates, mock_board_dict, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages_with_dates

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Filter before 2000-01-01. Middle Message is exactly on this date (at 12:00)
    # We expect it to be INCLUDED because it's "on or before"
    before_date = datetime.datetime(2000, 1, 1, 23, 59, 59)

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
        before=before_date,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Middle Message" in content  # 2000-01-01 12:00 is <= 2000-01-01 23:59:59


def test_filter_exclude_future(
    tmp_path, mock_messages_with_dates, mock_board_dict, mock_logger, monkeypatch
):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), mock_board_dict

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages_with_dates

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Filter before 1980 (Should exclude all)
    before_date = datetime.datetime(1980, 1, 1, 23, 59, 59)

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
        before=before_date,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content == ""
