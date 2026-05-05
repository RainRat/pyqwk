import pytest
from dataclasses import replace
from pyqwk.core import ProcessingSettings, ParsedMessage, MessageHeader, matches_filters


@pytest.fixture
def header_template():
    return MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="",
        msgfrom="",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )


def test_mine_filter_matches_sender(header_template):
    header = replace(header_template, msgfrom="Jules", msgto="Alice")
    message = ParsedMessage(
        text="Hello", msgnum=1, refnum=None, confnum=1, header=header
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
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
        encoding="cp437",
        quiet=True,
        mine=True,
    )

    # Matches when Jules is the user
    assert matches_filters(message, settings, set(), user_name="Jules") is True
    # Does not match when Jules is NOT the user
    assert matches_filters(message, settings, set(), user_name="Bob") is False


def test_mine_filter_matches_recipient(header_template):
    header = replace(header_template, msgfrom="Alice", msgto="Jules")
    message = ParsedMessage(
        text="Hello", msgnum=1, refnum=None, confnum=1, header=header
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
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
        encoding="cp437",
        quiet=True,
        mine=True,
    )

    # Matches when Jules is the user
    assert matches_filters(message, settings, set(), user_name="Jules") is True
    # Does not match when Jules is NOT the user
    assert matches_filters(message, settings, set(), user_name="Bob") is False


def test_mine_filter_case_insensitive(header_template):
    header = replace(header_template, msgfrom="jules", msgto="Alice")
    message = ParsedMessage(
        text="Hello", msgnum=1, refnum=None, confnum=1, header=header
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
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
        encoding="cp437",
        quiet=True,
        mine=True,
    )

    # Should be case-insensitive
    assert matches_filters(message, settings, set(), user_name="JULES") is True


def test_mine_filter_substring_match(header_template):
    header = replace(header_template, msgfrom="Jules Verne", msgto="Alice")
    message = ParsedMessage(
        text="Hello", msgnum=1, refnum=None, confnum=1, header=header
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
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
        encoding="cp437",
        quiet=True,
        mine=True,
    )

    # Should support substring match like other filters
    assert matches_filters(message, settings, set(), user_name="Jules") is True


def test_mine_filter_disabled(header_template):
    header = replace(header_template, msgfrom="Alice", msgto="Bob")
    message = ParsedMessage(
        text="Hello", msgnum=1, refnum=None, confnum=1, header=header
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
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
        encoding="cp437",
        quiet=True,
        mine=False,
    )

    # If mine is False, it should match even if user_name is different (it's ignored)
    assert matches_filters(message, settings, set(), user_name="Jules") is True
