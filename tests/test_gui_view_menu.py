import sys
from unittest.mock import MagicMock, patch

# Mock tkinter before importing pyqwk.gui
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
def app_with_mocks():
    root = MagicMock()
    root.after = MagicMock()
    # Mock StringVar and BooleanVar
    with patch("tkinter.StringVar"), patch("tkinter.BooleanVar"):
        app = QwkGuiApp(root)
        app.threaded_var = MagicMock()
        app.clean_var = MagicMock()
        app.wrap_var = MagicMock()
        return app


def test_alt_key_underlines(app_with_mocks):
    """Test that underlines are correctly configured on File, Edit, and View cascades."""
    root = MagicMock()
    mock_menu_class = MagicMock()

    with patch("pyqwk.gui.tk.Menu", mock_menu_class):
        app = QwkGuiApp(root)

        # We expect Menu instances: menubar, file_menu, edit_menu, view_menu
        assert mock_menu_class.call_count >= 4

        # Verify cascades added with underlines
        menubar_instance = mock_menu_class.return_value
        cascade_calls = menubar_instance.add_cascade.call_args_list

        labels = [call[1].get("label") for call in cascade_calls if "label" in call[1]]

        assert "File" in labels
        assert "Edit" in labels
        assert "View" in labels

        # Every added cascade has underline=0
        for call in cascade_calls:
            if "label" in call[1] and call[1]["label"] in ("File", "Edit", "View"):
                assert call[1].get("underline") == 0


def test_view_menu_items(app_with_mocks):
    """Verify checkbuttons exist in the View menu."""
    root = MagicMock()
    mock_menu_instance = MagicMock()

    with patch("pyqwk.gui.tk.Menu", return_value=mock_menu_instance):
        app = QwkGuiApp(root)

        # View menu items are added via add_checkbutton
        checkbutton_calls = mock_menu_instance.add_checkbutton.call_args_list
        labels = [call[1].get("label") for call in checkbutton_calls if "label" in call[1]]

        assert "Conversations (Threaded)" in labels
        assert "Clean View" in labels
        assert "Wrap Text" in labels
        assert "Remove Colors" in labels
        assert "Hide Personal Info" in labels
        assert "Embed Attachments" in labels


def test_toggle_shortcuts_without_focus(app_with_mocks):
    """Verify that toggle functions work when focus is on a non-text widget."""
    mock_focus = MagicMock()
    mock_focus.winfo_class.return_value = "Label"
    app_with_mocks.root.focus_get.return_value = mock_focus
    app_with_mocks.reload_messages = MagicMock()
    app_with_mocks._update_wrap = MagicMock()

    # Test toggle threaded
    app_with_mocks.threaded_var.get.return_value = False
    res = app_with_mocks._toggle_threaded()
    app_with_mocks.threaded_var.set.assert_called_with(True)
    app_with_mocks.reload_messages.assert_called_once()
    assert res == "break"

    # Test toggle wrap
    app_with_mocks.wrap_var.get.return_value = False
    res = app_with_mocks._toggle_wrap()
    app_with_mocks.wrap_var.set.assert_called_with(True)
    app_with_mocks._update_wrap.assert_called_once()
    assert res == "break"

    # Test toggle clean
    app_with_mocks.clean_var.get.return_value = False
    res = app_with_mocks._toggle_clean()
    app_with_mocks.clean_var.set.assert_called_with(True)
    assert res == "break"


def test_toggle_shortcuts_with_focus(app_with_mocks):
    """Verify that toggle functions return None and don't toggle when text/entry is focused."""
    # Mock focused widget to return winfo_class="Entry"
    mock_entry = MagicMock()
    mock_entry.winfo_class.return_value = "Entry"
    app_with_mocks.root.focus_get.return_value = mock_entry
    app_with_mocks.reload_messages = MagicMock()
    app_with_mocks._update_wrap = MagicMock()

    # Test toggle threaded
    app_with_mocks.threaded_var.set.reset_mock()
    res = app_with_mocks._toggle_threaded()
    app_with_mocks.threaded_var.set.assert_not_called()
    assert res is None

    # Test toggle wrap
    app_with_mocks.wrap_var.set.reset_mock()
    res = app_with_mocks._toggle_wrap()
    app_with_mocks.wrap_var.set.assert_not_called()
    assert res is None

    # Test toggle clean
    app_with_mocks.clean_var.set.reset_mock()
    res = app_with_mocks._toggle_clean()
    app_with_mocks.clean_var.set.assert_not_called()
    assert res is None
