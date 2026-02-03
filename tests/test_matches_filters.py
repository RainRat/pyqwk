
import pytest
import datetime
from pyqwk.core import matches_filters, ProcessingSettings, ParsedMessage, MessageHeader

@pytest.fixture
def base_header():
    return MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='To', msgfrom='From', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )

@pytest.fixture
def base_message(base_header):
    return ParsedMessage(
        text="Body", msgnum=1, refnum=None, confnum=1, header=base_header
    )

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", quiet=True
    )

def test_matches_filters_private_exclusion(base_message, default_settings):
    # Default: private=False, message is public
    assert matches_filters(base_message, default_settings, {}) is True

    # Message is private
    base_message.header.status = '*'
    assert matches_filters(base_message, default_settings, {}) is False

    # Allow private
    default_settings.private = True
    assert matches_filters(base_message, default_settings, {}) is True

def test_matches_filters_password_exclusion(base_message, default_settings):
    # Message is password protected
    base_message.header.status = '%'
    assert matches_filters(base_message, default_settings, {}) is False

    # Even if private=True, password protected is excluded
    default_settings.private = True
    assert matches_filters(base_message, default_settings, {}) is False

def test_matches_filters_conference(base_message, default_settings):
    default_settings.conferences = ["1"]
    allowed = {1}
    assert matches_filters(base_message, default_settings, {}, allowed) is True

    default_settings.conferences = ["2"]
    allowed = {2}
    assert matches_filters(base_message, default_settings, {}, allowed) is False

def test_matches_filters_author(base_message, default_settings):
    base_message.header.msgfrom = "Alice Smith"

    default_settings.authors = ["alice"]
    assert matches_filters(base_message, default_settings, {}) is True

    default_settings.authors = ["bob"]
    assert matches_filters(base_message, default_settings, {}) is False

def test_matches_filters_subject(base_message, default_settings):
    base_message.header.msgsubject = "Important Update"

    default_settings.subjects = ["update"]
    assert matches_filters(base_message, default_settings, {}) is True

    default_settings.subjects = ["news"]
    assert matches_filters(base_message, default_settings, {}) is False

def test_matches_filters_date(base_message, default_settings):
    base_message.header.msgdate = "06-15-23"
    base_message.header.msgtime = "10:00"
    # Date is 2023-06-15 10:00

    # After filter
    default_settings.after = datetime.datetime(2023, 1, 1)
    assert matches_filters(base_message, default_settings, {}) is True

    default_settings.after = datetime.datetime(2024, 1, 1)
    assert matches_filters(base_message, default_settings, {}) is False

    # Before filter
    default_settings.after = None
    default_settings.before = datetime.datetime(2023, 12, 31)
    assert matches_filters(base_message, default_settings, {}) is True

    default_settings.before = datetime.datetime(2022, 12, 31)
    assert matches_filters(base_message, default_settings, {}) is False

def test_matches_filters_search_term(base_message, default_settings):
    base_message.header.msgfrom = "Alice Smith"
    base_message.header.msgsubject = "Hello World"

    # Matches author
    default_settings.search_term = "alice"
    assert matches_filters(base_message, default_settings, {}) is True

    # Matches subject
    default_settings.search_term = "world"
    assert matches_filters(base_message, default_settings, {}) is True

    # No match
    default_settings.search_term = "bob"
    assert matches_filters(base_message, default_settings, {}) is False

def test_matches_filters_on_the_fly_conferences(base_message, default_settings):
    # Test that it calculates allowed_conferences if None is passed
    default_settings.conferences = ["General"]
    board_dict = {1: "General Chat"}

    assert matches_filters(base_message, default_settings, board_dict, None) is True

    default_settings.conferences = ["Tech"]
    assert matches_filters(base_message, default_settings, board_dict, None) is False
