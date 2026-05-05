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
    with patch("pyqwk.gui.tk") as mock_tk, patch("pyqwk.gui.ttk") as mock_ttk:
        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }


def test_select_relative_message_edge_cases(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # 1. Test when self.messages is empty (line 121)
    app.messages = []
    app._select_relative_message(1)
    app.message_list.selection_set.assert_not_called()

    # 2. Test when search_entry has focus and force is False (line 125)
    app.messages = [MagicMock()]
    root.focus_get.return_value = app.search_entry
    app._select_relative_message(1, force=False)
    app.message_list.selection_set.assert_not_called()

    # 3. Test when all_items is empty (line 129)
    root.focus_get.return_value = None
    with patch.object(app, "_get_all_tree_items", return_value=[]):
        app._select_relative_message(1)
        app.message_list.selection_set.assert_not_called()

    # 4. Test ValueError in all_items.index (line 141)
    # This happens if current_iid is not in all_items
    app.messages = [MagicMock()]
    app.message_list.selection.return_value = ["invalid_iid"]
    with patch.object(app, "_get_all_tree_items", return_value=["iid1", "iid2"]):
        app._select_relative_message(1)
        # Should fallback to selecting all_items[0]
        app.message_list.selection_set.assert_called_with("iid1")
