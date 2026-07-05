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

def test_process_merged_files_threaded_depth_filtering_integration(tmp_path):
    import logging
    import sys
    from unittest.mock import patch
    from pyqwk.core import process_merged_files, ConferenceMap, BBSInfo

    dummy_archive = tmp_path / "dummy.qwk"
    dummy_archive.write_text("dummy content")

    h1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="All", msgfrom="User1", msgsubject="Root", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    h2 = MessageHeader(
        status=" ", msgnum=2, msgdate="01-01-23", msgtime="12:05",
        msgto="User1", msgfrom="User2", msgsubject="Re: Root", msgpassword="",
        refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )

    m1 = ParsedMessage(text="Root Body Text", msgnum=1, refnum=None, confnum=1, header=h1)
    m2 = ParsedMessage(text="Reply Body Text", msgnum=2, refnum=1, confnum=1, header=h2)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=True, binaries_removal=False,
        redact_pii=False, format="text", separator="auto", output_mode="stdout",
        output_path=None, encoding="cp437",
        min_depth=1 # Only show replies
    )

    logger = logging.getLogger("test")
    board_dict = ConferenceMap({1: "General"})
    board_dict.bbs_info = BBSInfo(name="Test BBS", bbs_id="TEST")

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([m1, m2], board_dict)
        with patch("sys.stdout.write") as mock_stdout:
            process_merged_files([str(dummy_archive)], settings, logger)
            output = "".join(call.args[0] for call in mock_stdout.call_args_list)
            assert "Reply Body Text" in output
            assert "Root Body Text" not in output
