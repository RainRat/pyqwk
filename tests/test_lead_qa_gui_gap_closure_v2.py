import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def mock_app():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.messages = []
            app.search_var = MagicMock()
            app.exclude_var = MagicMock()
            app.bbs_combo = MagicMock()
            app.conf_combo = MagicMock()
            app.private_var = MagicMock()
            app.has_attach_var = MagicMock()
            app.mine_var = MagicMock()
            app.on_this_day_var = MagicMock()
            app.has_links_var = MagicMock()
            app.has_emails_var = MagicMock()
            app.has_phones_var = MagicMock()
            app.has_ansi_var = MagicMock()
            app.has_msg_links_var = MagicMock()
            app.search_entry = MagicMock()
            app.exclude_entry = MagicMock()
            app.detail_text = MagicMock()
            app.message_list = MagicMock()
            app._search_matches = []
            app._current_match_idx = -1
            app.search_count_label = MagicMock()
            return app

def test_is_any_filter_active_gaps(mock_app):
    """Cover lines 378, 390, 393 in pyqwk/gui.py."""
    app = mock_app
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"
    app.private_var.get.return_value = True
    for var in [app.has_attach_var, app.mine_var, app.on_this_day_var, app.has_links_var,
                app.has_emails_var, app.has_phones_var, app.has_ansi_var, app.has_msg_links_var]:
        var.get.return_value = False

    # Initially False
    assert app._is_any_filter_active() is False

    # Line 378: Conference filter active
    app.conf_combo.get.return_value = "1: General"
    assert app._is_any_filter_active() is True
    app.conf_combo.get.return_value = "All Conferences"

    # Line 390: Boolean filter active (e.g. mine)
    app.mine_var.get.return_value = True
    assert app._is_any_filter_active() is True
    app.mine_var.get.return_value = False

    # Line 393: Private toggle inactive (showing all)
    app.private_var.get.return_value = False
    assert app._is_any_filter_active() is True

def test_navigate_conference_empty_values(mock_app):
    """Cover line 790 in pyqwk/gui.py."""
    app = mock_app
    app.conf_combo.__getitem__.return_value = [] # values
    app._navigate_conference(1)
    app.conf_combo.current.assert_not_called()

def test_navigate_conference_no_selection_wrap(mock_app):
    """Cover line 796 in pyqwk/gui.py."""
    app = mock_app
    app.conf_combo.__getitem__.return_value = ["A", "B", "C"] # values
    app.conf_combo.current.return_value = -1 # No selection
    app.root.focus_get.return_value = None

    with patch.object(app, "reload_messages"):
        # Wrap to last if delta < 0
        app._navigate_conference(-1)
        app.conf_combo.current.assert_called_with(2)

def test_on_space_pressed_scrolling_gaps(mock_app):
    """Cover lines 815, 825 (middle of page scrolling) in pyqwk/gui.py."""
    app = mock_app
    app.root.focus_get.return_value = None

    # Forward scroll (line 815)
    app.detail_text.yview.return_value = (0.0, 0.5)
    event = MagicMock()
    event.keysym = "space"
    event.state = 0 # No shift
    assert app._on_space_pressed(event) == "break"
    app.detail_text.yview_scroll.assert_called_with(1, "pages")

    # Backward scroll (line 825)
    app.detail_text.yview.return_value = (0.5, 1.0)
    event.keysym = "BackSpace"
    assert app._on_space_pressed(event) == "break"
    app.detail_text.yview_scroll.assert_called_with(-1, "pages")

def test_on_space_pressed_focus_ignored(mock_app):
    """Cover line 807/830 (focused search/exclude) in pyqwk/gui.py."""
    app = mock_app
    app.root.focus_get.return_value = app.search_entry
    event = MagicMock()
    assert app._on_space_pressed(event) is None

def test_block_text_input_brackets(mock_app):
    """Cover lines 499-503 in pyqwk/gui.py."""
    app = mock_app
    event = MagicMock()
    event.state = 0

    with patch.object(app, "_navigate_conference") as mock_nav:
        event.keysym = "bracketleft"
        event.char = "["
        assert app._block_text_input(event) == "break"
        mock_nav.assert_called_with(-1)

        event.keysym = "bracketright"
        event.char = "]"
        assert app._block_text_input(event) == "break"
        mock_nav.assert_called_with(1)

def test_pivot_filter_subject_exclude_gaps(mock_app):
    """Cover lines 443, 463, 466, 469 in pyqwk/gui.py."""
    app = mock_app
    with patch.object(app, "reload_messages"):
        # Subject (line 443)
        app._pivot_filter(subject="Re: Test Subject")
        app.search_var.set.assert_called_with("test subject")

        # Exclude Subject (line 463)
        app._pivot_filter(exclude_subject="Fwd: Hidden")
        app.exclude_var.set.assert_called_with("hidden")

        # Exclude BBS (line 466)
        app._pivot_filter(exclude_bbs_name="Old BBS")
        app.exclude_var.set.assert_called_with("Old BBS")

        # Exclude Conf Num (line 469)
        app._pivot_filter(exclude_conf_num=123)
        app.exclude_var.set.assert_called_with("123")
