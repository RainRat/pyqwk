import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_root():
    root = tk.Tk()
    yield root
    root.destroy()

def test_navigate_conference(mock_root):
    # Mocking necessary components to avoid full app initialization issues
    with patch('pyqwk.gui.load_data'), \
         patch('pyqwk.gui.expand_paths', return_value=[]), \
         patch('pyqwk.gui.QwkGuiApp._render_welcome_screen'):

        app = QwkGuiApp(mock_root)
        app.reload_messages = MagicMock()

        # Setup conferences
        app.conf_combo['values'] = ["0: All", "1: General", "2: Tech"]
        app.conf_combo.current(1) # Start at General

        # Test forward navigation
        app._navigate_conference(1)
        assert app.conf_combo.current() == 2
        app.reload_messages.assert_called_once()

        # Test backward navigation
        app.reload_messages.reset_mock()
        app._navigate_conference(-1)
        assert app.conf_combo.current() == 1
        app.reload_messages.assert_called_once()

        # Test wrap around forward
        app.conf_combo.current(2)
        app._navigate_conference(1)
        assert app.conf_combo.current() == 0

        # Test wrap around backward
        app.conf_combo.current(0)
        app._navigate_conference(-1)
        assert app.conf_combo.current() == 2

def test_navigate_conference_no_values(mock_root):
    with patch('pyqwk.gui.QwkGuiApp._render_welcome_screen'):
        app = QwkGuiApp(mock_root)
        app.reload_messages = MagicMock()
        app.conf_combo['values'] = []

        app._navigate_conference(1)
        assert app.reload_messages.call_count == 0
