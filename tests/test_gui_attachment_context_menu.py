import tkinter as tk
from unittest.mock import MagicMock, patch
from pyqwk.core import MessageHeader, ParsedMessage
from pyqwk.gui import QwkGuiApp


def _create_test_header(msgnum=1, confnum=1, subject="Subj", msgfrom="Author", msgto="User"):
    return MessageHeader(" ", msgnum, "01-01-24", "10:00", msgto, msgfrom, subject, "", None, 1, " ", 0, "", confnum)


def _create_test_msg(attachments=None):
    hdr = _create_test_header()
    return ParsedMessage("Hello world", 1, None, 1, hdr, attachments=attachments or [])


def test_add_attachment_context_commands_single():
    root = tk.Tk()
    app = QwkGuiApp(root)

    msg = _create_test_msg(attachments=["test_image.png"])

    menu = tk.Menu(root)
    with patch.object(menu, "add_command") as mock_add_cmd:
        app._add_attachment_context_commands(menu, msg)
        mock_add_cmd.assert_called_once()
        kwargs = mock_add_cmd.call_args[1]
        assert "Save Attachment 'test_image.png'..." in kwargs["label"]

    root.destroy()


def test_add_attachment_context_commands_multiple():
    root = tk.Tk()
    app = QwkGuiApp(root)

    msg = _create_test_msg(attachments=["file1.bin", "file2.bin"])

    menu = tk.Menu(root)
    with patch.object(menu, "add_cascade") as mock_add_cascade:
        app._add_attachment_context_commands(menu, msg)
        mock_add_cascade.assert_called_once()
        kwargs = mock_add_cascade.call_args[1]
        assert "Save Attachment (2 files)" in kwargs["label"]

    root.destroy()


def test_show_list_context_menu_with_attachment():
    root = tk.Tk()
    app = QwkGuiApp(root)

    msg = _create_test_msg(attachments=["single_doc.pdf"])
    app.messages = [msg]
    app.message_list.insert("", "end", iid="0", text="Subj")

    with patch.object(app.message_list, "identify_region", return_value="cell"), \
         patch.object(app.message_list, "identify_row", return_value="0"), \
         patch.object(tk.Menu, "post") as mock_post:

        event = MagicMock()
        event.x = 10
        event.y = 10
        event.x_root = 100
        event.y_root = 100

        app._show_list_context_menu(event)
        mock_post.assert_called_once_with(100, 100)

    root.destroy()


def test_show_text_context_menu_with_attachment():
    root = tk.Tk()
    app = QwkGuiApp(root)

    msg = _create_test_msg(attachments=["single_doc.pdf"])
    app.messages = [msg]
    app.message_list.insert("", "end", iid="0", text="Subj")
    app.message_list.selection_set("0")

    with patch.object(tk.Menu, "post") as mock_post:
        event = MagicMock()
        event.x = 10
        event.y = 10
        event.x_root = 100
        event.y_root = 100

        app._show_text_context_menu(event)
        mock_post.assert_called_once_with(100, 100)

    root.destroy()
