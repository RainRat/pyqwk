import sys
from unittest.mock import MagicMock, patch, call
import pytest
import tkinter as tk

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def mock_app():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
    ):
        # Configure constants
        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.NONE = "none"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        from pyqwk.gui import QwkGuiApp
        root = MagicMock()
        # Mock focus_get to avoid issues with focused widget checks
        root.focus_get.return_value = None

        app = QwkGuiApp(root)

        # Setup dummy messages
        h1 = MessageHeader(" ", 1, "01-01-90", "12:00", "To", "From", "Sub1", "", None, 1, " ", 1, 1, "")
        h2 = MessageHeader(" ", 2, "01-01-90", "12:05", "To", "From", "Sub2", "", None, 1, " ", 1, 1, "")
        app.messages = [
            ParsedMessage("Body 1", 1, None, 1, h1),
            ParsedMessage("Body 2", 2, None, 1, h2),
        ]

        yield app

def test_on_space_pressed_next_keysym(mock_app):
    """Test that 'Next' keysym triggers the same logic as 'space'."""
    event = MagicMock()
    event.keysym = "Next"
    event.state = 0  # No modifiers

    # Mock detail_text.yview to return bottom reached (1.0)
    mock_app.detail_text.yview.return_value = (0.5, 1.0)

    with patch.object(mock_app, "_select_relative_message") as mock_select:
        result = mock_app._on_space_pressed(event)
        assert result == "break"
        mock_select.assert_called_with(1)

def test_on_space_pressed_prior_keysym(mock_app):
    """Test that 'Prior' keysym triggers the same logic as 'BackSpace'."""
    event = MagicMock()
    event.keysym = "Prior"
    event.state = 0

    # Mock detail_text.yview to return top reached (0.0)
    mock_app.detail_text.yview.return_value = (0.0, 0.5)

    with patch.object(mock_app, "_select_relative_message") as mock_select:
        result = mock_app._on_space_pressed(event)
        assert result == "break"
        mock_select.assert_called_with(-1)

def test_block_text_input_delegation(mock_app):
    """Test that _block_text_input delegates continuous reading keys to _on_space_pressed."""
    keys_to_test = ["space", "BackSpace", "Prior", "Next"]

    for key in keys_to_test:
        event = MagicMock()
        event.keysym = key

        with patch.object(mock_app, "_on_space_pressed", return_value="break") as mock_handler:
            result = mock_app._block_text_input(event)
            assert result == "break"
            mock_handler.assert_called_once_with(event)

def test_block_text_input_remains_blocked_for_others(mock_app):
    """Test that other keys still return 'break' or None as before."""
    # A regular character should return "break"
    event = MagicMock()
    event.keysym = "x"
    event.state = 0
    assert mock_app._block_text_input(event) == "break"

    # An allowed navigation key should return None
    event.keysym = "Up"
    assert mock_app._block_text_input(event) is None

    # Prior and Next should now return whatever _on_space_pressed returns (e.g. "break")
    event.keysym = "Prior"
    with patch.object(mock_app, "_on_space_pressed", return_value="delegated"):
        assert mock_app._block_text_input(event) == "delegated"
