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

from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.filedialog") as mock_fd, \
         patch("pyqwk.gui.messagebox") as mock_mb:

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

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }

def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)

class TestSearchNavigation:
    def test_search_match_population(self, mock_gui_deps):
        app = get_app()
        app.search_var.get.return_value = "match"

        # Mock search to find 2 occurrences
        app.detail_text.search.side_effect = ["1.5", "2.10", None]

        mock_iv = MagicMock()
        mock_iv.get.return_value = 5
        # side_effect takes precedence, so we need to override it
        mock_gui_deps["tk"].IntVar.side_effect = lambda *args, **kwargs: mock_iv

        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        msg = ParsedMessage("Body with match and another match", 1, None, 1, header)
        app.messages = [msg]
        app.board_dict = {1: "General"}

        app._render_message(0)

        assert len(app._search_matches) == 2
        assert app._search_matches == [("1.5", "1.5+5c"), ("2.10", "2.10+5c")]
        assert app._current_match_idx == 0

        # Verify initial highlight
        app.detail_text.tag_add.assert_any_call("current_search_highlight", "1.5", "1.5+5c")
        app.detail_text.see.assert_called_with("1.5")

    def test_navigate_search_matches(self, mock_gui_deps):
        app = get_app()
        app._search_matches = [("1.5", "1.5+5c"), ("2.10", "2.10+5c"), ("3.0", "3.0+5c")]
        app._current_match_idx = 0
        app.root.title.return_value = "Test BBS (test.qwk) - PyQWK Reader"

        # Navigate forward
        app._navigate_search_matches(1)
        assert app._current_match_idx == 1
        app.detail_text.tag_remove.assert_called_with("current_search_highlight", "1.0", "end")
        app.detail_text.tag_add.assert_called_with("current_search_highlight", "2.10", "2.10+5c")
        app.detail_text.see.assert_called_with("2.10")

        # Navigate backward (wrap around)
        app._navigate_search_matches(-1)
        assert app._current_match_idx == 0

        # Navigate backward again (wrap around)
        app._select_relative_message = MagicMock(return_value=False)
        app._get_all_tree_items = MagicMock(return_value=["0", "1", "2"])
        app._navigate_search_matches(-1)
        assert app._pending_match_idx == -1

    def test_menu_and_bindings(self, mock_gui_deps):
        app = get_app()
        # Verify F3 bindings
        app.root.bind.assert_any_call("<F3>", ANY)
        app.root.bind.assert_any_call("<Shift-F3>", ANY)

        # Verify menu items (Search through calls to add_command)
        # This is a bit complex with MagicMock, but we can check if lambda was used
        # or if specific labels were added to a menu.
        # Actually we can check the calls to edit_menu.add_command
        # But edit_menu is local to _build_menu.
        # However, we can check mock_tk.Menu().add_command calls

        found_next = False
        found_prev = False
        for call in mock_gui_deps["tk"].Menu().add_command.call_args_list:
            if call.kwargs.get('label') == "Find Next":
                found_next = True
                assert call.kwargs.get('accelerator') == "F3"
            if call.kwargs.get('label') == "Find Previous":
                found_prev = True
                assert call.kwargs.get('accelerator') == "Shift+F3"

        assert found_next, "Find Next menu item not found"
        assert found_prev, "Find Previous menu item not found"

        # Note: multiple menus are created, so we need to be careful.
        # If the above fails, it might be because the mock returned different Menu objects.
