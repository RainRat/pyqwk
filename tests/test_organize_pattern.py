import os
from pyqwk.core import _get_organization_subpath, ParsedMessage, MessageHeader, ProcessingSettings

def test_organize_pattern_basic():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-02-23", msgtime="12:34",
        msgto="All", msgfrom="Author Name", msgsubject="Test Subject",
        msgpassword="", refnum=0, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(
        text="Body", msgnum=1, refnum=0, confnum=1, header=header,
        confname="General", bbs_name="The BBS"
    )

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="file", output_path="out",
        encoding="cp437", organize_pattern="{year}/{month}/{author}"
    )

    subpath = _get_organization_subpath(msg, settings)
    # 01-02-23 -> 2023 / 01 / author_name
    expected = os.path.join("2023", "01", "author_name")
    assert subpath == expected

def test_organize_pattern_slashes():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-02-23", msgtime="12:34",
        msgto="All", msgfrom="Author", msgsubject="Subject",
        msgpassword="", refnum=0, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(
        text="Body", msgnum=1, refnum=0, confnum=1, header=header,
        confname="General"
    )

    # Test both forward and backward slashes in pattern
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="file", output_path="out",
        encoding="cp437", organize_pattern="archives\\{confname}/{year}"
    )

    subpath = _get_organization_subpath(msg, settings)
    expected = os.path.join("archives", "general", "2023")
    assert subpath == expected

def test_organize_pattern_invalid_variable():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-02-23", msgtime="12:34",
        msgto="All", msgfrom="Author", msgsubject="Subject",
        msgpassword="", refnum=0, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(
        text="Body", msgnum=1, refnum=0, confnum=1, header=header
    )

    # Invalid variable {nonexistent} should fall back to standard organization
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="file", output_path="out",
        encoding="cp437", organize_pattern="{nonexistent}", organize=True
    )

    subpath = _get_organization_subpath(msg, settings)
    # Fallback to organize (by conference): 001-unknown (since confname is None)
    assert "001-unknown" in subpath

def test_organize_pattern_sanitization():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-02-23", msgtime="12:34",
        msgto="All", msgfrom="Author / Path", msgsubject="Subj",
        msgpassword="", refnum=0, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(
        text="Body", msgnum=1, refnum=0, confnum=1, header=header
    )

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=True, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="file", output_path="out",
        encoding="cp437", organize_pattern="users/{author}"
    )

    subpath = _get_organization_subpath(msg, settings)
    # "Author / Path" should be slugified to "author_path"
    expected = os.path.join("users", "author_path")
    assert subpath == expected
