import sys
from unittest.mock import MagicMock, patch
import pytest


# Mock tkinter before any pyqwk.gui imports
class MockTclError(Exception):
    pass


if "tkinter" in sys.modules:
    existing_tk = sys.modules["tkinter"]
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

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader, format_size


@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()

    with (
        patch("tkinter.BooleanVar", return_value=MagicMock()),
        patch("tkinter.StringVar", return_value=MagicMock()),
        patch("tkinter.ttk.Treeview", return_value=MagicMock()) as mock_tree,
        patch("tkinter.Text", return_value=MagicMock()) as mock_text,
        patch("tkinter.ttk.Combobox") as mock_combo,
    ):
        a = QwkGuiApp(root)
        a.message_list = mock_tree.return_value
        a.detail_text = mock_text.return_value

        # Mock some attributes used in _current_settings
        a.bbs_combo = mock_combo.return_value
        a.conf_combo = mock_combo.return_value

        # Prevent recursion in _apply_zebra_striping by default
        a.message_list.get_children.return_value = []

        return a


def test_format_size_kb_mb(app):
    """Cover KB and MB formatting in format_size."""
    assert format_size(1500) == "1.5 KB"
    assert format_size(2000000) == "1.9 MB"


def test_show_stats_window_with_links(app):
    """Cover line 1545: Top Links in stats window."""
    app.current_paths = ["test.qwk"]
    stats_data = {
        "file": "test.qwk",
        "matching_messages": 1,
        "total_messages": 1,
        "attachments_count": 0,
        "dates": {"earliest": "2023-01-01T12:00:00", "latest": "2023-01-01T12:00:00"},
        "private_count": 0,
        "reply_rate": 0,
        "reply_count": 0,
        "avg_message_length": 100,
        "year_distribution": {},
        "month_distribution": {},
        "authors": [{"name": "Author", "count": 1}],
        "recipients": [{"name": "Recipient", "count": 1}],
        "subjects": [{"subject": "Sub", "count": 1}],
        "keywords": [{"word": "Key", "count": 1}],
        "day_of_week": {},
        "hour_of_day": {},
        "links": [{"url": "http://example.com", "count": 1}],
        "conferences": [],
    }

    with (
        patch("pyqwk.gui.calculate_archive_stats", return_value=stats_data),
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text") as mock_text_cls,
    ):
        mock_txt = MagicMock()
        mock_text_cls.return_value = mock_txt

        app.show_stats_window()

        # Check if "Top Links" was inserted
        found = False
        for call_args in mock_txt.insert.call_args_list:
            if "\nTop Links\n" in call_args.args:
                found = True
                break
        assert found


def test_sort_column_from_messages(app):
    """Cover lines 1615-1634: sorting using self.messages data."""
    h1 = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To1", "From1", "Sub1", "", None, 1, " ", 1, 1, ""
    )
    h2 = MessageHeader(
        " ", 2, "02-01-90", "13:00", "To2", "From2", "Sub2", "", None, 1, " ", 2, 1, ""
    )

    app.messages = [
        ParsedMessage("Body1", 1, None, 1, h1, bbs_name="BBS1"),
        ParsedMessage(
            "Body2", 2, None, 2, h2, bbs_name="BBS2", attachments=["file.txt"]
        ),
    ]
    app.board_dict = {1: "Conf1", 2: "Conf2"}

    # Mock treeview children to return iids that match indices in app.messages
    app.message_list.get_children.side_effect = [["0", "1"], []] * 10

    # Test multiple columns to cover all branches in 1617-1634
    cols = ["Num", "Size", "Date", "From", "To", "Conference", "BBS", "Flags", "#0"]
    for col in cols:
        app.sort_column(col, False)
        app.message_list.move.assert_called()


def test_sort_column_size_fallback_error(app):
    """Cover lines 1645-1646: Size parsing fallback error."""
    app.message_list.get_children.side_effect = [["item1"], []]
    # idx = int("item1") will raise ValueError, triggering fallback
    app.message_list.set.return_value = ""  # val.split() is [], [0] raises IndexError

    app.sort_column("Size", False)
    app.message_list.move.assert_called()


def test_sort_column_general_exception_fallback(app):
    """Cover lines 1662-1665: General sort exception fallback."""
    app.message_list.get_children.side_effect = [["item1", "item2"], []]

    def mock_set(iid, col):
        if iid == "item1":
            return "01-01-90 12:00"
        return "Not a date"

    app.message_list.set.side_effect = mock_set

    with patch("pyqwk.gui._parse_qwk_date") as mock_parse:
        # Trigger both sort failures to reach line 1665
        class UltimateUnsortable:
            def __lt__(self, other):
                raise TypeError("Initial sort failure")

            def __str__(self):
                raise RuntimeError("Secondary sort failure (str conversion)")

        mock_parse.side_effect = [UltimateUnsortable(), UltimateUnsortable()]

        app.sort_column("Date", False)

    app.message_list.move.assert_called()
