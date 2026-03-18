import json
import logging
from pyqwk.core import show_stats, ProcessingSettings, ParsedMessage, MessageHeader, ConferenceMap

def test_stats_advanced_metrics(monkeypatch, capsys, tmp_path):
    """Test that show_stats correctly calculates advanced metrics and distributions."""

    # Create mock messages with varied dates and reply indicators
    msg1 = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-90", msgtime="12:00",
            msgto="All", msgfrom="Alice", msgsubject="Topic 1",
            msgpassword="", refnum=0, numblocks=2, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )
    )
    msg2 = ParsedMessage(
        text="Reply to topic 1",
        msgnum=2,
        refnum=1,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=2, msgdate="01-02-90", msgtime="13:00",
            msgto="Alice", msgfrom="Bob", msgsubject="Re: Topic 1",
            msgpassword="", refnum=1, numblocks=2, msgflag=" ",
            confnum=1, lognum=2, nettag=""
        )
    )
    msg3 = ParsedMessage(
        text="Modern message from 2023",
        msgnum=100,
        refnum=0,
        confnum=2,
        header=MessageHeader(
            status=" ", msgnum=100, msgdate="05-20-23", msgtime="10:00",
            msgto="All", msgfrom="Charlie", msgsubject="Topic 2",
            msgpassword="", refnum=0, numblocks=2, msgflag=" ",
            confnum=2, lognum=100, nettag=""
        )
    )

    messages = [msg1, msg2, msg3]
    board_dict = ConferenceMap({1: "General", 2: "Modern"})

    # Mock load_data to return our pre-defined messages
    def mock_load_data(path, logger, encoding='cp437'):
        return messages, board_dict

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='json', separator='none',
        output_mode='stdout', output_path=None,
        encoding='cp437', quiet=True
    )

    logger = logging.getLogger("test")
    show_stats(["dummy.qwk"], settings, logger)

    captured = capsys.readouterr()
    stats = json.loads(captured.out)[0]

    # Verify Metrics
    assert stats["total_messages"] == 3
    assert stats["matching_messages"] == 3
    # msg2 is a reply (refnum=1 and "Re:" prefix)
    assert stats["reply_count"] == 1
    assert stats["reply_rate"] == 33.3

    # msg1: 11 chars, msg2: 16 chars, msg3: 24 chars. Total: 51. Avg: 17.0
    assert stats["avg_message_length"] == 17.0

    # Verify Distributions
    assert stats["year_distribution"]["1990"] == 2
    assert stats["year_distribution"]["2023"] == 1
    assert stats["month_distribution"]["1990-01"] == 2
    assert stats["month_distribution"]["2023-05"] == 1

def test_stats_advanced_ui(monkeypatch, capsys):
    """Test that the text output includes the new sections."""
    msg1 = ParsedMessage(
        text="Short",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-90", msgtime="12:00",
            msgto="All", msgfrom="Alice", msgsubject="Topic 1",
            msgpassword="", refnum=0, numblocks=2, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )
    )

    monkeypatch.setattr("pyqwk.core.load_data", lambda p, l, e: ([msg1], ConferenceMap({1: "Test"})))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='text', separator='none',
        output_mode='stdout', output_path=None,
        encoding='cp437', quiet=True
    )

    show_stats(["dummy.qwk"], settings, logging.getLogger("test"))

    captured = capsys.readouterr()
    assert "Vitality & Content:" in captured.out
    assert "Reply Rate:" in captured.out
    assert "Avg Length:" in captured.out
    assert "Yearly Activity:" in captured.out
    assert "1990 :" in captured.out
