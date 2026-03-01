import pytest
from pyqwk.core import MessageHeader

def test_oneline_alignment_long_names():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="A Very Long Author Name That Should Be Truncated",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    board_dict = {1: "A Very Long Conference Name That Should Also Be Truncated"}

    oneline = header.format_oneline(board_dict)

    # Expected truncation:
    # Conf: "A Very Long Conf" (16 chars)
    # From: "A Very Long Author N" (20 chars)
    # Date: "01-01-24 12:00" (14 chars)

    assert "A Very Long Conf " in oneline
    assert "01-01-24 12:00 " in oneline
    assert "A Very Long Author N " in oneline

    # Check total length of fixed parts
    # msgnum_part: ""
    # conf_part: 16
    # space: 1
    # date_part: 14
    # space: 1
    # from_part: 20
    # space: 1
    # total before subject: 16+1+14+1+20+1 = 53

    prefix = oneline[:53]
    assert len(prefix) == 53
    assert prefix.endswith("A Very Long Author N ")

def test_oneline_alignment_with_highlighting():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author Name",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    board_dict = {1: "Conference"}

    # Highlight "Auth"
    oneline = header.format_oneline(
        board_dict,
        use_colors=True,
        highlight_term="Auth"
    )

    # ANSI escape for reverse video is \x1b[7m and reset is \x1b[0m
    assert "\x1b[7mAuthor\x1b[0m Name" not in oneline # Wait, "Author" contains "Auth"
    # Actually _highlight_text highlights exact matches or regex
    # If highlight_term is "Auth", it highlights "Auth"
    assert "\x1b[7mAuth\x1b[0m" in oneline

    # Even with ANSI codes, the spacing should be preserved.
    # The prepare_field function calculates display_len WITHOUT the ANSI codes
    # because it truncates first, then highlights, but it adds padding based on display_len.

    # "Author Name" is 11 chars. Truncated to 20 is still 11 chars.
    # display_len = 11.
    # Highlighted "Auth" -> "\x1b[7mAuth\x1b[0mor Name"
    # Padding = 20 - 11 = 9 spaces.

    assert "Author Name         " in oneline.replace("\x1b[7m", "").replace("\x1b[0m", "")

    # Check the whole line structure
    plain_line = oneline.replace("\x1b[7m", "").replace("\x1b[0m", "")
    # Conf (16) + space (1) + Date (14) + space (1) + From (20) + space (1) + Subject
    # "Conference      " (16)
    # "01-01-24 12:00 " (14+1)
    # "Author Name         " (20)
    # " " (1)
    # "Subject"

    expected_start = "Conference       01-01-24 12:00 Author Name          Subject"
    assert plain_line.startswith(expected_start)
