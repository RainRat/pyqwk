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

        # Mock Toplevel
        mock_toplevel = MagicMock()
        mock_tk.Toplevel.return_value = mock_toplevel

        # Mock Text widget
        mock_text = MagicMock()
        mock_tk.Text.return_value = mock_text

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "menu": mock_menu,
            "toplevel": mock_toplevel,
            "text": mock_text,
        }


def get_app(initial_paths=None):
    root = MagicMock()
    # Mock geometry etc to avoid actual window layout calculation errors
    root.winfo_rootx.return_value = 100
    root.winfo_rooty.return_value = 100
    root.winfo_width.return_value = 800
    root.winfo_height.return_value = 600
    return QwkGuiApp(root, initial_paths=initial_paths)


class TestGuiHelp:
    def test_help_menu_creation_and_contents(self, mock_gui_deps):
        """Test that the Help menu cascade is added to the menubar and configured properly."""
        app = get_app()
        menu_mock = mock_gui_deps["menu"]

        # Help menu cascade should be added to the menubar
        menu_mock.add_cascade.assert_any_call(
            label="Help", menu=ANY, underline=0
        )

        # Verify command items in the Help menu
        # Expecting 'Keyboard Shortcuts...' and 'About PyQWK...'
        command_labels = []
        for call_arg in menu_mock.add_command.call_args_list:
            if "label" in call_arg.kwargs:
                command_labels.append(call_arg.kwargs["label"])

        assert "Keyboard Shortcuts..." in command_labels
        assert "About PyQWK..." in command_labels

    def test_show_about_dialog(self, mock_gui_deps):
        """Test that About PyQWK menu option shows the expected information box."""
        app = get_app()
        app.show_about_dialog()

        mock_gui_deps["messagebox"].showinfo.assert_called_once_with(
            "About PyQWK",
            ANY
        )

    def test_show_shortcuts_window(self, mock_gui_deps):
        """Test that show_shortcuts_window opens and populates the reference modal."""
        app = get_app()
        app.show_shortcuts_window()

        # Should instantiate tk.Toplevel
        mock_gui_deps["tk"].Toplevel.assert_called_once_with(app.root)
        toplevel_mock = mock_gui_deps["toplevel"]

        # Verify modal setup
        toplevel_mock.title.assert_called_once_with("Keyboard Shortcuts")
        toplevel_mock.resizable.assert_called_once_with(False, False)
        toplevel_mock.transient.assert_called_once_with(app.root)
        toplevel_mock.grab_set.assert_called_once()

        # Check key bindings on the modal window (Escape and Return)
        toplevel_mock.bind.assert_any_call("<Escape>", ANY)
        toplevel_mock.bind.assert_any_call("<Return>", ANY)

        # Text reference rendering check: called during app init and once in help dialog
        assert mock_gui_deps["tk"].Text.call_count == 2
        text_mock = mock_gui_deps["text"]

        # Ensure insert is called to add references to text widget
        assert text_mock.insert.call_count > 0
        text_mock.config.assert_any_call(state="disabled")

        # Verify close button is added and focused
        button_mock = mock_gui_deps["ttk"].Button
        button_instance = button_mock.return_value
        button_instance.pack.assert_called()
        button_instance.focus_set.assert_called_once()

    def test_f1_shortcut_binding(self, mock_gui_deps):
        """Test that the F1 keyboard shortcut is bound to show_shortcuts_window on the root window."""
        app = get_app()
        # Verify binding on root
        app.root.bind.assert_any_call("<F1>", app.show_shortcuts_window)
