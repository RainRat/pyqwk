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
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk:

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

def test_get_all_tree_items_traversal(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Mocking a tree structure:
    # "" (root)
    # ├── "iid1"
    # │   └── "iid1.1"
    # └── "iid2"

    def get_children(parent):
        if parent == "":
            return ["iid1", "iid2"]
        if parent == "iid1":
            return ["iid1.1"]
        return []

    app.message_list.get_children.side_effect = get_children

    items = app._get_all_tree_items()

    # Expected flattened list in depth-first order
    assert items == ["iid1", "iid1.1", "iid2"]

def test_apply_zebra_striping_traversal(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Mocking same tree structure
    def get_children(parent):
        if parent == "":
            return ["iid1", "iid2"]
        if parent == "iid1":
            return ["iid1.1"]
        return []

    app.message_list.get_children.side_effect = get_children

    app._apply_zebra_striping()

    # iid1: index 0 (even=False)
    # iid1.1: index 1 (even=True)
    # iid2: index 2 (even=False)

    app.message_list.item.assert_any_call("iid1", tags=())
    app.message_list.item.assert_any_call("iid1.1", tags=("even",))
    app.message_list.item.assert_any_call("iid2", tags=())

def test_sort_column_empty(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    app.message_list.get_children.return_value = []

    app.sort_column("Num", False)
    # Should return early (line 826)
    app.message_list.move.assert_not_called()
