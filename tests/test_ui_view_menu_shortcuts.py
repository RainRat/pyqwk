import pytest
from unittest.mock import MagicMock, patch, ANY

# Mock tkinter before importing QwkGuiApp
import sys
if 'tkinter' not in sys.modules:
    mock_tk = MagicMock()
    sys.modules['tkinter'] = mock_tk
    sys.modules['tkinter.filedialog'] = MagicMock()
    sys.modules['tkinter.messagebox'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.simpledialog'] = MagicMock()

from pyqwk.gui import QwkGuiApp

class MockBooleanVar:
    def __init__(self, value=False):
        self._value = value
    def get(self):
        return self._value
    def set(self, val):
        self._value = val

@pytest.fixture
def test_app():
    root = MagicMock()
    # Mocking necessary attributes for initialization
    with patch('pyqwk.gui.ttk.Style'), \
         patch('pyqwk.gui.QwkGuiApp._render_welcome_screen'), \
         patch('pyqwk.gui.QwkGuiApp._build_menu'), \
         patch('pyqwk.gui.QwkGuiApp._build_toolbar'), \
         patch('pyqwk.gui.QwkGuiApp._build_status_bar'), \
         patch('pyqwk.gui.QwkGuiApp._build_layout'):
        app = QwkGuiApp(root)
        app.wrap_var = MockBooleanVar(True)
        app.threaded_var = MockBooleanVar(False)
        app.clean_var = MockBooleanVar(False)
        app.search_entry = MagicMock()
        app.exclude_entry = MagicMock()
        app.message_list = MagicMock()
        app.detail_text = MagicMock()
        return app

def test_toggle_wrap_no_event(test_app):
    test_app.wrap_var.set(True)
    with patch.object(test_app, '_update_wrap') as mock_update:
        test_app.toggle_wrap()
        assert not test_app.wrap_var.get()
        mock_update.assert_called_once()

def test_toggle_wrap_with_event_unfocused(test_app):
    test_app.wrap_var.set(True)
    test_app.root.focus_get.return_value = test_app.message_list
    with patch.object(test_app, '_update_wrap') as mock_update:
        event = MagicMock()
        test_app.toggle_wrap(event)
        assert not test_app.wrap_var.get()
        mock_update.assert_called_once()

def test_toggle_wrap_with_event_focused_search(test_app):
    test_app.wrap_var.set(True)
    test_app.root.focus_get.return_value = test_app.search_entry
    with patch.object(test_app, '_update_wrap') as mock_update:
        event = MagicMock()
        test_app.toggle_wrap(event)
        assert test_app.wrap_var.get()  # Remains True
        mock_update.assert_not_called()

def test_toggle_threaded_no_event(test_app):
    test_app.threaded_var.set(False)
    with patch.object(test_app, 'reload_messages') as mock_reload:
        test_app.toggle_threaded()
        assert test_app.threaded_var.get()
        mock_reload.assert_called_once()

def test_toggle_threaded_with_event_focused_exclude(test_app):
    test_app.threaded_var.set(False)
    test_app.root.focus_get.return_value = test_app.exclude_entry
    with patch.object(test_app, 'reload_messages') as mock_reload:
        event = MagicMock()
        test_app.toggle_threaded(event)
        assert not test_app.threaded_var.get()  # Remains False
        mock_reload.assert_not_called()

def test_toggle_clean_no_event(test_app):
    test_app.clean_var.set(False)
    with patch.object(test_app, 'reload_messages') as mock_reload:
        test_app.toggle_clean()
        assert test_app.clean_var.get()
        mock_reload.assert_called_once()

def test_toggle_clean_with_event_focused_search(test_app):
    test_app.clean_var.set(False)
    test_app.root.focus_get.return_value = test_app.search_entry
    with patch.object(test_app, 'reload_messages') as mock_reload:
        event = MagicMock()
        test_app.toggle_clean(event)
        assert not test_app.clean_var.get()  # Remains False
        mock_reload.assert_not_called()

def test_block_text_input_toggles(test_app):
    # w key
    event_w = MagicMock()
    event_w.keysym.lower.return_value = 'w'
    event_w.state = 0
    with patch.object(test_app, 'toggle_wrap') as mock_toggle:
        res = test_app._block_text_input(event_w)
        assert res == "break"
        mock_toggle.assert_called_once()

    # t key
    event_t = MagicMock()
    event_t.keysym.lower.return_value = 't'
    event_t.state = 0
    with patch.object(test_app, 'toggle_threaded') as mock_toggle:
        res = test_app._block_text_input(event_t)
        assert res == "break"
        mock_toggle.assert_called_once()

    # c key
    event_c = MagicMock()
    event_c.keysym.lower.return_value = 'c'
    event_c.state = 0
    with patch.object(test_app, 'toggle_clean') as mock_toggle:
        res = test_app._block_text_input(event_c)
        assert res == "break"
        mock_toggle.assert_called_once()
