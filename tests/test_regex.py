from pyqwk.core import ProcessingSettings, ParsedMessage, MessageHeader, matches_filters

def test_matches_filters_regex():
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate='01-01-23',
        msgtime='12:00',
        msgto='Alice',
        msgfrom='Bob Smith',
        msgsubject='Hello World',
        msgpassword='',
        refnum=0,
        numblocks=1,
        msgflag='',
        confnum=1,
        lognum=0,
        nettag=''
    )
    message = ParsedMessage(
        text="This is a test message about BBS systems.",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header
    )

    # Base settings
    base_settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='auto', output_mode='stdout',
        output_path=None, encoding='cp437'
    )

    # 1. Regex match on Author
    settings = base_settings
    settings.regex = True
    settings.authors = ["Bob.*"]
    assert matches_filters(message, settings, set()) is True

    # 2. Regex non-match on Author
    settings.authors = ["^Alice"]
    assert matches_filters(message, settings, set()) is False

    # 3. Regex match on Subject
    settings.authors = None
    settings.subjects = [".*World$"]
    assert matches_filters(message, settings, set()) is True

    # 4. Regex match on Body (Search term)
    settings.subjects = None
    settings.search_term = "BBS [a-z]+"
    assert matches_filters(message, settings, set()) is True

    # 5. Invalid Regex (should not crash, should just not match)
    settings.search_term = "["
    assert matches_filters(message, settings, set()) is False

def test_normal_substring_still_works():
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate='01-01-23',
        msgtime='12:00',
        msgto='Alice',
        msgfrom='Bob Smith',
        msgsubject='Hello World',
        msgpassword='',
        refnum=0,
        numblocks=1,
        msgflag='',
        confnum=1,
        lognum=0,
        nettag=''
    )
    message = ParsedMessage(
        text="This is a test message about BBS systems.",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header
    )

    base_settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='auto', output_mode='stdout',
        output_path=None, encoding='cp437', regex=False
    )

    settings = base_settings
    settings.authors = ["Bob"]
    assert matches_filters(message, settings, set()) is True

    settings.authors = ["Alice"]
    assert matches_filters(message, settings, set()) is False
