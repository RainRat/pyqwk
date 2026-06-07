import pytest
from unittest.mock import MagicMock, patch

# Mock tkinter before importing QwkGuiApp
import sys
mock_tk = MagicMock()
sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.simpledialog'] = MagicMock()

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    # Mocking necessary attributes for initialization
    with patch('pyqwk.gui.ttk.Style'), \
         patch('pyqwk.gui.QwkGuiApp._render_welcome_screen'), \
         patch('pyqwk.gui.QwkGuiApp._build_menu'), \
         patch('pyqwk.gui.QwkGuiApp._build_toolbar'), \
         patch('pyqwk.gui.QwkGuiApp._build_status_bar'), \
         patch('pyqwk.gui.QwkGuiApp._build_layout'):
        app = QwkGuiApp(root)
        app.search_entry = MagicMock()
        app.exclude_entry = MagicMock()
        app.message_list = MagicMock()
        app.detail_text = MagicMock()
        return app

def test_focus_search_respects_entry_focus(app):
    # 1. Test when focus is NOT in search/exclude fields
    app.root.focus_get.return_value = app.message_list
    app._focus_search()
    app.search_entry.focus_set.assert_called_once()
    app.search_entry.focus_set.reset_mock()

    # 2. Test when focus IS in search field
    app.root.focus_get.return_value = app.search_entry
    app._focus_search()
    app.search_entry.focus_set.assert_not_called()

    # 3. Test when focus IS in exclude field
    app.root.focus_get.return_value = app.exclude_entry
    app._focus_search()
    app.search_entry.focus_set.assert_not_called()

def test_select_random_message_respects_entry_focus(app):
    app._get_all_tree_items = MagicMock(return_value=['item1'])

    # 1. Test when focus is NOT in search/exclude fields
    app.root.focus_get.return_value = app.message_list
    app._select_random_message()
    app.message_list.selection_set.assert_called_once()
    app.message_list.selection_set.reset_mock()

    # 2. Test when focus IS in search field
    app.root.focus_get.return_value = app.search_entry
    app._select_random_message()
    app.message_list.selection_set.assert_not_called()

def test_block_text_input_shortcuts(app):
    # Mock event for 'r'
    event_r = MagicMock()
    event_r.keysym.lower.return_value = 'r'
    event_r.state = 0

    with patch.object(app, '_select_random_message') as mock_random:
        result = app._block_text_input(event_r)
        assert result == "break"
        mock_random.assert_called_once()

    # Mock event for '/'
    event_slash = MagicMock()
    event_slash.keysym.lower.return_value = 'slash'
    event_slash.char = '/'
    event_slash.state = 0

    with patch.object(app, '_focus_search') as mock_focus:
        result = app._block_text_input(event_slash)
        assert result == "break"
        mock_focus.assert_called_once()
