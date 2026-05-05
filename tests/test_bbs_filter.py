from dataclasses import replace
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters


def test_bbs_filter():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subj",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )

    msg1 = ParsedMessage(
        text="Hello",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        bbs_name="Vintage BBS",
        bbs_id="VINTAGE",
    )

    msg2 = ParsedMessage(
        text="World",
        msgnum=2,
        refnum=None,
        confnum=1,
        header=header,
        bbs_name="Other BBS",
        bbs_id="OTHER",
    )

    # Base settings
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
    )

    # Filter by name
    settings_name = replace_settings(settings, bbs_names=["Vintage"])
    assert matches_filters(msg1, settings_name, set()) is True
    assert matches_filters(msg2, settings_name, set()) is False

    # Filter by ID
    settings_id = replace_settings(settings, bbs_names=["OTHER"])
    assert matches_filters(msg1, settings_id, set()) is False
    assert matches_filters(msg2, settings_id, set()) is True

    # Filter by either (multi)
    settings_multi = replace_settings(settings, bbs_names=["Vintage", "OTHER"])
    assert matches_filters(msg1, settings_multi, set()) is True
    assert matches_filters(msg2, settings_multi, set()) is True


def replace_settings(settings, **kwargs):
    return replace(settings, **kwargs)
