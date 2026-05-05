import sys
from unittest.mock import MagicMock, patch
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
        mock_tk.NONE = "none"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }


def test_wrap_toggle(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Initially wrapping should be ON (tk.WORD)
    app.wrap_var.get.return_value = True
    app._update_wrap()
    app.detail_text.config.assert_any_call(wrap=mock_gui_deps["tk"].WORD)
    app.detail_h_scrollbar.grid_forget.assert_called()

    # Toggle wrapping OFF
    app.wrap_var.get.return_value = False
    app._update_wrap()
    app.detail_text.config.assert_any_call(wrap=mock_gui_deps["tk"].NONE)
    app.detail_h_scrollbar.grid.assert_called_with(row=1, column=0, sticky="ew")


def test_reset_all_resets_wrap(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Mock wrap_var.get to return True after it's set to True
    def mock_set(val):
        app.wrap_var.get.return_value = val

    app.wrap_var.set.side_effect = mock_set

    # Initially False
    app.wrap_var.get.return_value = False

    app.clear_filters()

    app.wrap_var.set.assert_called_with(True)
    app.detail_text.config.assert_any_call(wrap=mock_gui_deps["tk"].WORD)
