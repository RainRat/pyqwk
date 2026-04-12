import sys
from unittest.mock import MagicMock, patch
import pytest
import tkinter as tk

# Mock tkinter for GUI tests
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    _reconstruct_archive_information
)
from pyqwk.gui import QwkGuiApp

def test_reconstruct_archive_information_upgrade_default_name():
    """Test that a descriptive conference name replaces the 'Conference X' default."""
    h1 = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='All', msgfrom='User', msgsubject='Subj',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=42, lognum=1, nettag=''
    )
    # Message 1 has no confname, will trigger default "Conference 42"
    m1 = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=42, header=h1, confname=None)

    # Message 2 has a descriptive name
    m2 = ParsedMessage(text="Body", msgnum=2, refnum=None, confnum=42, header=h1, confname="The Answer")

    board_dict = _reconstruct_archive_information([m1, m2])
    assert board_dict[42] == "The Answer"

@pytest.fixture
def mock_gui():
    # Ensure fresh mocks for each test
    mock_tk.Text.return_value = MagicMock()
    mock_tk.Canvas.return_value = MagicMock()
    mock_ttk.Treeview.return_value = MagicMock()
    mock_ttk.Combobox.return_value = MagicMock()

    root = MagicMock()
    root.after = MagicMock()
    with patch('tkinter.StringVar'), patch('tkinter.BooleanVar'), patch('tkinter.IntVar'):
        app = QwkGuiApp(root)
        app.search_var = MagicMock()
        app.search_var.get.return_value = ""
        app.regex_var = MagicMock()
        app.regex_var.get.return_value = False
        return app

def test_gui_render_overlapping_entities(mock_gui):
    """Verify that overlapping entities are skipped (line 896 in gui.py)."""
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='Recipient', msgfrom='Sender', msgsubject='Overlap',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )
    # This string contains something that matches both URL and Phone
    # www.example.com/123-4567
    # URL: matches full string
    # Phone: matches 123-4567
    body = "Check www.example.com/123-4567 for info"
    mock_gui.messages = [ParsedMessage(text=body, msgnum=1, refnum=None, confnum=1, header=header)]
    mock_gui.board_dict = {1: "General"}

    # Reset mock to avoid interference from other tests sharing the same mocked detail_text
    mock_gui.detail_text.tag_bind.reset_mock()

    mock_gui._render_message(0)

    # We expect only one entity to be inserted (the longer URL)
    # Check tag_bind calls to see how many entities were made interactive.
    # Each entity calls tag_bind 3 times (Button-1, Enter, Leave).
    bind_calls = mock_gui.detail_text.tag_bind.call_args_list
    url_tags = [c[0][0] for c in bind_calls if c[0][0].startswith("url_")]
    phone_tags = [c[0][0] for c in bind_calls if c[0][0].startswith("phone_")]

    # Check unique tags to ensure only one entity was processed
    assert len(set(url_tags)) == 1
    assert len(set(phone_tags)) == 0 # Should have been skipped due to overlap

    # Branch coverage: line 899 (start == last_idx, so text before entity is empty)
    # We'll use a string where entity starts at the very beginning of the line.
    mock_gui.detail_text.insert.reset_mock()
    body2 = "www.example.com"
    mock_gui.messages = [ParsedMessage(text=body2, msgnum=2, refnum=None, confnum=1, header=header)]
    mock_gui._render_message(0)
    # The first insert should be the entity, not a text before it.
    # Looking at _render_message, it inserts header first.
    # Body is after two newlines (lines 871, 872)
    # Let's just check that no empty strings were inserted for body parts
    body_inserts = [c[0][1] for c in mock_gui.detail_text.insert.call_args_list if c[0][1] == ""]
    assert len(body_inserts) == 0

def test_gui_navigate_search_matches_empty(mock_gui):
    """Verify early return when navigating with no search matches (line 977 in gui.py)."""
    mock_gui._search_matches = []

    # This should return immediately and NOT call tag_remove
    mock_gui._navigate_search_matches(1)

    mock_gui.detail_text.tag_remove.assert_not_called()
