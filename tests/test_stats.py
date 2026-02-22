import pytest
import logging
import json
import pyqwk.core as qwk
from pyqwk.core import ProcessingSettings, show_stats, ParsedMessage, MessageHeader

def test_show_stats_basic(capsys):
    input_path = "testdata/test1_qwk.zip"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )
    logger = logging.getLogger("test")

    show_stats([input_path], settings, logger)

    captured = capsys.readouterr()
    assert "Statistics for:" in captured.out
    assert "Messages: 1 matching / 1 total" in captured.out
    assert "Warren Zatwarniski" in captured.out

def test_show_stats_json(capsys):
    input_path = "testdata/test1_qwk.zip"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='json',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )
    logger = logging.getLogger("test")

    show_stats([input_path], settings, logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["total_messages"] == 1
    assert data[0]["authors"][0]["name"] == "Warren Zatwarniski"
    assert data[0]["recipients"][0]["name"] == "Wes Kitchen"

def test_show_stats_filter(capsys):
    input_path = "testdata/test2_qwk.zip"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True,
        authors=["Russ"]
    )
    logger = logging.getLogger("test")

    show_stats([input_path], settings, logger)

    captured = capsys.readouterr()
    assert "Messages: 1 matching / 2 total" in captured.out
    assert "Russ Beuker" in captured.out
    assert "Chris Exner" not in captured.out

def test_show_stats_skip_limit(capsys):
    input_path = "testdata/test2_qwk.zip"
    # test2 has 2 messages.
    # Skip 1 should leave 1.
    # Limit 1 should leave 1.
    # Skip 2 should leave 0.

    logger = logging.getLogger("test")

    settings_skip = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='text', separator='auto',
        output_mode='stdout', output_path=None, encoding='cp437', quiet=True,
        skip=1
    )
    show_stats([input_path], settings_skip, logger)
    captured = capsys.readouterr()
    assert "Messages: 1 matching / 2 total" in captured.out

    settings_limit = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='text', separator='auto',
        output_mode='stdout', output_path=None, encoding='cp437', quiet=True,
        limit=1
    )
    show_stats([input_path], settings_limit, logger)
    captured = capsys.readouterr()
    assert "Messages: 1 matching / 2 total" in captured.out

    settings_both = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='text', separator='auto',
        output_mode='stdout', output_path=None, encoding='cp437', quiet=True,
        skip=1, limit=1
    )
    show_stats([input_path], settings_both, logger)
    captured = capsys.readouterr()
    assert "Messages: 1 matching / 2 total" in captured.out

    settings_skip_all = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='text', separator='auto',
        output_mode='stdout', output_path=None, encoding='cp437', quiet=True,
        skip=2
    )
    show_stats([input_path], settings_skip_all, logger)
    captured = capsys.readouterr()
    assert "Messages: 0 matching / 2 total" in captured.out

def test_show_stats_private_messages(monkeypatch, capsys):
    # Mock messages including a private one
    h1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="User1", msgsubject="Subj1",
        msgpassword="", refnum=None, numblocks=2, msgflag=" ",
        confnum=1, lognum=1, nettag="",
    )
    h2 = MessageHeader(
        status="*", msgnum=2, msgdate="01-01-23", msgtime="13:00",
        msgto="User1", msgfrom="User2", msgsubject="Private",
        msgpassword="", refnum=None, numblocks=2, msgflag=" ",
        confnum=1, lognum=1, nettag="",
    )

    msgs = [
        ParsedMessage(text="Msg 1", msgnum=1, refnum=None, confnum=1, header=h1),
        ParsedMessage(text="Msg 2", msgnum=2, refnum=None, confnum=1, header=h2),
    ]

    monkeypatch.setattr(qwk, "load_data", lambda *args, **kwargs: (bytearray(b'Produced \0' + b'\0'*119), {1: "General"}))
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(msgs))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='text', separator='auto',
        output_mode='stdout', output_path=None, encoding='cp437', quiet=True
    )
    logger = logging.getLogger("test")

    show_stats(["dummy.qwk"], settings, logger)

    captured = capsys.readouterr().out
    assert "Messages: 2 matching / 2 total" in captured
    assert "Private:    1 messages" in captured
