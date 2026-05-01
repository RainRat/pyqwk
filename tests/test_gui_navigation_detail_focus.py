import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk:

        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }

def test_block_text_input_navigation(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Mock _select_relative_message
    app._select_relative_message = MagicMock()

    # Simulate 'j' key press
    event_j = MagicMock()
    event_j.keysym = 'j'
    event_j.state = 0

    result = app._block_text_input(event_j)

    assert result == "break"
    app._select_relative_message.assert_called_with(1)

    # Simulate 'K' key press (capital)
    event_k = MagicMock()
    event_k.keysym = 'K'
    event_k.state = 0

    result = app._block_text_input(event_k)

    assert result == "break"
    app._select_relative_message.assert_called_with(-1)

    # Simulate 'Up' key press
    event_up = MagicMock()
    event_up.keysym = 'Up'
    event_up.state = 0

    result = app._block_text_input(event_up)
    assert result is None

    # Simulate random key 'x'
    event_x = MagicMock()
    event_x.keysym = 'x'
    event_x.state = 0

    result = app._block_text_input(event_x)
    assert result == "break"

    # Simulate Control+C
    event_ctrl_c = MagicMock()
    event_ctrl_c.keysym = 'c'
    event_ctrl_c.state = 0x4

    result = app._block_text_input(event_ctrl_c)
    assert result is None
