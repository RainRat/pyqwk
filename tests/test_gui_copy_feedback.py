import sys
from unittest.mock import MagicMock, patch

# Mock tkinter modules before importing pyqwk.gui for headless unit tests
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
        app.status_label = MagicMock()
        return app


def test_copy_to_clipboard_status_feedback(app):
    app.root.clipboard_clear = MagicMock()
    app.root.clipboard_append = MagicMock()

    # Test copy with label
    app._copy_to_clipboard("Test Subject Text", "Subject")
    app.root.clipboard_clear.assert_called_once()
    app.root.clipboard_append.assert_called_once_with("Test Subject Text")
    app.status_label.config.assert_called_with(text="Copied Subject to clipboard")

    # Test copy without label
    app._copy_to_clipboard("Generic Text")
    app.status_label.config.assert_called_with(text="Copied to clipboard")
