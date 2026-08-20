import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters, _order_messages_by_thread

def test_depth_filtering_logic():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="Author", msgsubject="Test", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )

    # Message with depth 2
    msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header, depth=2)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437",
        min_depth=1, max_depth=3
    )

    assert matches_filters(msg, settings, {1}) is True

    # Test min depth failure
    settings.min_depth = 3
    assert matches_filters(msg, settings, {1}) is False

    # Test max depth failure
    settings.min_depth = 1
    settings.max_depth = 1
    assert matches_filters(msg, settings, {1}) is False

def test_depth_calculation_and_filtering():
    h1 = MessageHeader(
        status=" ", msgnum=10, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="User1", msgsubject="Root", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    h2 = MessageHeader(
        status=" ", msgnum=11, msgdate="01-01-23", msgtime="12:05",
        msgto="User1", msgfrom="User2", msgsubject="Re: Root", msgpassword="",
        refnum=10, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    h3 = MessageHeader(
        status=" ", msgnum=12, msgdate="01-01-23", msgtime="12:10",
        msgto="User2", msgfrom="User3", msgsubject="Re: Root", msgpassword="",
        refnum=11, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )

    m1 = ParsedMessage(text="Root", msgnum=10, refnum=None, confnum=1, header=h1)
    m2 = ParsedMessage(text="Reply 1", msgnum=11, refnum=10, confnum=1, header=h2)
    m3 = ParsedMessage(text="Reply 2", msgnum=12, refnum=11, confnum=1, header=h3)

    # Order them to set depths
    threaded = _order_messages_by_thread([m1, m2, m3])

    assert threaded[0].depth == 0
    assert threaded[1].depth == 1
    assert threaded[2].depth == 2

    # Test filtering on the threaded results
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=True, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437",
        min_depth=1
    )

    filtered = [m for m in threaded if (settings.min_depth is None or m.depth >= settings.min_depth)
                and (settings.max_depth is None or m.depth <= settings.max_depth)]

    assert len(filtered) == 2
    assert filtered[0].msgnum == 11
    assert filtered[1].msgnum == 12

    settings.min_depth = 0
    settings.max_depth = 0
    filtered = [m for m in threaded if (settings.min_depth is None or m.depth >= settings.min_depth)
                and (settings.max_depth is None or m.depth <= settings.max_depth)]
    assert len(filtered) == 1
    assert filtered[0].msgnum == 10


def test_cli_depth_arguments(mocker, monkeypatch, tmp_path):
    from pyqwk.cli import main

    mock_process = mocker.patch("pyqwk.cli.process_merged_files")
    test_file = tmp_path / "dummy.qwk"
    test_file.write_text("dummy content")

    monkeypatch.setattr(
        "sys.argv",
        ["qwk", str(test_file), "--threaded", "--min-depth", "1", "--max-depth", "5"]
    )

    main()

    mock_process.assert_called_once()
    _, settings, _ = mock_process.call_args[0]
    assert settings.min_depth == 1
    assert settings.max_depth == 5
