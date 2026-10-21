from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader


def _make_header(msgnum=1, msgto="All", msgfrom="Alice", msgsubject="Test"):
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-2025",
        msgtime="12:00",
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )


def test_add_attachment_context_commands_single():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        hdr = _make_header(msgnum=10, msgsubject="Test Single")
        msg = ParsedMessage(
            header=hdr,
            text="Body",
            attachments=["file1.zip"],
            msgnum=10,
            refnum=0,
            confnum=1,
        )

        menu = MagicMock()
        app._add_attachment_context_commands(menu, msg)

        menu.add_separator.assert_called_once()
        menu.add_command.assert_called_once()
        _, kwargs = menu.add_command.call_args
        assert "Save Attachment (file1.zip)" in kwargs["label"]

        cmd_fn = kwargs["command"]
        with patch.object(app, "save_attachment") as mock_save:
            cmd_fn()
            mock_save.assert_called_once_with("file1.zip", 0)


def test_add_attachment_context_commands_multiple():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        hdr = _make_header(msgnum=11, msgsubject="Test Multi")
        msg = ParsedMessage(
            header=hdr,
            text="Body",
            attachments=["image1.png", "doc2.pdf"],
            msgnum=11,
            refnum=0,
            confnum=1,
        )

        menu = MagicMock()
        attach_sub_menu = MagicMock()
        mock_tk.Menu.return_value = attach_sub_menu

        mock_extract = MagicMock()
        app.extract_all_attachments = mock_extract

        app._add_attachment_context_commands(menu, msg)

        menu.add_separator.assert_called_once()
        assert attach_sub_menu.add_command.call_count == 3  # 2 files + 1 Extract All
        attach_sub_menu.add_separator.assert_called_once()
        menu.add_cascade.assert_called_once()
        _, kwargs = menu.add_cascade.call_args
        assert "Save Attachments (2)..." in kwargs["label"]

        # Call individual file save command
        first_call = attach_sub_menu.add_command.call_args_list[0]
        cmd_fn = first_call.kwargs["command"]
        with patch.object(app, "save_attachment") as mock_save:
            cmd_fn()
            mock_save.assert_called_once_with("image1.png", 0)

        # Call extract all command
        extract_call = attach_sub_menu.add_command.call_args_list[2]
        extract_fn = extract_call.kwargs["command"]
        extract_fn()
        mock_extract.assert_called_once()


def test_add_attachment_context_commands_no_attachments():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        hdr = _make_header(msgnum=12, msgsubject="Test None")
        msg = ParsedMessage(
            header=hdr,
            text="Body",
            attachments=[],
            msgnum=12,
            refnum=0,
            confnum=1,
        )

        menu = MagicMock()
        app._add_attachment_context_commands(menu, msg)

        menu.add_separator.assert_not_called()
        menu.add_command.assert_not_called()
