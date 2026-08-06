import sys
from unittest.mock import MagicMock, patch, call, ANY
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.gui import QwkGuiApp


@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):
        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        # Tkinter constants
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

        # Mock Menu
        mock_menu = MagicMock()
        mock_tk.Menu.return_value = mock_menu

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "menu": mock_menu,
        }


def get_app(initial_paths=None):
    root = MagicMock()
    return QwkGuiApp(root, initial_paths=initial_paths)


class TestGuiViewMenu:
    def test_view_menu_creation_and_contents(self, mock_gui_deps):
        """Test that the View menu is created and populated with checkbuttons."""
        app = get_app()
        menu_mock = mock_gui_deps["menu"]

        # View menu should be created via tk.Menu(menubar, tearoff=0)
        # Verify call arguments
        menu_calls = mock_gui_deps["tk"].Menu.call_args_list
        assert len(menu_calls) >= 3  # File menu, Edit menu, View menu, context menus etc

        # Let's verify that the view menu is added as a cascade
        # menubar.add_cascade(label="View", menu=view_menu, underline=0)
        menu_mock.add_cascade.assert_any_call(
            label="View", menu=ANY, underline=0
        )
        menu_mock.add_cascade.assert_any_call(
            label="File", menu=ANY, underline=0
        )
        menu_mock.add_cascade.assert_any_call(
            label="Edit", menu=ANY, underline=0
        )

        # Verify checkbutton items in the View menu
        # It should add checkbuttons for Conversations, Clean View, Wrap Text, etc.
        checkbutton_labels = []
        for call_arg in menu_mock.add_checkbutton.call_args_list:
            if "label" in call_arg.kwargs:
                checkbutton_labels.append(call_arg.kwargs["label"])

        assert "Conversations" in checkbutton_labels
        assert "Clean View" in checkbutton_labels
        assert "Wrap Text" in checkbutton_labels
        assert "Remove Colors" in checkbutton_labels
        assert "Hide Personal Info" in checkbutton_labels
        assert "Embed Attachments" in checkbutton_labels

    def test_view_shortcuts_when_focused_on_entries(self, mock_gui_deps):
        """Shortcuts should NOT trigger if focused on search/exclude fields."""
        app = get_app()
        app.threaded_var.get.return_value = False
        app.wrap_var.get.return_value = True
        app.clean_var.get.return_value = False

        # Mock focus_get returning the search_entry
        app.root.focus_get.return_value = app.search_entry

        with patch.object(app, "reload_messages") as mock_reload:
            res = app._toggle_threaded_shortcut()
            assert res is None
            app.threaded_var.set.assert_not_called()
            mock_reload.assert_not_called()

            res2 = app._toggle_wrap_shortcut()
            assert res2 is None
            app.wrap_var.set.assert_not_called()

            res3 = app._toggle_clean_shortcut()
            assert res3 is None
            app.clean_var.set.assert_not_called()

        # Mock focus_get returning the exclude_entry
        app.root.focus_get.return_value = app.exclude_entry

        with patch.object(app, "reload_messages") as mock_reload:
            res = app._toggle_threaded_shortcut()
            assert res is None
            app.threaded_var.set.assert_not_called()

    def test_view_shortcuts_when_not_focused_on_entries(self, mock_gui_deps):
        """Shortcuts should trigger and toggle settings if focused elsewhere."""
        app = get_app()
        app.threaded_var.get.return_value = False
        app.wrap_var.get.return_value = True
        app.clean_var.get.return_value = False

        # Mock focus_get returning root or message_list (not search/exclude)
        app.root.focus_get.return_value = app.message_list

        with patch.object(app, "reload_messages") as mock_reload:
            res = app._toggle_threaded_shortcut()
            assert res == "break"
            # Since get was False, it sets True
            app.threaded_var.set.assert_called_with(True)
            mock_reload.assert_called_once()

        # Wrap text shortcut
        with patch.object(app, "_update_wrap") as mock_update_wrap:
            res2 = app._toggle_wrap_shortcut()
            assert res2 == "break"
            # Since get was True, it sets False
            app.wrap_var.set.assert_called_with(False)
            mock_update_wrap.assert_called_once()

        # Clean view shortcut
        with patch.object(app, "reload_messages") as mock_reload:
            res3 = app._toggle_clean_shortcut()
            assert res3 == "break"
            # Since get was False, it sets True
            app.clean_var.set.assert_called_with(True)
            mock_reload.assert_called_once()
