from pyqwk.core import _linkify_text, MessageHeader


def test_highlight_text_no_colors():
    text = "Hello world"
    # Should return original text if use_colors is False
    assert _linkify_text(text, "ansi", search_term="world", use_colors=False) == text


def test_highlight_text_basic():
    text = "Hello world"
    highlighted = _linkify_text(text, "ansi", search_term="world", use_colors=True)
    assert highlighted == "Hello \x1b[7mworld\x1b[0m"


def test_highlight_text_case_insensitive():
    text = "Hello World"
    highlighted = _linkify_text(text, "ansi", search_term="world", use_colors=True)
    assert highlighted == "Hello \x1b[7mWorld\x1b[0m"


def test_highlight_text_regex():
    text = "The price is $100"
    highlighted = _linkify_text(text, "ansi", search_term=r"\$\d+", is_regex=True, use_colors=True)
    assert highlighted == "The price is \x1b[7m$100\x1b[0m"


def test_header_format_text_colors():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Testing",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )

    formatted = header.format_text(
        board_dict={1: "General"},
        verbose=False,
        include_separator=False,
        use_colors=True,
        highlight_term="Bob",
    )

    # Check for dim/grey label and highlighted value
    assert "\x1b[90mFrom:           \x1b[0m" in formatted
    assert "\x1b[7mBob\x1b[0m" in formatted
    assert "\x1b[90mSubject:        \x1b[0mTesting" in formatted


def test_highlight_text_no_term():
    text = "Hello world"
    assert _linkify_text(text, "ansi", search_term=None, use_colors=True) == text
    assert _linkify_text(text, "ansi", search_term="", use_colors=True) == text


def test_highlight_text_invalid_regex():
    text = "Hello world"
    # Invalid regex should return original text
    assert _linkify_text(text, "ansi", search_term="[", is_regex=True, use_colors=True) == text
