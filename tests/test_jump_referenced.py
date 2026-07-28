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
from pyqwk.core import ParsedMessage, MessageHeader


@pytest.fixture
def app_with_referenced_messages():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.simpledialog"):
        app = QwkGuiApp(root)
        app.current_paths = ["fake.qwk"]

        # Create dummy messages: h2 replies to h1 (refnum 101)
        h1 = MessageHeader(
            " ",
            101,
            "01-01-23",
            "12:00",
            "To1",
            "From1",
            "Subj1",
            "",
            None,
            1,
            " ",
            1,
            1,
            "",
        )
        h2 = MessageHeader(
            " ",
            102,
            "01-01-23",
            "12:05",
            "To2",
            "From2",
            "Subj2",
            "",
            None,
            1,
            " ",
            1,
            1,
            "",
        )
        # Message 1 has no refnum, Message 2 references 101
        msg1 = ParsedMessage("Text 1", 101, None, 1, h1)
        msg2 = ParsedMessage("Text 2", 102, None, 1, h2)
        msg2.refnum = 101

        app.messages = [msg1, msg2]

        # Mock message_list behavior
        app.message_list.exists.return_value = True

        return app


def test_jump_to_referenced_message_no_archive():
    root = MagicMock()
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.messagebox.showwarning") as mock_warning,
    ):
        app = QwkGuiApp(root)
        app.messages = []
        app.current_paths = []

        app.jump_to_referenced_message()

        mock_warning.assert_called_once_with(
            "Go to Referenced Message", "Please open an archive first."
        )


def test_jump_to_referenced_message_no_selection(app_with_referenced_messages):
    app = app_with_referenced_messages
    app.message_list.selection.return_value = []

    with patch("pyqwk.gui.messagebox.showwarning") as mock_warning:
        app.jump_to_referenced_message()

    mock_warning.assert_called_once_with(
        "Go to Referenced Message", "Please select a message first."
    )


def test_jump_to_referenced_message_no_refnum(app_with_referenced_messages):
    app = app_with_referenced_messages
    # Index 0 is msg1 (has no refnum)
    app.message_list.selection.return_value = ["0"]

    with patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.jump_to_referenced_message()

    mock_info.assert_called_once_with(
        "Go to Referenced Message",
        "The selected message does not reference another message (no Reply-To/RefNum)."
    )


def test_jump_to_referenced_message_success(app_with_referenced_messages):
    app = app_with_referenced_messages
    # Index 1 is msg2 (references msgnum 101 in conf 1)
    app.message_list.selection.return_value = ["1"]

    with patch.object(app, "jump_to_message") as mock_jump:
        app.jump_to_referenced_message()

    mock_jump.assert_called_once_with(1, 101)


def test_context_menus_referenced_option(app_with_referenced_messages):
    app = app_with_referenced_messages
    # Verify that treeview context menu includes Go to Referenced Message option
    mock_event = MagicMock()
    mock_event.x = 10
    mock_event.y = 10
    mock_event.x_root = 100
    mock_event.y_root = 100

    # Mock identify_row to return '1' (msg2 which has refnum)
    app.message_list.identify_row.return_value = "1"
    app.message_list.selection.return_value = ["1"]

    with patch("pyqwk.gui.tk.Menu") as mock_menu_cls:
        mock_menu = MagicMock()
        mock_menu_cls.return_value = mock_menu

        app._show_list_context_menu(mock_event)

        # Let's verify add_command was called with label containing "Go to Referenced Message #101"
        command_labels = []
        for args, kwargs in mock_menu.add_command.call_args_list:
            label = kwargs.get("label", "")
            command_labels.append(label)
        assert any("Go to Referenced Message #101" in label for label in command_labels)

        # Now test text context menu
        mock_menu.reset_mock()
        app._show_text_context_menu(mock_event)
        command_labels = []
        for args, kwargs in mock_menu.add_command.call_args_list:
            label = kwargs.get("label", "")
            command_labels.append(label)
        assert any("Go to Referenced Message #101" in label for label in command_labels)
