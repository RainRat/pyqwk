import sys
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter and related modules before importing QwkGuiApp
mock_tk = MagicMock()
mock_ttk = MagicMock()
mock_msgbox = MagicMock()
mock_simpledialog = MagicMock()

sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.messagebox"] = mock_msgbox
sys.modules["tkinter.simpledialog"] = mock_simpledialog

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def app():
    root = MagicMock()
    with patch("pyqwk.gui.tk") as m_tk, patch("pyqwk.gui.ttk") as m_ttk, patch("pyqwk.gui.simpledialog"), patch("pyqwk.gui.messagebox"):
        m_tk.BooleanVar.side_effect = lambda *a, **kw: MagicMock()
        m_tk.StringVar.side_effect = lambda *a, **kw: MagicMock()

        # Ensure different widgets are returned for different calls
        m_ttk.Combobox.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Entry.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Label.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Button.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Checkbutton.side_effect = lambda *a, **kw: MagicMock()

        app = QwkGuiApp(root)
        app.current_paths = ["test.qwk"]

        # Setup default "inactive" state for filters
        app.search_var.get.return_value = ""
        app.exclude_var.get.return_value = ""
        app.min_words_var.get.return_value = ""
        app.max_words_var.get.return_value = ""

        # bbs_combo and conf_combo are mocked widgets
        app.bbs_combo.get.return_value = "All BBSes (100)"
        app.conf_combo.get.return_value = "All Conferences (100)"

        # Ensure we don't accidentally match the other one
        app.bbs_combo.get.side_effect = None

        # Ensure all checkbutton vars return False for inactive
        app.has_attach_var.get.return_value = False
        app.mine_var.get.return_value = False
        app.on_this_day_var.get.return_value = False
        app.has_links_var.get.return_value = False
        app.has_emails_var.get.return_value = False
        app.has_phones_var.get.return_value = False
        app.has_ansi_var.get.return_value = False
        app.has_msg_links_var.get.return_value = False

        # Private filter is active if False, inactive if True
        app.private_var.get.return_value = True

        # Populate messages
        h1 = MessageHeader(" ", 101, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, "")
        app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]

        # Mock Treeview methods
        app.message_list.selection.return_value = []
        app.message_list.exists.return_value = True

        return app

def test_prompt_jump_to_message_filters_inactive_not_found(app):
    # Ensure filters are inactive
    assert app._is_any_filter_active() is False

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.askyesno") as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        app.prompt_jump_to_message()

    mock_ask.assert_not_called()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]

def test_prompt_jump_to_message_filters_active_user_declines_reset(app):
    # Activate a filter
    app.search_var.get.return_value = "something"
    assert app._is_any_filter_active() is True

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        app.prompt_jump_to_message()

    mock_ask.assert_called_once()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]

def test_jump_to_message_filters_active_user_declines_reset(app):
    # Activate a filter
    app.search_var.get.return_value = "something"

    with (
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        # Try to jump to a message that doesn't exist (msgnum 999 in conf 1)
        app.jump_to_message(1, 999)

    mock_ask.assert_called_once()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]

def test_jump_to_message_specific_conf_fallback_fix(app):
    """Verify that jumping to msgnum in Conf A doesn't find it in Conf B and instead prompts for reset."""
    # Message 101 is in Conf 1
    # Try to jump to Message 101 in Conf 2

    # Activate a filter so we get the reset prompt if not found
    app.search_var.get.return_value = "something"

    with (
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        app.jump_to_message(2, 101)

    # Before fix, it would have found 101 in Conf 1 and NOT prompted.
    # Now it should NOT find it in Conf 2 and prompt for reset.
    mock_ask.assert_called_once()
    mock_info.assert_called_once()
