import sys
from unittest.mock import MagicMock, patch

# Ensure pyqwk.gui has a valid Exception class for tk.TclError if tkinter is mocked
if "tkinter" not in sys.modules:
    mock_tk = MagicMock()
    sys.modules["tkinter"] = mock_tk

if "tkinter.ttk" not in sys.modules:
    sys.modules["tkinter.ttk"] = MagicMock()
if "tkinter.filedialog" not in sys.modules:
    sys.modules["tkinter.filedialog"] = MagicMock()
if "tkinter.messagebox" not in sys.modules:
    sys.modules["tkinter.messagebox"] = MagicMock()
if "tkinter.simpledialog" not in sys.modules:
    sys.modules["tkinter.simpledialog"] = MagicMock()

import pytest
import pyqwk.gui
from pyqwk.gui import QwkGuiApp

# Use whatever TclError class is currently configured in pyqwk.gui.tk
TclErrorClass = getattr(pyqwk.gui.tk, "TclError", Exception)
if not (isinstance(TclErrorClass, type) and issubclass(TclErrorClass, BaseException)):
    class MockTclError(Exception):
        pass
    pyqwk.gui.tk.TclError = MockTclError
    TclErrorClass = MockTclError


@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    with patch("tkinter.StringVar"), patch("tkinter.BooleanVar"):
        app = QwkGuiApp(root)
        app.exclude_var = MagicMock()
        return app


def test_exclude_from_selection_logic(app):
    """Verify that _exclude_from_selection correctly updates exclude_var and reloads."""
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ("1.0", "1.5")
    app.detail_text.get.return_value = " spam "
    app.reload_messages = MagicMock()
    app.message_list = MagicMock()

    app._exclude_from_selection()

    app.exclude_var.set.assert_called_once_with("spam")
    app.reload_messages.assert_called_once()
    app.message_list.focus_set.assert_called_once()


def test_exclude_from_selection_empty(app):
    """Verify that _exclude_from_selection does nothing if no text is selected."""
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ()
    app.reload_messages = MagicMock()

    app._exclude_from_selection()

    app.exclude_var.set.assert_not_called()
    app.reload_messages.assert_not_called()


def test_exclude_from_selection_tcl_error(app):
    """Test _exclude_from_selection when tag_ranges raises TclError."""
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.side_effect = pyqwk.gui.tk.TclError("No selection")
    app.reload_messages = MagicMock()

    app._exclude_from_selection()

    app.exclude_var.set.assert_not_called()
    app.reload_messages.assert_not_called()


def test_show_text_context_menu_with_exclude_selection(app):
    """Verify that the context menu includes the Exclude option when text is selected."""
    event = MagicMock(x_root=100, y_root=100)
    app.detail_text = MagicMock()
    app.detail_text.tag_ranges.return_value = ("1.0", "1.10")
    app.detail_text.get.return_value = "Unwanted Term"

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_text_context_menu(event)

        calls = mock_menu_instance.add_command.call_args_list
        labels = [c[1].get("label", "") for c in calls]
        assert "Exclude 'Unwanted Term'" in labels
