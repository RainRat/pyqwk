import pytest
from pyqwk.core import ParsedMessage, ProcessingSettings, matches_filters, MessageHeader

def create_mock_header():
    return MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-20",
        msgtime="00:00",
        msgto="To",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag=""
    )

def test_max_depth_filter():
    # Mock messages with different depths
    msg_depth_0 = ParsedMessage(
        text="Body",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=create_mock_header(),
        depth=0
    )

    msg_depth_1 = ParsedMessage(
        text="Body",
        msgnum=2,
        refnum=1,
        confnum=1,
        header=create_mock_header(),
        depth=1
    )

    msg_depth_2 = ParsedMessage(
        text="Body",
        msgnum=3,
        refnum=2,
        confnum=1,
        header=create_mock_header(),
        depth=2
    )

    # Settings with no max_depth
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="utf-8", max_depth=None
    )

    assert matches_filters(msg_depth_0, settings, set()) is True
    assert matches_filters(msg_depth_1, settings, set()) is True
    assert matches_filters(msg_depth_2, settings, set()) is True

    # Settings with max_depth=0
    settings.max_depth = 0
    assert matches_filters(msg_depth_0, settings, set()) is True
    assert matches_filters(msg_depth_1, settings, set()) is False
    assert matches_filters(msg_depth_2, settings, set()) is False

    # Settings with max_depth=1
    settings.max_depth = 1
    assert matches_filters(msg_depth_0, settings, set()) is True
    assert matches_filters(msg_depth_1, settings, set()) is True
    assert matches_filters(msg_depth_2, settings, set()) is False

def test_max_depth_filter_default_depth():
    # Message without explicitly setting depth (should default to 0 in dataclass)
    msg = ParsedMessage(
        text="Body",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=create_mock_header()
    )

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="utf-8", max_depth=0
    )

    assert matches_filters(msg, settings, set()) is True

    settings.max_depth = -1 # Should filter out even depth 0
    assert matches_filters(msg, settings, set()) is False
