import sys
from unittest.mock import MagicMock, patch

# Mock tkinter before pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

import pytest
from pyqwk.gui import QwkGuiApp


@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    with patch("tkinter.StringVar"), patch("tkinter.BooleanVar"):
        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        app.detail_text = MagicMock()
        return app


def test_on_message_list_activate_with_selection(app):
    """Test that activation transfers focus to detail_text and returns 'break' when selected."""
    app.message_list.selection.return_value = ("0",)
    res = app._on_message_list_activate()

    app.detail_text.focus_set.assert_called_once()
    assert res == "break"


def test_on_message_list_activate_without_selection(app):
    """Test that activation does nothing and returns None when no item is selected."""
    app.message_list.selection.return_value = ()
    res = app._on_message_list_activate()

    app.detail_text.focus_set.assert_not_called()
    assert res is None
