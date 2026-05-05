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


@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    # Mock search_var as it's initialized with tk.StringVar()
    with patch("tkinter.StringVar"), patch("tkinter.BooleanVar"):
        app = QwkGuiApp(root)
        app.search_var = MagicMock()
        return app


def test_search_from_selection_logic(app):
    """Verify that _search_from_selection correctly updates search_var and reloads."""
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ("1.0", "1.5")
    app.detail_text.get.return_value = " BBS "
    app.reload_messages = MagicMock()
    app.message_list = MagicMock()

    app._search_from_selection()

    app.search_var.set.assert_called_once_with("BBS")
    app.reload_messages.assert_called_once()
    app.message_list.focus_set.assert_called_once()


def test_search_from_selection_empty(app):
    """Verify that _search_from_selection does nothing if no text is selected."""
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ()
    app.reload_messages = MagicMock()

    app._search_from_selection()

    app.search_var.set.assert_not_called()
    app.reload_messages.assert_not_called()


def test_show_text_context_menu_with_selection(app):
    """Verify that the context menu includes the Search option when text is selected."""
    event = MagicMock(x_root=100, y_root=100)
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ("1.0", "1.10")
    app.detail_text.get.return_value = "Selected Text"

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_text_context_menu(event)

        # Check that add_command was called with the search label
        calls = mock_menu_instance.add_command.call_args_list
        labels = [c[1].get("label", "") for c in calls]
        assert "Search for 'Selected Text'" in labels


def test_show_text_context_menu_with_long_selection(app):
    """Verify that the context menu truncates long selected text."""
    event = MagicMock(x_root=100, y_root=100)
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ("1.0", "1.50")
    app.detail_text.get.return_value = (
        "This is a very long selection that should be truncated"
    )

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_text_context_menu(event)

        calls = mock_menu_instance.add_command.call_args_list
        labels = [c[1].get("label", "") for c in calls]
        expected_label = "Search for 'This is a very long ...'"
        assert expected_label in labels


def test_show_text_context_menu_no_selection(app):
    """Verify that the context menu excludes the Search option when no text is selected."""
    event = MagicMock(x_root=100, y_root=100)
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ()

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_text_context_menu(event)

        calls = mock_menu_instance.add_command.call_args_list
        labels = [c[1].get("label", "") for c in calls]
        for label in labels:
            assert "Search for" not in label
