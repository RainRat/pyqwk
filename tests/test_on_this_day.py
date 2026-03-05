import datetime
import pytest
from pyqwk.core import ProcessingSettings, ParsedMessage, MessageHeader, matches_filters

def _make_msg(date_str, month, day):
    # date_str is MM-DD-YY
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate=date_str,
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag=""
    )
    return ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header
    )

def _make_settings(on_this_day=True, reference_date=None):
    return ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format='text',
        separator='none',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        on_this_day=on_this_day,
        reference_date=reference_date
    )

def test_on_this_day_matches():
    # Feb 14, 1995
    msg = _make_msg("02-14-95", 2, 14)
    # Reference Feb 14, 2024
    settings = _make_settings(reference_date=datetime.datetime(2024, 2, 14))

    assert matches_filters(msg, settings, set()) == True

def test_on_this_day_mismatch_day():
    # Feb 14, 1995
    msg = _make_msg("02-14-95", 2, 14)
    # Reference Feb 15, 2024
    settings = _make_settings(reference_date=datetime.datetime(2024, 2, 15))

    assert matches_filters(msg, settings, set()) == False

def test_on_this_day_mismatch_month():
    # Feb 14, 1995
    msg = _make_msg("02-14-95", 2, 14)
    # Reference Mar 14, 2024
    settings = _make_settings(reference_date=datetime.datetime(2024, 3, 14))

    assert matches_filters(msg, settings, set()) == False

def test_on_this_day_leap_year():
    # Feb 29, 1996
    msg = _make_msg("02-29-96", 2, 29)
    # Reference Feb 29, 2024
    settings = _make_settings(reference_date=datetime.datetime(2024, 2, 29))

    assert matches_filters(msg, settings, set()) == True

def test_on_this_day_defaults_to_now(monkeypatch):
    # Feb 14, 1995
    msg = _make_msg("02-14-95", 2, 14)

    class MockDatetime(datetime.datetime):
        @classmethod
        def now(cls):
            return datetime.datetime(2024, 2, 14)

    monkeypatch.setattr(datetime, "datetime", MockDatetime)

    settings = _make_settings(reference_date=None)
    assert matches_filters(msg, settings, set()) == True

def test_on_this_day_disabled():
    # Feb 14, 1995
    msg = _make_msg("02-14-95", 2, 14)
    # Reference Feb 15, 2024, but feature disabled
    settings = _make_settings(on_this_day=False, reference_date=datetime.datetime(2024, 2, 15))

    assert matches_filters(msg, settings, set()) == True
