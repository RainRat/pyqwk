
import sys
import re
from pyqwk.core import _highlight_text, MessageHeader

def test_highlight_text_no_colors():
    text = "Hello world"
    # Should return original text if use_colors is False
    assert _highlight_text(text, "world", use_colors=False) == text

def test_highlight_text_basic():
    text = "Hello world"
    highlighted = _highlight_text(text, "world", use_colors=True)
    assert highlighted == "Hello \x1b[7mworld\x1b[0m"

def test_highlight_text_case_insensitive():
    text = "Hello World"
    highlighted = _highlight_text(text, "world", use_colors=True)
    assert highlighted == "Hello \x1b[7mWorld\x1b[0m"

def test_highlight_text_regex():
    text = "The price is $100"
    highlighted = _highlight_text(text, r"\$\d+", is_regex=True, use_colors=True)
    assert highlighted == "The price is \x1b[7m$100\x1b[0m"

def test_header_format_text_colors():
    header = MessageHeader(
        status=' ', msgnum=123, msgdate='01-01-23', msgtime='12:00',
        msgto='Alice', msgfrom='Bob', msgsubject='Testing',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )

    formatted = header.format_text(
        board_dict={1: "General"},
        verbose=False,
        include_separator=False,
        use_colors=True,
        highlight_term="Bob"
    )

    # Check for bold label and highlighted value
    assert "\x1b[1mFrom: \x1b[0m" in formatted
    assert "\x1b[7mBob\x1b[0m" in formatted
    assert "\x1b[1mSubject: \x1b[0mTesting" in formatted

def test_highlight_text_no_term():
    text = "Hello world"
    assert _highlight_text(text, None, use_colors=True) == text
    assert _highlight_text(text, "", use_colors=True) == text

def test_highlight_text_invalid_regex():
    text = "Hello world"
    # Invalid regex should return original text
    assert _highlight_text(text, "[", is_regex=True, use_colors=True) == text
