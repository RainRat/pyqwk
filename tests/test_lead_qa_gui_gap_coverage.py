import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui():
    mock_root = MagicMock()
    # Mocking necessary parts of tkinter and other dependencies
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.font"),
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.simpledialog"),
    ):
        # Setup common return values for StringVar and BooleanVar
        mock_tk.StringVar.return_value = MagicMock()
        mock_tk.BooleanVar.return_value = MagicMock()

        # Mocking Treeview
        mock_tree = MagicMock()
        mock_ttk.Treeview.return_value = mock_tree
        # Prevent recursion in _apply_zebra_striping by returning empty list for children
        mock_tree.get_children.return_value = []
        mock_tree.item.return_value = {"tags": []}

        app = QwkGuiApp(mock_root)
        app.messages = []
        app.message_list = mock_tree
        app.detail_text = MagicMock()
        app.search_entry = MagicMock()
        app.search_var = MagicMock()
        app.search_count_label = MagicMock()
        app.root = mock_root

        # Mock comboboxes
        app.bbs_combo = MagicMock()
        app.conf_combo = MagicMock()

        # Mock some internal methods that might be called
        app.reload_messages = MagicMock()
        app._update_status_bar = MagicMock()
        app._render_message = MagicMock()
        app._select_by_index = MagicMock()

        # Mock _apply_zebra_striping to avoid recursion issues in mock environment
        app._apply_zebra_striping = MagicMock()

        yield app

def test_show_text_context_menu_no_selection(mock_gui):
    """Test _show_text_context_menu when no message is selected in the list (Branch 208->215)."""
    mock_gui.message_list.selection.return_value = []
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_gui._show_text_context_menu(event)
    # Success is no exception and branch covered

def test_show_text_context_menu_invalid_index(mock_gui):
    """Test _show_text_context_menu with an invalid selection index (Branch 212-213)."""
    mock_gui.message_list.selection.return_value = ["not_an_int"]
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_gui._show_text_context_menu(event)
    # Should catch ValueError and continue.

def test_show_text_context_menu_exception_in_msg_block(mock_gui, message_factory):
    """Test _show_text_context_menu with an exception inside the msg block (Lines 286-287)."""
    # 1. Trigger IndexError in the first block (before "if msg:")
    mock_gui.messages = []
    mock_gui.message_list.selection.return_value = ["0"]
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_gui._show_text_context_menu(event)

    # 2. Trigger ValueError in the second block (inside "if msg:")
    msg = message_factory(1, 0, "Test")
    mock_gui.messages = [msg]
    mock_gui.message_list.selection.return_value = ["0"]

    # Initialize header with strings
    msg.header.msgfrom = "Author"
    msg.header.msgto = "To"
    msg.header.msgsubject = "Subject"
    msg.header.msgnum = 1

    class FailingString(str):
        def __init__(self, val):
            self.count = 0
        def strip(self, *args, **kwargs):
            self.count += 1
            if self.count > 1:
                raise ValueError("Failing inside second try block")
            return super().strip(*args, **kwargs)

    msg.header.msgfrom = FailingString("Author")

    with patch("pyqwk.gui.tk.Menu"):
        mock_gui._show_text_context_menu(event)

def test_show_text_context_menu_empty_detail_selection(mock_gui):
    """Test _show_text_context_menu with an empty text selection (Branch 293->307)."""
    mock_gui.detail_text.tag_ranges.return_value = ("1.0", "1.1")
    mock_gui.detail_text.get.return_value = "   " # Whitespace only
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_gui._show_text_context_menu(event)

def test_search_from_selection_empty(mock_gui):
    """Test _search_from_selection with no selection (Branch 315->exit)."""
    mock_gui.detail_text.tag_ranges.return_value = ()
    mock_gui._search_from_selection()
    mock_gui.search_var.set.assert_not_called()

