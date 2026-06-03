import pytest
from pyqwk.core import ProcessingSettings, matches_filters, ParsedMessage, MessageHeader
from pyqwk.cli import _parse_msgnum_ranges


def test_parse_msgnum_ranges():
    assert _parse_msgnum_ranges("100") == {100}
    assert _parse_msgnum_ranges("100,200,300") == {100, 200, 300}
    assert _parse_msgnum_ranges("100-105") == {100, 101, 102, 103, 104, 105}
    assert _parse_msgnum_ranges("1,5-7,10") == {1, 5, 6, 7, 10}
    assert _parse_msgnum_ranges("") is None

    with pytest.raises(ValueError, match="Invalid message number"):
        _parse_msgnum_ranges("abc")

    with pytest.raises(ValueError, match="Invalid message number range"):
        _parse_msgnum_ranges("100-xyz")


def message_with_num(msgnum):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text="Body", msgnum=msgnum, refnum=None, confnum=1, header=header
    )


def test_msgnum_filtering():
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        msgnum_filters={10, 20, 30, 31, 32},
    )

    allowed_confs = {1}

    assert matches_filters(message_with_num(10), settings, allowed_confs) is True
    assert matches_filters(message_with_num(20), settings, allowed_confs) is True
    assert matches_filters(message_with_num(31), settings, allowed_confs) is True
    assert matches_filters(message_with_num(15), settings, allowed_confs) is False
    assert matches_filters(message_with_num(100), settings, allowed_confs) is False


def test_msgnum_filtering_none():
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        msgnum_filters=None,
    )

    allowed_confs = {1}
    assert matches_filters(message_with_num(10), settings, allowed_confs) is True
    assert matches_filters(message_with_num(100), settings, allowed_confs) is True


def test_msgnum_filtering_missing_num():
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        msgnum_filters={10, 20},
    )

    allowed_confs = {1}
    # message_with_num(None) creates a message with msgnum=None
    assert matches_filters(message_with_num(None), settings, allowed_confs) is False
