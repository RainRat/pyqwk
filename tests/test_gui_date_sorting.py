import sys
from unittest.mock import MagicMock, patch, call, ANY
import pytest
import datetime

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture(autouse=True)
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

def test_sort_column_chronological(mock_gui_deps):
    app = get_app()
    app.message_list.get_children.return_value = ["item1", "item2", "item3"]

    # item1: Dec 1993, item2: Jan 1994, item3: Feb 1994
    dates = {
        "item1": "12-10-93 12:00",
        "item2": "01-15-94 09:00",
        "item3": "02-01-94 15:00"
    }

    # Mock set returning these date strings
    app.message_list.set.side_effect = lambda k, col: dates[k]
    app.threaded_var.get.return_value = False

    # Sort Ascending (earliest first)
    app.sort_column("Date", False)
    # Expected order: item1, item2, item3
    app.message_list.move.assert_has_calls([
        call("item1", "", 0),
        call("item2", "", 1),
        call("item3", "", 2)
    ])

    # Sort Descending (latest first)
    app.message_list.move.reset_mock()
    app.sort_column("Date", True)
    # Expected order: item3, item2, item1
    app.message_list.move.assert_has_calls([
        call("item3", "", 0),
        call("item2", "", 1),
        call("item1", "", 2)
    ])

def test_sort_column_date_handles_y2k(mock_gui_deps):
    app = get_app()
    app.message_list.get_children.return_value = ["item1", "item2"]

    # item1: 1999, item2: 2023 (01-01-23)
    dates = {
        "item1": "12-31-99 23:59",
        "item2": "01-01-23 00:01"
    }

    app.message_list.set.side_effect = lambda k, col: dates[k]
    app.threaded_var.get.return_value = False

    # Sort Ascending: 1999 should be before 2023
    app.sort_column("Date", False)
    app.message_list.move.assert_has_calls([
        call("item1", "", 0),
        call("item2", "", 1)
    ])

def test_sort_column_date_malformed(mock_gui_deps):
    app = get_app()
    app.message_list.get_children.return_value = ["item1", "item2"]

    # One good, one malformed
    dates = {
        "item1": "01-01-90 12:00",
        "item2": "not-a-date"
    }

    app.message_list.set.side_effect = lambda k, col: dates[k]
    app.threaded_var.get.return_value = False

    # Should not crash and should still sort something
    app.sort_column("Date", False)
    assert app.message_list.move.call_count == 2
