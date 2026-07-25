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

        # Create some dummy messages
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
        h3 = MessageHeader(
            " ",
            103,
            "01-01-23",
            "12:10",
            "To3",
            "From3",
            "Subj3",
            "",
            None,
            1,
            " ",
            2,
            1,
            "",
        )

        app.messages = [
            ParsedMessage("Text 1", 101, None, 1, h1),  # No refnum
            ParsedMessage("Text 2", 102, 101, 1, h2),   # References 101
            ParsedMessage("Text 3", 103, "invalid", 2, h3), # Invalid non-numeric refnum
        ]

        # Mock message_list behavior
        app.message_list.exists.return_value = True

        # Ensure filters appear inactive
        app.search_var.get.return_value = ""
        app.bbs_combo.get.return_value = "All BBSes"
        app.conf_combo.get.return_value = "All Conferences"
        for var in [
            app.has_attach_var,
            app.mine_var,
            app.on_this_day_var,
            app.has_links_var,
            app.has_emails_var,
            app.has_phones_var,
            app.has_ansi_var,
        ]:
            var.get.return_value = False

        return app


def test_jump_to_referenced_message_no_archive():
    root = MagicMock()
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.simpledialog"),
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

    # Mock jump_to_message
    app.jump_to_message = MagicMock()

    app.jump_to_referenced_message()

    app.jump_to_message.assert_not_called()


def test_jump_to_referenced_message_invalid_selection(app_with_referenced_messages):
    app = app_with_referenced_messages
    app.message_list.selection.return_value = ["invalid_index"]

    app.jump_to_message = MagicMock()

    app.jump_to_referenced_message()

    app.jump_to_message.assert_not_called()


def test_jump_to_referenced_message_no_refnum(app_with_referenced_messages):
    app = app_with_referenced_messages
    # Selection index 0 is msg 101, which has refnum=None
    app.message_list.selection.return_value = ["0"]

    with patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.jump_to_referenced_message()

    mock_info.assert_called_once_with(
        "Go to Referenced Message",
        "The selected message does not reference any other message.",
    )


def test_jump_to_referenced_message_with_refnum_success(app_with_referenced_messages):
    app = app_with_referenced_messages
    # Selection index 1 is msg 102, which has refnum=101
    app.message_list.selection.return_value = ["1"]

    app.jump_to_message = MagicMock()

    app.jump_to_referenced_message()

    app.jump_to_message.assert_called_once_with(1, 101)


def test_jump_to_referenced_message_with_refnum_invalid_value(app_with_referenced_messages):
    app = app_with_referenced_messages
    # Selection index 2 is msg 103, which has refnum="invalid"
    app.message_list.selection.return_value = ["2"]

    app.jump_to_message = MagicMock()

    app.jump_to_referenced_message()

    app.jump_to_message.assert_not_called()
