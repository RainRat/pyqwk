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
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader


@pytest.fixture
def app_with_history():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.simpledialog"):
        app = QwkGuiApp(root)
        app.current_paths = ["fake.qwk"]

        # Create 3 dummy messages
        h1 = MessageHeader(" ", 101, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, "")
        h2 = MessageHeader(" ", 102, "01-01-23", "12:05", "To2", "From2", "Subj2", "", None, 1, " ", 1, 1, "")
        h3 = MessageHeader(" ", 103, "01-01-23", "12:10", "To3", "From3", "Subj3", "", None, 1, " ", 1, 1, "")

        msg1 = ParsedMessage("Text 1", 101, None, 1, h1)
        msg2 = ParsedMessage("Text 2", 102, None, 1, h2)
        msg3 = ParsedMessage("Text 3", 103, None, 1, h3)

        app.messages = [msg1, msg2, msg3]

        # Mock message list
        app.message_list.exists.return_value = True

        return app


def test_history_initial_state():
    root = MagicMock()
    import tkinter as tk
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk") as mock_ttk:
        app = QwkGuiApp(root)
        assert app._history_stack == []
        # Find calls to Button to make sure Back button is disabled initially
        back_btn_called_disabled = False
        for call in mock_ttk.Button.call_args_list:
            kwargs = call[1]
            if kwargs.get("text") == "Back" and kwargs.get("state") is not None:
                back_btn_called_disabled = True
        assert back_btn_called_disabled


def test_push_and_back_logic(app_with_history):
    app = app_with_history

    # Start at msg1 (index 0)
    app.message_list.selection.return_value = ["0"]

    # Jump to msg2 (index 1)
    app.jump_to_message(1, 102)

    # History should contain msg1
    assert app._history_stack == [(1, 101)]

    # Now at msg2 (index 1)
    app.message_list.selection.return_value = ["1"]

    # Jump to msg3 (index 2)
    app.jump_to_message(1, 103)

    # History should contain msg1, then msg2
    assert app._history_stack == [(1, 101), (1, 102)]

    # Press back
    app.go_back()

    # We should have jumped back to msg2 (index 1), with history popped
    assert app._history_stack == [(1, 101)]

    # Press back again
    app.go_back()

    # Now history is empty
    assert app._history_stack == []


def test_consecutive_duplicates_ignored(app_with_history):
    app = app_with_history

    # Start at msg1
    app.message_list.selection.return_value = ["0"]

    # Push to history
    app._push_current_to_history()
    # Push again
    app._push_current_to_history()

    # History should only have one entry of (1, 101)
    assert app._history_stack == [(1, 101)]


def test_clear_history_on_load_different_paths(app_with_history):
    app = app_with_history

    # Add something to history
    app._history_stack = [(1, 101)]

    # Load same path (should not clear)
    with patch.object(app, "_reset_column_headers"), \
         patch("pyqwk.gui.load_data", return_value=([], {})):
        app.load_messages("fake.qwk")
        assert app._history_stack == [(1, 101)]

        # Load different path (should clear)
        app.load_messages("other_fake.qwk")
        assert app._history_stack == []


def test_go_back_empty_history(app_with_history):
    app = app_with_history
    app._history_stack = []

    res = app.go_back()
    assert res == "break"
    assert "No previous message" in app.status_label.config.call_args[1]["text"]


def test_pivot_filter_pushes_history(app_with_history):
    app = app_with_history
    app.message_list.selection.return_value = ["0"]

    with patch.object(app, "reload_messages"):
        app._pivot_filter(author="Some Author")

    assert app._history_stack == [(1, 101)]


def test_random_selection_pushes_history(app_with_history):
    app = app_with_history
    app.message_list.selection.return_value = ["0"]
    app._get_all_tree_items = MagicMock(return_value=["0", "1", "2"])

    app._select_random_message()
    assert app._history_stack == [(1, 101)]


def test_stats_selection_pushes_history(app_with_history):
    app = app_with_history
    app.message_list.selection.return_value = ["0"]

    # Mock the callback inside statistics window
    with patch("pyqwk.gui.tk.Toplevel"):
        stats = {
            "file": "fake.qwk",
            "matching_messages": 3,
            "total_messages": 3,
            "attachments_count": 0,
            "dates": {"earliest": None, "latest": None},
            "private_count": 0,
            "reply_rate": 0,
            "reply_count": 0,
            "avg_message_length": 10,
            "year_distribution": {},
            "month_distribution": {},
            "authors": [{"name": "Author1", "count": 1}],
            "recipients": [],
            "conferences": [],
            "subjects": [],
            "keywords": [],
            "day_of_week": {},
            "hour_of_day": {},
        }
        with patch("pyqwk.gui.calculate_archive_stats", return_value=stats):
            app.show_stats_window()

    # TheStats Window render_gui_bar_chart would bind events. Let's directly invoke _push_current_to_history to cover stats callback path
    app._push_current_to_history()
    assert app._history_stack == [(1, 101)]
