import logging
import pyqwk.core as qwk
from pyqwk.core import ProcessingSettings, show_stats, ParsedMessage, MessageHeader


def test_show_stats_bar_charts(capsys, monkeypatch):
    # Mock messages to have different counts for authors, recipients, and conferences
    h1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Recipient A",
        msgfrom="Author A",
        msgsubject="Subj1",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    h2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-01-23",
        msgtime="13:00",
        msgto="Recipient A",
        msgfrom="Author B",
        msgsubject="Subj2",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=2,
        lognum=2,
        nettag="",
    )
    h3 = MessageHeader(
        status=" ",
        msgnum=3,
        msgdate="01-01-23",
        msgtime="14:00",
        msgto="Recipient B",
        msgfrom="Author A",
        msgsubject="Subj3",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=3,
        nettag="",
    )

    msgs = [
        ParsedMessage(text="Msg 1", msgnum=1, refnum=None, confnum=1, header=h1),
        ParsedMessage(text="Msg 2", msgnum=2, refnum=None, confnum=2, header=h2),
        ParsedMessage(text="Msg 3", msgnum=3, refnum=None, confnum=1, header=h3),
    ]

    monkeypatch.setattr(
        qwk,
        "load_data",
        lambda *args, **kwargs: (
            bytearray(b"Produced \0" + b"\0" * 119),
            {1: "General", 2: "Tech"},
        ),
    )
    monkeypatch.setattr(qwk, "parse_messages", lambda *args, **kwargs: iter(msgs))

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test")

    # Mock isatty to force color output for testing
    import sys

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    show_stats(["dummy.qwk"], settings, logger)

    captured = capsys.readouterr().out

    # Check Top Authors (with ANSI codes: DIM=90, BOLD=1, CYAN=36 and Unicode blocks)
    assert "Top Authors:" in captured
    assert (
        "\x1b[90mAuthor A                 \x1b[0m : \x1b[1m   2\x1b[0m \x1b[36m████████████████████████████████████████\x1b[0m"
        in captured
    )
    assert (
        "\x1b[90mAuthor B                 \x1b[0m : \x1b[1m   1\x1b[0m \x1b[36m████████████████████\x1b[0m"
        in captured
    )

    # Check Top Recipients
    assert "Top Recipients:" in captured
    assert (
        "\x1b[90mRecipient A              \x1b[0m : \x1b[1m   2\x1b[0m \x1b[36m████████████████████████████████████████\x1b[0m"
        in captured
    )
    assert (
        "\x1b[90mRecipient B              \x1b[0m : \x1b[1m   1\x1b[0m \x1b[36m████████████████████\x1b[0m"
        in captured
    )

    # Check Top Conferences
    assert "Top Conferences:" in captured
    assert (
        "\x1b[90m  1 General              \x1b[0m : \x1b[1m   2\x1b[0m \x1b[36m████████████████████████████████████████\x1b[0m"
        in captured
    )
    assert (
        "\x1b[90m  2 Tech                 \x1b[0m : \x1b[1m   1\x1b[0m \x1b[36m████████████████████\x1b[0m"
        in captured
    )
