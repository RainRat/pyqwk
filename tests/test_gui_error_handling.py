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

from pyqwk.core import ParsedMessage, MessageHeader


@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):

        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)
        mock_tk.NORMAL = "normal"
        mock_tk.DISABLED = "disabled"
        mock_tk.END = "end"

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }


def get_app():
    from pyqwk.gui import QwkGuiApp

    root = MagicMock()
    return QwkGuiApp(root)


def test_load_messages_restores_state_on_error(mock_gui_deps):
    app = get_app()

    # Setup initial state
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    initial_msg = ParsedMessage("Initial Body", 1, None, 1, header)
    app.messages = [initial_msg]
    app.current_path = "initial.qwk"
    app.board_dict = {1: "General"}
    app._cache = {"path": "initial.qwk", "file_data": b"", "board_dict": app.board_dict}
    app.root.title.return_value = "Initial BBS (initial.qwk) - PyQWK Reader"

    # Mock load_data to fail for the new file
    with patch("pyqwk.gui.load_data", side_effect=Exception("Load failed")):
        app.load_messages("failed.qwk")

        # Verify error message was shown
        mock_gui_deps["messagebox"].showerror.assert_called_with(
            "Failed to load QWK", "Load failed"
        )

        # Verify state was restored
        assert app.messages == [initial_msg]
        assert app.current_path == "initial.qwk"
        assert app.board_dict == {1: "General"}
        assert app._cache["path"] == "initial.qwk"

        # Verify status label was reset to show initial state
        app.status_label.config.assert_any_call(
            text="Showing 1 messages from Initial BBS (initial.qwk)"
        )


def test_load_messages_first_time_failure(mock_gui_deps):
    app = get_app()
    app.messages = []
    app.current_path = None

    with patch("pyqwk.gui.load_data", side_effect=Exception("First load failed")):
        app.load_messages("first.qwk")

        assert app.messages == []
        assert app.current_path is None
        app.status_label.config.assert_any_call(text="Ready")
        app.root.title.assert_any_call("PyQWK Reader")
