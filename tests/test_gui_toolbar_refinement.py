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
        app.search_var = MagicMock()
        app.exclude_var = MagicMock()
        return app

def test_clear_search_refocus(app):
    # Retrieve the command for the search clear button
    # In _build_toolbar, it's the first button with text "✕"
    # Wait, we need to find how it was called.
    # Actually, we can just test the lambda logic if we can extract it,
    # but it's easier to mock what it calls.

    # Since we can't easily extract the lambda from the mock Button call without
    # capturing it during _build_toolbar, let's re-run _build_toolbar with a mock ttk.

    with patch('pyqwk.gui.ttk') as mock_ttk:
        entries = [MagicMock(name="search_entry"), MagicMock(name="exclude_entry")]
        mock_ttk.Entry.side_effect = lambda *args, **kwargs: entries.pop(0) if entries else MagicMock()
        app._build_toolbar()

        # Find the search clear button (it's the first '✕' button)
        search_clear_btn_call = None
        exclude_clear_btn_call = None

        for call in mock_ttk.Button.call_args_list:
            if call.kwargs.get('text') == '✕':
                if search_clear_btn_call is None:
                    search_clear_btn_call = call
                else:
                    exclude_clear_btn_call = call
                    break

        assert search_clear_btn_call is not None
        assert exclude_clear_btn_call is not None

        search_clear_cmd = search_clear_btn_call.kwargs['command']
        exclude_clear_cmd = exclude_clear_btn_call.kwargs['command']

        # Test search clear refocus
        search_clear_cmd()
        app.search_var.set.assert_called_with("")
        app.search_entry.focus_set.assert_called_once()

        # Test exclude clear refocus
        exclude_clear_cmd()
        app.exclude_var.set.assert_called_with("")
        app.exclude_entry.focus_set.assert_called_once()
