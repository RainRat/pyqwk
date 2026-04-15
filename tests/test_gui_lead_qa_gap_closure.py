import sys
import runpy
import os
from unittest.mock import MagicMock, patch, ANY
import pytest
import tkinter as tk

# Mock tkinter before any pyqwk.gui imports to avoid Tcl/Tk dependency in headless environments
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

# Define a real Exception subclass for TclError to satisfy 'except tk.TclError' blocks
class MockTclError(Exception):
    pass
mock_tk.TclError = MockTclError

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader, BBSInfo

@pytest.fixture
def app():
    root = MagicMock()
    # Ensure the root object behaves enough like a tk.Tk object
    root.clipboard_clear = MagicMock()
    root.clipboard_append = MagicMock()

    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.simpledialog"), patch("pyqwk.gui.filedialog"):
        app = QwkGuiApp(root)
        app.current_paths = ["fake.qwk"]
        app.message_list = MagicMock()
        app.bbs_combo = MagicMock()
        app.conf_combo = MagicMock()
        app.detail_text = MagicMock()
        app.status_label = MagicMock()
        app.search_var = MagicMock()
        app.search_var.get.return_value = ""
        app.has_attach_var = MagicMock()
        app.mine_var = MagicMock()
        app.on_this_day_var = MagicMock()
        app.has_links_var = MagicMock()
        app.has_emails_var = MagicMock()
        app.has_phones_var = MagicMock()
        app.has_ansi_var = MagicMock()

        for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                    app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
            var.get.return_value = False

        app.bbs_combo.get.return_value = "All BBSes"
        app.conf_combo.get.return_value = "All Conferences"

        return app

def test_clear_filters_exception_handling(app):
    # Setup: mock current() to raise an exception
    app.bbs_combo.current.side_effect = Exception("Mock Error")
    app.conf_combo.current.side_effect = Exception("Mock Error")

    # Execution
    app.clear_filters()

    # Verification: should fallback to .set()
    app.bbs_combo.set.assert_called_with("All BBSes")
    app.conf_combo.set.assert_called_with("All Conferences")

def test_open_folder_cancellation(app):
    app.current_paths = []
    with patch("pyqwk.gui.filedialog.askdirectory", return_value=""):
        app.open_folder()

    # Should return early and not call load_messages
    assert app.current_paths == []

def test_open_folder_no_archives(app):
    with patch("pyqwk.gui.filedialog.askdirectory", return_value="/tmp/empty"), \
         patch("pyqwk.gui.expand_paths", return_value=[]), \
         patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.open_folder()

    mock_info.assert_called_once()
    assert "No supported message archives found" in mock_info.call_args[0][1]

def test_prompt_jump_to_message_no_messages(app):
    app.messages = []
    app.prompt_jump_to_message()
    # Should return early (line 1348)
    mock_simpledialog = sys.modules["tkinter.simpledialog"]
    mock_simpledialog.askinteger.assert_not_called()

def test_prompt_jump_to_message_selection_error(app):
    h1 = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    app.messages = [ParsedMessage("Text", 1, None, 1, h1)]

    # Mock selection to return an invalid IID that causes ValueError when int() is called
    app.message_list.selection.return_value = ["invalid_iid"]

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=1):
        # This will trigger the except (ValueError, IndexError) block at 1361-1362
        app.prompt_jump_to_message()

    # Verification: It should still find the message by global search (line 1371)
    app.message_list.selection_set.assert_called_with("0")

def test_show_stats_window_with_bbs_and_confs(app):
    app.current_paths = ["test.qwk"]
    stats_data = {
        'file': 'test.qwk',
        'matching_messages': 10,
        'total_messages': 10,
        'attachments_count': 0,
        'dates': {'earliest': '2023-01-01T12:00:00', 'latest': '2023-01-01T12:00:00'},
        'private_count': 0,
        'reply_rate': 0,
        'reply_count': 0,
        'avg_message_length': 100,
        'year_distribution': {},
        'month_distribution': {},
        'authors': [],
        'recipients': [],
        'subjects': [],
        'keywords': [],
        'day_of_week': {},
        'hour_of_day': {},
        'bbses': [{'name': 'Test BBS', 'count': 5}],
        'conferences': [{'number': 1, 'name': 'General', 'count': 5}]
    }

    with patch("pyqwk.gui.calculate_archive_stats", return_value=stats_data), \
         patch("pyqwk.gui.tk.Toplevel") as mock_top:

        # We need to mock the Text widget inside show_stats_window
        mock_text = MagicMock()
        with patch("pyqwk.gui.tk.Text", return_value=mock_text):
            app.show_stats_window()

        # Verify that BBS and Conference stats were inserted
        # We look for calls to insert that contain "Top BBSes" and "Top Conferences"
        insert_calls = [call.args[1] for call in mock_text.insert.call_args_list]
        assert any("Top BBSes" in s for s in insert_calls)
        assert any("Top Conferences" in s for s in insert_calls)

def test_sort_column_size(app):
    # Mock some items in the treeview
    # values are (Flags, Num, From, To, Date, Size, Conference, BBS)
    # Size is at index 5 (0-indexed)
    app.message_list.get_children.side_effect = [["item1", "item2"], []] # Avoid recursion in traverse
    app.message_list.set.side_effect = lambda k, col: "100 B" if k == "item1" else "20 B"
    app.message_list.item.return_value = {"tags": []}

    app.sort_column("Size", False)

    # item2 (20 B) should be moved to index 0, item1 (100 B) to index 1
    calls = app.message_list.move.call_args_list
    assert any(c.args == ("item2", "", 0) for c in calls)
    assert any(c.args == ("item1", "", 1) for c in calls)

def test_gui_main_entry(monkeypatch):
    mock_root = MagicMock()
    # We patch tk.Tk in pyqwk.gui to return our mock_root
    with patch("pyqwk.gui.tk.Tk", return_value=mock_root), \
         patch("pyqwk.gui.QwkGuiApp") as mock_app, \
         patch("argparse.ArgumentParser.parse_args", return_value=MagicMock(paths=[])):

        from pyqwk.gui import main
        main()

        mock_app.assert_called_once()
        args, kwargs = mock_app.call_args
        assert args[0] == mock_root
        assert kwargs['initial_paths'] == []
        mock_root.mainloop.assert_called_once()

@pytest.mark.skip(reason="runpy coverage is tricky in this environment")
def test_gui_main_block():
    # Placeholder to document the intent of covering line 1640
    pass
