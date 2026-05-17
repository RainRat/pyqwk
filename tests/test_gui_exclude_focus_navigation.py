import sys
from unittest.mock import MagicMock, patch

# Mock tkinter and related components before importing pyqwk.gui
mock_tk = MagicMock()
mock_ttk = MagicMock()
mock_font = MagicMock()

# Mock BooleanVar and StringVar to return usable mocks
def make_var(value=None):
    m = MagicMock()
    m.get.return_value = value
    return m

mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.font"] = mock_font
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp

def test_select_relative_message_focus_awareness():
    """Verify that _select_relative_message returns False when exclude_entry has focus."""
    root = MagicMock()
    app = QwkGuiApp(root)

    # Setup state
    app.messages = [MagicMock(), MagicMock()]
    app.search_entry = MagicMock()
    app.exclude_entry = MagicMock()

    # Scenario: exclude_entry has focus
    root.focus_get.return_value = app.exclude_entry

    # Should return False (suppress navigation)
    assert app._select_relative_message(1) is False

def test_on_space_pressed_focus_awareness():
    """Verify that _on_space_pressed returns None when exclude_entry has focus."""
    root = MagicMock()
    app = QwkGuiApp(root)

    # Setup widgets
    app.search_entry = MagicMock()
    app.exclude_entry = MagicMock()

    # Scenario: exclude_entry has focus
    root.focus_get.return_value = app.exclude_entry

    event = MagicMock()
    event.keysym = "space"
    event.state = 0

    # Should return None (let entry handle the key)
    assert app._on_space_pressed(event) is None
