import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch, ANY
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_app():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.detail_text = MagicMock()
            app.search_var = MagicMock()
            app.regex_var = MagicMock()
            app.bbs_combo = MagicMock()
            app.conf_combo = MagicMock()
            app.min_words_var = MagicMock()
            app.max_words_var = MagicMock()
            app.private_var = MagicMock()
            app.has_attach_var = MagicMock()
            app.mine_var = MagicMock()
            app.on_this_day_var = MagicMock()
            app.has_links_var = MagicMock()
            app.has_emails_var = MagicMock()
            app.has_phones_var = MagicMock()
            app.has_ansi_var = MagicMock()
            app.has_msg_links_var = MagicMock()
            app.search_count_label = MagicMock()
            # Ensure reload_messages is a MagicMock so we can use assert_called_once
            app.reload_messages = MagicMock()
            return app

def test_render_empty_state_private_hidden(mock_app):
    """Cover line 656 in pyqwk/gui.py."""
    app = mock_app
    app.private_var.get.return_value = False # Private Hidden
    app.search_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"
    app.min_words_var.get.return_value = ""
    app.max_words_var.get.return_value = ""

    # Other boolean filters set to False
    for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                app.has_links_var, app.has_emails_var, app.has_phones_var,
                app.has_ansi_var, app.has_msg_links_var]:
        var.get.return_value = False

    with patch.object(app, "_update_status_bar"), patch.object(app, "_render_hr"):
        app._render_empty_state()

    # Verify "Private Hidden" was appended to active_bools and inserted
    # Use ANY for tk.END to avoid MagicMock comparison issues
    app.detail_text.insert.assert_any_call(ANY, "Private Hidden\n", "body")

def test_reset_bbs_filter_exception(mock_app):
    """Cover lines 914-915 in pyqwk/gui.py."""
    app = mock_app
    app.bbs_combo.current.side_effect = Exception("Tcl Error")

    app._reset_bbs_filter()

    app.bbs_combo.set.assert_called_with("All BBSes")
    app.reload_messages.assert_called_once()

def test_reset_conf_filter_exception(mock_app):
    """Cover lines 922-923 in pyqwk/gui.py."""
    app = mock_app
    app.conf_combo.current.side_effect = Exception("Tcl Error")

    app._reset_conf_filter()

    app.conf_combo.set.assert_called_with("All Conferences")
    app.reload_messages.assert_called_once()

def test_focus_entry_field_missing_attribute(mock_app):
    """Cover line 930 in pyqwk/gui.py."""
    app = mock_app
    # Call with attribute that doesn't exist on app
    app._focus_entry_field("non_existent_entry", "some_var")
    # Should return early without doing anything
    app.detail_text.tag_ranges.assert_not_called()

def test_reset_visibility_filters(mock_app):
    """Test that _reset_visibility_filters correctly resets all nine variables and reloads messages."""
    app = mock_app

    # Run the reset method
    app._reset_visibility_filters()

    # Check that all nine visibility variables were set to their defaults
    app.private_var.set.assert_called_with(True)
    app.has_attach_var.set.assert_called_with(False)
    app.mine_var.set.assert_called_with(False)
    app.on_this_day_var.set.assert_called_with(False)
    app.has_links_var.set.assert_called_with(False)
    app.has_emails_var.set.assert_called_with(False)
    app.has_phones_var.set.assert_called_with(False)
    app.has_ansi_var.set.assert_called_with(False)
    app.has_msg_links_var.set.assert_called_with(False)

    # And that reload_messages was called
    app.reload_messages.assert_called_once()
