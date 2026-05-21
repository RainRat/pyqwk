import sys
from unittest.mock import MagicMock, patch, ANY
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk


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

        # Mock classes/types
        class TclError(Exception):
            pass
        mock_tk.TclError = TclError

        # Mock Combobox
        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "combo": mock_combo,
        }

def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)

class TestConferenceNavigation:
    def test_navigate_conference_logic(self, mock_gui_deps):
        app = get_app()
        # Setup mock conferences
        mock_gui_deps["combo"].__getitem__.side_effect = lambda key: ["All", "1: General", "2: Tech"] if key == "values" else None
        mock_gui_deps["combo"].current.return_value = 1  # Current is "1: General"

        with patch.object(app, "reload_messages") as mock_reload:
            # Navigate forward
            app._navigate_conference(1)
            mock_gui_deps["combo"].current.assert_called_with(2)
            mock_reload.assert_called_once()

            # Navigate backward
            mock_gui_deps["combo"].current.return_value = 2
            app._navigate_conference(-1)
            mock_gui_deps["combo"].current.assert_called_with(1)

            # Wrap around forward
            mock_gui_deps["combo"].current.return_value = 2
            app._navigate_conference(1)
            mock_gui_deps["combo"].current.assert_called_with(0)

            # Wrap around backward
            mock_gui_deps["combo"].current.return_value = 0
            app._navigate_conference(-1)
            mock_gui_deps["combo"].current.assert_called_with(2)

    def test_navigate_conference_empty(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["combo"].__getitem__.side_effect = lambda key: [] if key == "values" else None

        with patch.object(app, "reload_messages") as mock_reload:
            app._navigate_conference(1)
            mock_reload.assert_not_called()

    def test_navigation_buttons_existence(self, mock_gui_deps):
        app = get_app()
        # Verify that buttons with ◀ and ▶ were created
        mock_gui_deps["ttk"].Button.assert_any_call(
            ANY, text="◀", width=2, command=ANY
        )
        mock_gui_deps["ttk"].Button.assert_any_call(
            ANY, text="▶", width=2, command=ANY
        )

    def test_keyboard_shortcuts_bound(self, mock_gui_deps):
        app = get_app()
        # Check that [ and ] are bound
        calls = app.root.bind.call_args_list
        bound_keys = [c[0][0] for c in calls]
        assert "[" in bound_keys
        assert "]" in bound_keys

    def test_welcome_screen_updates(self, mock_gui_deps):
        app = get_app()
        app._render_welcome_screen()

        # Verify that the new shortcut is mentioned in the welcome screen
        found_shortcut = False
        for call_args in app.detail_text.insert.call_args_list:
            if "[ / ]" in str(call_args):
                found_shortcut = True
                break
        assert found_shortcut, "Conference navigation shortcuts not found in welcome screen"
