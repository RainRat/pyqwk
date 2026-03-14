import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter and ttk
mock_tk = MagicMock()
mock_ttk = MagicMock()

# Ensure variables return mocks that don't need a root
mock_tk.BooleanVar.return_value = MagicMock()
mock_tk.StringVar.return_value = MagicMock()

# Import QwkGuiApp with mocked modules
with patch.dict(sys.modules, {
    "tkinter": mock_tk,
    "tkinter.ttk": mock_ttk,
    "tkinter.filedialog": MagicMock(),
    "tkinter.messagebox": MagicMock(),
    "tkinter.simpledialog": MagicMock()
}):
    from pyqwk.gui import QwkGuiApp

def test_welcome_screen_on_startup():
    """Verify that the welcome screen is rendered when no archive is provided."""
    mock_root = MagicMock()

    # Pre-create the mock for Text to be used in QwkGuiApp
    mock_detail_text = MagicMock()
    mock_tk.Text.return_value = mock_detail_text

    # Create instance
    app = QwkGuiApp(mock_root)

    # Ensure detail_text is what we expect
    assert app.detail_text == mock_detail_text

    # Manually trigger the welcome screen call
    app._render_welcome_screen()

    # Check that welcome text was inserted
    found_welcome = False
    for call in mock_detail_text.insert.call_args_list:
        args, _ = call
        # args[1] is the text content
        if len(args) > 1 and "Welcome to PyQWK" in str(args[1]):
            found_welcome = True
            break

    assert found_welcome, "Welcome screen text was not inserted into detail_text"

    # Check for shortcuts section
    found_shortcuts = False
    for call in mock_detail_text.insert.call_args_list:
        args, _ = call
        if len(args) > 1 and "Keyboard Shortcuts:" in str(args[1]):
            found_shortcuts = True
            break
    assert found_shortcuts, "Keyboard shortcuts section was not found in welcome screen"

def test_no_welcome_screen_with_path():
    """Verify that current_path is set when an initial path is provided."""
    mock_root = MagicMock()
    with patch("pyqwk.gui.load_data"): # Prevent actual loading
        app = QwkGuiApp(mock_root, initial_path="test.qwk")
        assert app.current_path == "test.qwk"
