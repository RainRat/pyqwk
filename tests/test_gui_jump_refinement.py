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
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp


@pytest.fixture
def app():
    root = MagicMock()
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.simpledialog"),
    ):
        # Ensure distinct mocks for each Variable call to avoid crosstalk
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        return app


def test_prompt_jump_to_message_with_empty_view_but_loaded_archives(app):
    """Verify that Jump to Message works even if the current filtered view is empty."""
    # Archive is loaded
    app.current_paths = ["test.qwk"]
    # But current view is empty (due to filters)
    app.messages = []

    # Mock askinteger to return a message number
    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=123) as mock_ask,
        patch.object(app, "_is_any_filter_active", return_value=True),
        patch("pyqwk.gui.messagebox.askyesno", return_value=True) as mock_ask_reset,
        patch.object(app, "clear_filters") as mock_clear,
    ):
        app.prompt_jump_to_message()

        mock_ask.assert_called_once()
        # It should check for filters and ask to reset because messages list is empty
        mock_ask_reset.assert_called_once()
        mock_clear.assert_called_once()


def test_prompt_jump_to_message_disabled_when_no_archive(app):
    """Verify that Jump to Message does nothing if no archive is loaded."""
    app.current_paths = []
    app.messages = []

    with patch("pyqwk.gui.simpledialog.askinteger") as mock_ask:
        app.prompt_jump_to_message()
        mock_ask.assert_not_called()
