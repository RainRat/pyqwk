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
        mock_tk.CENTER = "center"
        mock_tk.WORD = "word"
        mock_tk.NONE = "none"

        yield


def get_app():
    root = MagicMock()
    app = QwkGuiApp(root)
    return app


def test_column_vars_initialization(mock_gui_deps):
    """Verify that column_vars contains BooleanVars initialized to True for all columns except #0."""
    app = get_app()
    assert "Flags" in app.column_vars
    assert "Num" in app.column_vars
    assert "#0" not in app.column_vars
    # All should default to True (shown)
    assert app.column_vars["Flags"].get() is True


def test_update_visible_columns(mock_gui_deps):
    """Verify that _update_visible_columns filters visible columns based on self.column_vars."""
    app = get_app()

    # Uncheck a couple of columns
    app.column_vars["Flags"].get.return_value = False
    app.column_vars["Words"].get.return_value = False

    app._update_visible_columns()

    # Extract the displaycolumns list set on message_list
    display_list = None
    for call_args in app.message_list.__setitem__.call_args_list:
        if call_args[0][0] == "displaycolumns":
            display_list = call_args[0][1]
            break

    assert display_list is not None
    assert "Flags" not in display_list
    assert "Words" not in display_list
    assert "Num" in display_list
    assert "From" in display_list


def test_show_list_context_menu_heading(mock_gui_deps):
    """Verify right-clicking on treeview header displays the columns checkbutton context menu."""
    app = get_app()

    event = MagicMock()
    event.x = 50
    event.y = 10
    event.x_root = 100
    event.y_root = 150

    app.message_list.identify_region.return_value = "heading"

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        app._show_list_context_menu(event)

        # Check that menu was initialized and posted
        mock_menu_class.assert_called_with(app.root, tearoff=0)
        mock_menu.post.assert_called_with(100, 150)

        # Check checkbuttons were added for each column (total 10 non-tree columns)
        assert mock_menu.add_checkbutton.call_count == 10
