import sys
import logging
from pathlib import Path
import pytest
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyqwk.core as qwk
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)

def _make_header(msgnum, msgdate, msgtime, msgfrom, msgto, msgsubject, confnum):
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=confnum,
        lognum=1,
        nettag="",
    )

@pytest.fixture
def mock_messages():
    # Dates are MM-DD-YY
    h1 = _make_header(1, "01-01-23", "12:00", "Alice", "Bob", "Subject C", 1)
    h2 = _make_header(2, "02-01-23", "10:00", "Charlie", "Alice", "Subject B", 1)
    h3 = _make_header(3, "01-01-23", "09:00", "Bob", "Charlie", "Subject A", 2)

    return [
        ParsedMessage(text="Message 1", msgnum=1, refnum=None, confnum=1, header=h1),
        ParsedMessage(text="Message 2", msgnum=2, refnum=None, confnum=1, header=h2),
        ParsedMessage(text="Message 3", msgnum=3, refnum=None, confnum=2, header=h3),
    ]

def _make_settings(**overrides):
    defaults = dict(
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
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        conferences=None,
        authors=None,
        recipients=None,
        subjects=None,
        search_term=None,
        after=None,
        before=None,
        limit=None,
        skip=None,
        sort=None,
        reverse=False,
        headers_only=False,
        unique=False,
        organize=False,
        strip_ansi=False,
        quiet=True,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_sort_by_date(mock_messages, monkeypatch, capsys):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = _make_settings(sort="date")
    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr().out
    # Expected chronological order:
    # 3 (01-01-23 09:00)
    # 1 (01-01-23 12:00)
    # 2 (02-01-23 10:00)
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    assert lines == ["Message 3", "Message 1", "Message 2"]

def test_sort_by_author(mock_messages, monkeypatch, capsys):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = _make_settings(sort="author")
    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr().out
    # Alice (1), Bob (3), Charlie (2)
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    assert lines == ["Message 1", "Message 3", "Message 2"]

def test_sort_by_subject(mock_messages, monkeypatch, capsys):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = _make_settings(sort="subject")
    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr().out
    # Subj A (3), Subj B (2), Subj C (1)
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    assert lines == ["Message 3", "Message 2", "Message 1"]

def test_reverse(mock_messages, monkeypatch, capsys):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = _make_settings(reverse=True)
    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr().out
    # Natural order reversed: 3, 2, 1
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    assert lines == ["Message 3", "Message 2", "Message 1"]

def test_sort_by_conference(mock_messages, monkeypatch, capsys):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = _make_settings(sort="conference")
    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr().out
    # Conf 1 (1, 2), Conf 2 (3)
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    assert lines == ["Message 1", "Message 2", "Message 3"]

def test_sort_with_limit(mock_messages, monkeypatch, capsys):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = _make_settings(sort="author", limit=2)
    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr().out
    # Alice (1), Bob (3)
    lines = [line.strip() for line in captured.splitlines() if line.strip()]
    assert lines == ["Message 1", "Message 3"]

def test_sort_with_individual_files(mock_messages, monkeypatch, tmp_path):
    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "Conf 1", 2: "Conf 2"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(mock_messages))

    output_dir = tmp_path / "out"
    settings = _make_settings(sort="subject", individual_files=True, output_mode="file", output_path=str(output_dir))

    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    files = sorted(list(output_dir.iterdir()))
    assert len(files) == 3
    # Check that they were all written. Sorting for individual files doesn't change much
    # except the collision counter (if used), but we verify it still works.
    assert any("subject_a" in f.name for f in files)
    assert any("subject_b" in f.name for f in files)
    assert any("subject_c" in f.name for f in files)
