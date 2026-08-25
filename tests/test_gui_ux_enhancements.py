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
    # Mock search_var as it's initialized with tk.StringVar()
    with patch("tkinter.StringVar"), patch("tkinter.BooleanVar"):
        app = QwkGuiApp(root)
        app.search_var = MagicMock()
        return app


def test_block_text_input_logic(app):
    """Verify that _block_text_input allows specific shortcuts and blocks others."""
    # Control+C
    event_c = MagicMock(state=0x4, keysym="c")
    assert app._block_text_input(event_c) is None

    # Control+A
    event_a = MagicMock(state=0x4, keysym="a")
    assert app._block_text_input(event_a) is None

    # Navigation key
    event_up = MagicMock(state=0, keysym="Up")
    assert app._block_text_input(event_up) is None

    # Regular key (typing 'x')
    event_x = MagicMock(state=0, keysym="x")
    assert app._block_text_input(event_x) == "break"


def test_pivot_filter_author(app):
    """Verify that pivoting by author updates the search variable and reloads."""
    app.reload_messages = MagicMock()
    app._pivot_filter(author="Sysop")
    app.search_var.set.assert_called_once_with("Sysop")
    app.reload_messages.assert_called_once()


def test_pivot_filter_conference(app):
    """Verify that pivoting by conference updates the combobox and reloads."""
    app.reload_messages = MagicMock()
    app.conf_combo = MagicMock()
    app.conf_combo.__getitem__.return_value = [
        "All Conferences (10)",
        "1: General (5)",
        "2: Tech (5)",
    ]

    app._pivot_filter(conf_num=1)
    app.conf_combo.current.assert_called_once_with(1)
    app.reload_messages.assert_called_once()


def test_copy_to_clipboard(app):
    """Verify clipboard interaction."""
    app.root.clipboard_clear = MagicMock()
    app.root.clipboard_append = MagicMock()

    app._copy_to_clipboard("test text")
    app.root.clipboard_clear.assert_called_once()
    app.root.clipboard_append.assert_called_once_with("test text")


def test_show_list_context_menu(app):
    """Verify that right-clicking the list triggers menu posting."""
    event = MagicMock(x_root=100, y_root=100, y=50)
    app.message_list.identify_row.return_value = "0"

    # Setup messages so indexing works
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    app.messages = [
        ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=header)
    ]
    app.board_dict = {1: "General"}

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_list_context_menu(event)

        app.message_list.selection_set.assert_called_with("0")
        mock_menu_instance.post.assert_called_once_with(100, 100)

        # Check for expected commands including "Copy Full Message"
        calls = [c[1]["label"] for c in mock_menu_instance.add_command.call_args_list]
        assert "Copy Subject" in calls
        assert "Copy From" in calls
        assert "Copy To" in calls
        assert "Copy Num" in calls
        assert "Copy Full Message" in calls

        # Find the command callback for "Copy Full Message" and run it to verify behavior
        copy_full_call = [c for c in mock_menu_instance.add_command.call_args_list if c[1]["label"] == "Copy Full Message"][0]
        cmd_cb = copy_full_call[1]["command"]

        app.detail_text.get.return_value = "Full Formatted Message Content"
        app._copy_to_clipboard = MagicMock()
        cmd_cb()
        app._copy_to_clipboard.assert_called_once_with(
            "Full Formatted Message Content", "Full Message"
        )


def test_show_text_context_menu(app):
    """Verify that right-clicking the text triggers menu posting with metadata filters."""
    event = MagicMock(x_root=200, y_root=200)

    # Mock selection
    app.message_list.selection.return_value = ("0",)
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    app.messages = [
        ParsedMessage(
            text="Hello",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
            bbs_name="TestBBS",
        )
    ]
    app.board_dict = {1: "General"}

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_text_context_menu(event)

        # Check for expected commands: Copy, Select All, Copy Full Message, Filter by Author, Conf, BBS
        calls = [c[1]["label"] for c in mock_menu_instance.add_command.call_args_list]
        assert "Copy" in calls
        assert "Select All" in calls
        assert "Copy Full Message" in calls
        assert any("Filter by Author: Bob" == c for c in calls)
        assert any("Filter by Conference: General" == c for c in calls)
        assert any("Filter by BBS: TestBBS" == c for c in calls)

        mock_menu_instance.post.assert_called_once_with(200, 200)
