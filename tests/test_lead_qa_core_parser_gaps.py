import pytest
import logging
from unittest.mock import MagicMock, patch
from pyqwk.core import _parse_text_messages, _order_messages_by_thread, ParsedMessage, MessageHeader
from pyqwk.gui import QwkGuiApp

def test_parse_text_empty_date(tmp_path):
    """Test _parse_text_messages with an empty date field (coverage for line 1680 false branch)."""
    content = "From: Alice\nTo: Bob\nSubject: Test\nDate:  \n\nBody"
    f = tmp_path / "empty_date.txt"
    f.write_text(content, encoding="utf-8")
    msgs = _parse_text_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

def test_parse_text_single_part_date(tmp_path):
    """Test _parse_text_messages with a single-part date field (coverage for line 1682 false branch)."""
    content = "From: Alice\nTo: Bob\nSubject: Test\nDate: 2024-05-20\n\nBody"
    f = tmp_path / "single_date.txt"
    f.write_text(content, encoding="utf-8")
    msgs = _parse_text_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "2024-05-20"
    assert msgs[0].header.msgtime == "00:00"

def test_parse_text_no_conf_number(tmp_path):
    """Test _parse_text_messages with no conference number (coverage for line 1699 false branch)."""
    content = "From: Alice\nTo: Bob\nSubject: Test\nConference: General Area\n\nBody"
    f = tmp_path / "no_conf.txt"
    f.write_text(content, encoding="utf-8")
    msgs = _parse_text_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].confname == "General Area"
    assert msgs[0].confnum == 0

def test_threading_cycle_deduplication(caplog):
    """Test cycle detection deduplication (coverage for line 6285)."""
    def make_msg(idx, msgnum, refnum, subject="Sub"):
        h = MessageHeader(" ", msgnum, "01-01-24", "12:00", "To", "From", subject, "", refnum, 1, " ", 1, 1, "")
        return ParsedMessage("Body", msgnum, refnum, 1, h)

    # Long cycle: A (1) -> B (2) -> C (3) -> A (1)
    # Plus another path to trigger the cycle report twice if not deduplicated.
    # D (4) -> C (3)
    msgs = [
        make_msg(0, 1, 3), # A replies to C
        make_msg(1, 2, 1), # B replies to A
        make_msg(2, 3, 2), # C replies to B
        make_msg(3, 4, 3), # D replies to C
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)

    reports = [w for w in caplog.text.splitlines() if "Conversation loop detected" in w and "msgnum 1" in w]
    assert len(reports) == 1

def test_gui_random_message_empty():
    """Test GUI random message selection with empty list (coverage for line 2334)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.search_entry = MagicMock()
            app.exclude_entry = MagicMock()
            app.message_list = MagicMock()
            app._get_all_tree_items = MagicMock(return_value=[])
            app._select_random_message()
            app.message_list.selection_set.assert_not_called()

def test_gui_select_by_index_nonexistent():
    """Test GUI selection by nonexistent index (coverage for line 2325 false branch)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.message_list = MagicMock()
            app.message_list.exists.return_value = False
            app._select_by_index(999)
            app.message_list.selection_set.assert_not_called()

def test_gui_navigate_search_no_matches_no_more_messages():
    """Test GUI search navigation with no matches and no other messages (coverage for line 1569 false branch)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.search_var = MagicMock()
            app.search_var.get.return_value = "query"
            app._search_matches = []
            app._select_relative_message = MagicMock(return_value=False)
            app._navigate_search_matches(1)
            app._select_relative_message.assert_called_once_with(1, force=True)
