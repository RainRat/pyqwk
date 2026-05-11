import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters

def create_msg(text="Hello world", author="Alice", to="Bob", subject="Greetings", confnum=1, bbs_name="MyBBS"):
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto=to,
        msgfrom=author,
        msgsubject=subject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag=" ",
    )
    return ParsedMessage(
        text=text,
        msgnum=1,
        refnum=None,
        confnum=confnum,
        header=header,
        bbs_name=bbs_name,
    )

def test_body_search():
    msg = create_msg(text="The secret code is 12345")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", body_search="secret"
    )
    assert matches_filters(msg, settings, set()) is True

    settings.body_search = "missing"
    assert matches_filters(msg, settings, set()) is False

def test_exclude_search():
    msg = create_msg(text="Spam message")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", exclude_search="spam"
    )
    assert matches_filters(msg, settings, set()) is False

    settings.exclude_search = "ham"
    assert matches_filters(msg, settings, set()) is True

def test_exclude_author():
    msg = create_msg(author="Mallory")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", exclude_authors=["Mallory"]
    )
    assert matches_filters(msg, settings, set()) is False

    settings.exclude_authors = ["Alice"]
    assert matches_filters(msg, settings, set()) is True

def test_exclude_subject():
    msg = create_msg(subject="Annoying Topic")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", exclude_subjects=["annoying"]
    )
    assert matches_filters(msg, settings, set()) is False

def test_exclude_conference():
    msg = create_msg(confnum=10)
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437"
    )
    # Exclude conference 10
    assert matches_filters(msg, settings, set(), allowed_exclude_conferences={10}) is False
    assert matches_filters(msg, settings, set(), allowed_exclude_conferences={20}) is True

def test_exclude_bbs():
    msg = create_msg(bbs_name="LameBBS")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", exclude_bbs_names=["lame"]
    )
    assert matches_filters(msg, settings, set()) is False

def test_combined_inclusion_exclusion():
    msg = create_msg(text="Good content", author="Alice")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", authors=["Alice"], exclude_search="content"
    )
    # Matches author Alice (inclusion) BUT matches "content" (exclusion). Exclusion wins.
    assert matches_filters(msg, settings, set()) is False

    settings.exclude_search = "spam"
    # Matches author Alice, no exclusion.
    assert matches_filters(msg, settings, set()) is True
