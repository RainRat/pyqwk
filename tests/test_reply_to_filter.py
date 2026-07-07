import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters

def create_msg(msgnum, refnum, confnum=1):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=refnum,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag=" "
    )
    return ParsedMessage(
        text="Body",
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header
    )

@pytest.fixture
def base_settings():
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437"
    )

def test_reply_to_single(base_settings):
    settings = base_settings
    settings.reply_to = {100}

    msg1 = create_msg(101, 100)
    msg2 = create_msg(102, 101)

    assert matches_filters(msg1, settings, set()) is True
    assert matches_filters(msg2, settings, set()) is False

def test_reply_to_multiple(base_settings):
    settings = base_settings
    settings.reply_to = {100, 200}

    msg1 = create_msg(101, 100)
    msg2 = create_msg(201, 200)
    msg3 = create_msg(301, 300)

    assert matches_filters(msg1, settings, set()) is True
    assert matches_filters(msg2, settings, set()) is True
    assert matches_filters(msg3, settings, set()) is False

def test_reply_to_none_in_msg(base_settings):
    settings = base_settings
    settings.reply_to = {100}

    msg = create_msg(101, None)

    assert matches_filters(msg, settings, set()) is False

def test_reply_to_zero_in_msg(base_settings):
    settings = base_settings
    settings.reply_to = {100}

    msg = create_msg(101, 0)

    assert matches_filters(msg, settings, set()) is False
