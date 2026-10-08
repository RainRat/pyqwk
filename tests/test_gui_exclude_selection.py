import sys
from unittest.mock import MagicMock, patch, ANY
import pytest

@pytest.fixture(autouse=True)
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        class TclError(Exception):
            pass

        mock_tk.TclError = TclError

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }

def test_exclude_from_selection(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp

    root = MagicMock()
    app = QwkGuiApp(root)

    app.detail_text.tag_ranges.return_value = ("1.0", "1.11")
    app.detail_text.get.return_value = "Hello world\n"

    with patch.object(app, "reload_messages") as mock_reload:
        app._exclude_from_selection()
        app.exclude_var.set.assert_called_with("Hello world")
        mock_reload.assert_called_once()
        app.message_list.focus_set.assert_called_once()

def test_show_text_context_menu_with_selection(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp

    root = MagicMock()
    app = QwkGuiApp(root)

    app.message_list.selection.return_value = ()
    app.detail_text.tag_ranges.return_value = ("1.0", "1.11")
    app.detail_text.get.return_value = "Sample text"

    mock_menu = MagicMock()
    mock_gui_deps["tk"].Menu.return_value = mock_menu

    class DummyEvent:
        x_root = 100
        y_root = 100

    app._show_text_context_menu(DummyEvent())

    calls = mock_menu.add_command.call_args_list
    labels = [c.kwargs.get("label") for c in calls if "label" in c.kwargs]

    assert "Search for 'Sample text'" in labels
    assert "Exclude 'Sample text'" in labels
