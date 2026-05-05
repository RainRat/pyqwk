import sys
from unittest.mock import MagicMock, patch, ANY


# Mock tkinter BEFORE any pyqwk imports
# Use a custom Exception for TclError to avoid TypeError when catching it
class MockTclError(Exception):
    pass


# We must ensure we don't clobber an existing mock if it's already there and working
# but we need TclError to be our catchable class.
if "tkinter" in sys.modules:
    # If it was already mocked by another test, we might need to inject TclError
    existing_tk = sys.modules["tkinter"]
    # We must replace it to ensure it's catchable as a class in our current process
    existing_tk.TclError = MockTclError
else:
    mock_tk = MagicMock()
    mock_tk.TclError = MockTclError
    sys.modules["tkinter"] = mock_tk

if "tkinter.ttk" not in sys.modules:
    sys.modules["tkinter.ttk"] = MagicMock()
if "tkinter.filedialog" not in sys.modules:
    sys.modules["tkinter.filedialog"] = MagicMock()
if "tkinter.messagebox" not in sys.modules:
    sys.modules["tkinter.messagebox"] = MagicMock()
if "tkinter.simpledialog" not in sys.modules:
    sys.modules["tkinter.simpledialog"] = MagicMock()

import pytest

# Now we can import QwkGuiApp, it will use our mocks
import pyqwk.gui
from pyqwk.gui import QwkGuiApp

# Force the module-level tk to use our MockTclError
pyqwk.gui.tk.TclError = MockTclError


@pytest.fixture
def app():
    root = MagicMock()
    # Mock some methods that might be called during init
    root.after = MagicMock()

    # We must patch the classes BEFORE QwkGuiApp is instantiated in the fixture
    with (
        patch("tkinter.BooleanVar", return_value=MagicMock()),
        patch("tkinter.StringVar", return_value=MagicMock()),
        patch("tkinter.ttk.Treeview", return_value=MagicMock()) as mock_tree,
        patch("tkinter.Text", return_value=MagicMock()) as mock_text,
    ):
        # Instantiate app
        a = QwkGuiApp(root)

        # Attach the mock instances to the app object for easy access in tests
        a.message_list = mock_tree.return_value
        a.detail_text = mock_text.return_value

        return a


def test_show_list_context_menu_no_iid(app):
    """Test _show_list_context_menu when no row is identified (line 95)."""
    event = MagicMock()
    event.y = 10
    app.message_list.identify_row.return_value = ""

    app._show_list_context_menu(event)

    app.message_list.identify_row.assert_called_with(10)
    app.message_list.selection_set.assert_not_called()


def test_show_list_context_menu_invalid_iid(app, mocker):
    """Test _show_list_context_menu with invalid iid (lines 103-104)."""
    event = MagicMock()
    event.y = 10
    app.message_list.identify_row.return_value = "invalid"

    # Mocking self.messages to ensure we hit the try/except
    mocker.patch.object(app, "messages", [])

    app._show_list_context_menu(event)

    app.message_list.selection_set.assert_called_with("invalid")
    # Should exit after the ValueError catch


def test_show_text_context_menu_tcl_error(app, mocker):
    """Test _show_text_context_menu when tag_ranges raises TclError (lines 142-143)."""
    event = MagicMock()
    event.x_root = 100
    event.y_root = 100

    app.detail_text.tag_ranges.side_effect = MockTclError("mock error")

    with patch("pyqwk.gui.tk.Menu"):
        app._show_text_context_menu(event)

    app.detail_text.tag_ranges.assert_called_with("sel")


def test_search_from_selection_tcl_error(app, mocker):
    """Test _search_from_selection when tag_ranges raises TclError (lines 157-158)."""
    app.detail_text.tag_ranges.side_effect = MockTclError("mock error")

    app._search_from_selection()

    app.detail_text.tag_ranges.assert_called_with("sel")


def test_show_stats_window_with_bbses(app):
    """Test show_stats_window when bbses data is present (line 1266)."""
    app.current_paths = ["test.qwk"]
    app.logger = MagicMock()

    mock_stats = {
        "file": "test.qwk",
        "total_messages": 10,
        "matching_messages": 10,
        "attachments_count": 0,
        "dates": {"earliest": "2023-01-01T12:00:00", "latest": "2023-01-01T13:00:00"},
        "authors": [],
        "recipients": [],
        "conferences": [],
        "subjects": [],
        "keywords": [],
        "day_of_week": {},
        "hour_of_day": {},
        "year_distribution": {},
        "month_distribution": {},
        "private_count": 0,
        "reply_count": 0,
        "reply_rate": 0.0,
        "avg_message_length": 100.0,
        "bbses": [{"name": "MyBBS", "count": 10}],
    }

    with (
        patch("pyqwk.gui.calculate_archive_stats", return_value=mock_stats),
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text") as mock_text_cls,
    ):
        mock_txt = MagicMock()
        mock_text_cls.return_value = mock_txt

        app.show_stats_window()

        # Verify Top BBSes header and data were inserted
        mock_txt.insert.assert_any_call(ANY, "\nTop BBSes\n", "h2")
        # Check that 'dim' and 'link' tags are present (or just check the label text)
        found_call = False
        for call in mock_txt.insert.call_args_list:
            if len(call.args) >= 2 and call.args[1] == f"{'MyBBS'[:25]:<25}":
                tags = call.args[2]
                if isinstance(tags, tuple) and "dim" in tags and "link" in tags:
                    found_call = True
                    break
        assert found_call, "Could not find insert call for MyBBS with expected tags"
