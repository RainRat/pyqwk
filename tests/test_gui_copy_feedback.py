import sys
from unittest.mock import MagicMock, patch

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

import pytest
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader


@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    with patch("tkinter.StringVar"), patch("tkinter.BooleanVar"):
        app = QwkGuiApp(root)
        app.search_var = MagicMock()
        app.status_label = MagicMock()
        return app


def test_copy_to_clipboard_feedback(app):
    """Verify that _copy_to_clipboard updates status_label when a label is provided."""
    app.root.clipboard_clear = MagicMock()
    app.root.clipboard_append = MagicMock()

    app._copy_to_clipboard("test text", "Subject")
    app.root.clipboard_clear.assert_called_once()
    app.root.clipboard_append.assert_called_once_with("test text")
    app.status_label.config.assert_called_once_with(text="Copied Subject to clipboard")


def test_list_context_menu_copy_labels(app):
    """Verify that context menu commands pass label arguments to _copy_to_clipboard."""
    event = MagicMock(x_root=100, y_root=100, y=50)
    app.message_list.identify_row.return_value = "0"

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    app.messages = [
        ParsedMessage(text="Hello World", msgnum=1, refnum=None, confnum=1, header=header)
    ]
    app.board_dict = {1: "General"}

    app._copy_to_clipboard = MagicMock()

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_list_context_menu(event)

        # Retrieve commands
        command_map = {
            c[1]["label"]: c[1]["command"]
            for c in mock_menu_instance.add_command.call_args_list
        }

        # Test Copy Subject command callback
        command_map["Copy Subject"]()
        app._copy_to_clipboard.assert_called_with("Test Subject", "Subject")

        # Test Copy From command callback
        command_map["Copy From"]()
        app._copy_to_clipboard.assert_called_with("Bob", "From")

        # Test Copy To command callback
        command_map["Copy To"]()
        app._copy_to_clipboard.assert_called_with("Alice", "To")

        # Test Copy Num command callback
        command_map["Copy Num"]()
        app._copy_to_clipboard.assert_called_with("1", "Num")

        # Test Copy Full Message command callback
        app.detail_text.get.return_value = "Full Message Text"
        command_map["Copy Full Message"]()
        app._copy_to_clipboard.assert_called_with("Full Message Text", "Full Message")