def test_search_from_selection_whitespace(mock_gui):
    """Test _search_from_selection with whitespace-only selection (Branch 315->exit)."""
    mock_gui.detail_text.tag_ranges.return_value = ("1.0", "1.5")
    mock_gui.detail_text.get.return_value = "    "
    mock_gui._search_from_selection()
    mock_gui.search_var.set.assert_not_called()

def test_find_message_index_no_tree_selection(mock_gui, message_factory):
    """Test _find_message_index when no message is selected in the tree (Branch 368->375)."""
    msg = message_factory(1, 0, "Test")
    mock_gui.messages = [msg]
    mock_gui.message_list.selection.return_value = []

    # This should call _find_message_index which triggers the target_conf=None branch
    idx = mock_gui._find_message_index(1, None)
    assert idx == 0

def test_block_text_input_control_keys(mock_gui):
    """Test _block_text_input with control keys (Branch 421->425)."""
    event = MagicMock()
    event.state = 0x4 # Control mask
    event.keysym = "c"
    assert mock_gui._block_text_input(event) is None

    event.keysym = "a"
    assert mock_gui._block_text_input(event) is None

    event.keysym = "v"
    # Should not be None (it returns "break" by default at the end of function)
    assert mock_gui._block_text_input(event) == "break"

def test_on_space_pressed_unhandled_key(mock_gui):
    """Test _on_space_pressed with an unhandled keysym (Line 725)."""
    event = MagicMock()
    event.keysym = "Escape"
    # Mock yview to return two values
    mock_gui.detail_text.yview.return_value = (0.0, 1.0)
    assert mock_gui._on_space_pressed(event) is None

def test_current_settings_missing_mapping(mock_gui):
    """Test _current_settings with missing conference mapping (Lines 1125-1128)."""
    mock_gui.conf_combo.get.return_value = "Not All Conferences"
    mock_gui.conf_mapping = {} # Missing entry

    settings = mock_gui._current_settings()
    assert settings.conferences is None

def test_navigate_search_matches_invalid_selection(mock_gui):
    """Test _navigate_search_matches with invalid tree selection (Lines 1482-1483)."""
    mock_gui._search_matches = [("1.0", "1.5")]
    mock_gui._current_match_idx = 0
    mock_gui.message_list.selection.return_value = ["invalid"]
    mock_gui._navigate_search_matches(1)
    # Should catch ValueError and continue to update status bar.

def test_sort_column_fallback_subject(mock_gui):
    """Test sort_column fallback to displayed text for Subject/#0 (Line 2566)."""
    mock_gui.message_list.get_children.return_value = ["iid_invalid"]
    # For #0 it calls .item(iid, "text")
    mock_gui.message_list.item.return_value = "Subject Text"

    mock_gui.sort_column("#0", False)
    mock_gui.message_list.item.assert_any_call("iid_invalid", "text")

def test_sort_column_fallback_other(mock_gui):
    """Test sort_column fallback to displayed text for other columns (Line 2564)."""
    mock_gui.message_list.get_children.return_value = ["iid_invalid"]
    # For other columns it calls .set(iid, col)
    mock_gui.message_list.set.return_value = "Column Value"

    mock_gui.sort_column("From", False)
    mock_gui.message_list.set.assert_any_call("iid_invalid", "From")

def test_load_messages_invalid_selection_index(mock_gui):
    """Test load_messages with invalid selection index (Lines 1641-1642)."""
    mock_gui.current_paths = ["test.qwk"]
    mock_gui.message_list.selection.return_value = ["not_an_int"]
    with patch("pyqwk.gui.load_data", return_value=([], {})):
        mock_gui.load_messages(["test.qwk"])

def test_pivot_filter_no_matches(mock_gui):
    """Test _pivot_filter when no matches are found in comboboxes."""
    mock_gui.bbs_combo.__getitem__.return_value = ["Other BBS"]
    mock_gui.conf_combo.__getitem__.return_value = ["999: Other Conf"]

    mock_gui._pivot_filter(bbs_name="Missing", conf_num=1)

    mock_gui.bbs_combo.current.assert_not_called()
    mock_gui.conf_combo.current.assert_not_called()
