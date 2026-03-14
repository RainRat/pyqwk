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

    # Expected truncation (New widths):
    # Conf: "A Very Long " (12 chars)
    # Date: "01-01-24 12:00" (14 chars)
    # From: "A Very Long Aut" (15 chars)
    # To:   "Recipient      " (15 chars)

    assert "A Very Long  " in oneline
    assert "01-01-24 12:00 " in oneline
    assert "A Very Long Aut" in oneline
    assert "Recipient      " in oneline

    # Check total length of fixed parts
    # msgnum_part: ""
    # conf_part: 12
    # space: 1
    # date_part: 14
    # space: 1
    # from_part: 15
    # space: 1
    # to_part: 15
    # space: 1
    # total before subject: 12+1+14+1+15+1+15+1 = 60

    prefix = oneline[:60]
    assert len(prefix) == 60
    assert prefix.endswith("Recipient       ")

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

    # "Author Name" is 11 chars. Truncated to 15 is still 11 chars.
    # display_len = 11.
    # Highlighted "Auth" -> "\x1b[7mAuth\x1b[0mor Name"
    # Padding = 15 - 11 = 4 spaces.

    assert "Author Name    " in oneline.replace("\x1b[7m", "").replace("\x1b[0m", "")

    # Check the whole line structure
    plain_line = oneline.replace("\x1b[7m", "").replace("\x1b[0m", "")
    # Conf (12) + space (1) + Date (14) + space (1) + From (15) + space (1) + To (15) + space (1) + Subject
    # "Conference  " (12)
    # "01-01-24 12:00 " (14+1)
    # "Author Name    " (15)
    # "Recipient      " (15)
    # " " (1)
    # "Subject"

    expected_start = "Conference   01-01-24 12:00 Author Name     Recipient       Subject"
    assert plain_line.startswith(expected_start)

def test_threaded_oneline_indentation():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Threaded Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    board_dict = {1: "Conference"}

    # Depth 1: Subject should start with "└ "
    oneline_d1 = header.format_oneline(board_dict, depth=1)
    assert "└ Threaded Subject" in oneline_d1
    # Verify metadata alignment (should be the same as depth 0)
    # 12 (Conf) + 1 + 14 (Date) + 1 + 15 (From) + 1 + 15 (To) + 1 = 60 chars before subject
    prefix_d1 = oneline_d1[:60]
    assert prefix_d1 == "Conference   01-01-24 12:00 Author          Recipient       "
    assert oneline_d1[60:].startswith("└ Threaded Subject")

    # Depth 2: Subject should start with "  └ "
    oneline_d2 = header.format_oneline(board_dict, depth=2)
    assert "  └ Threaded Subject" in oneline_d2
    # Verify metadata alignment remains consistent
    prefix_d2 = oneline_d2[:60]
    assert prefix_d2 == "Conference   01-01-24 12:00 Author          Recipient       "
    assert oneline_d2[60:].startswith("  └ Threaded Subject")
