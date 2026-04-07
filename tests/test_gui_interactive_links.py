
import sys
from unittest.mock import MagicMock, patch

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

import pytest
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    with patch('tkinter.StringVar'), patch('tkinter.BooleanVar'):
        app = QwkGuiApp(root)
        app.search_var = MagicMock()
        app.search_var.get.return_value = ""
        app.regex_var = MagicMock()
        app.regex_var.get.return_value = False
        return app

def test_render_message_interactive_links(app):
    """Verify that URLs, emails, and phone numbers are correctly linkified in the detail view."""
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='Recipient', msgfrom='Sender', msgsubject='Test Links',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )
    # Body containing URL, Email, and Phone
    body = "Check https://example.com or mail me at test@example.com or call 555-1234."
    app.messages = [ParsedMessage(text=body, msgnum=1, refnum=None, confnum=1, header=header)]
    app.board_dict = {1: "General"}

    with patch("webbrowser.open") as mock_open:
        app._render_message(0)

        # Check for correct tag bindings
        # We need to find the calls to tag_bind
        bind_calls = app.detail_text.tag_bind.call_args_list

        # Verify URL binding
        url_tags = [c[0][0] for c in bind_calls if c[0][0].startswith("url_")]
        assert len(url_tags) > 0

        # Verify Email binding
        email_tags = [c[0][0] for c in bind_calls if c[0][0].startswith("email_")]
        assert len(email_tags) > 0

        # Verify Phone binding
        phone_tags = [c[0][0] for c in bind_calls if c[0][0].startswith("phone_")]
        assert len(phone_tags) > 0

        # Simulate clicks
        # URL
        url_cmd = next(c[0][2] for c in bind_calls if c[0][0] == url_tags[0])
        url_cmd(MagicMock())
        mock_open.assert_any_call("https://example.com")

        # Email
        email_cmd = next(c[0][2] for c in bind_calls if c[0][0] == email_tags[0])
        email_cmd(MagicMock())
        mock_open.assert_any_call("mailto:test@example.com")

        # Phone
        phone_cmd = next(c[0][2] for c in bind_calls if c[0][0] == phone_tags[0])
        phone_cmd(MagicMock())
        mock_open.assert_any_call("tel:5551234")

def test_render_message_overlapping_entities(app):
    """Verify that overlapping entities are handled correctly (longer match preferred)."""
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='Recipient', msgfrom='Sender', msgsubject='Overlap',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )
    # A phone number that might also look like a date or something else if patterns were different
    # But here we just want to ensure if multiple regexes match, we don't double-insert.
    # Current regex for phone: r'\d{3}[-\.\s]?\d{4}'
    # Current regex for email: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'

    body = "Call 123-4567 or email user@example.com"
    app.messages = [ParsedMessage(text=body, msgnum=1, refnum=None, confnum=1, header=header)]
    app.board_dict = {1: "General"}

    app._render_message(0)

    # Verify that total text inserted (after header) matches body
    # (Excluding headers and newlines between header and body)
    inserted_text = "".join(call[0][1] for call in app.detail_text.insert.call_args_list)
    assert "123-4567" in inserted_text
    assert "user@example.com" in inserted_text
    # Ensure no duplicates (very rough check)
    assert inserted_text.count("123-4567") == 1
    assert inserted_text.count("user@example.com") == 1
