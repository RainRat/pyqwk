import sys
from unittest.mock import MagicMock, patch
import pytest
import tkinter as tk

from pyqwk.gui import QwkGuiApp


@pytest.fixture
def gui_app(real_tkinter_modules):
    root = real_tkinter_modules.Tk()
    root.withdraw()
    app = QwkGuiApp(root)
    yield app
    try:
        root.destroy()
    except Exception:
        pass


def test_add_attachment_context_commands_single(gui_app, mocker, real_tkinter_modules):
    msg = MagicMock()
    msg.attachments = ["document.pdf"]

    menu = MagicMock(spec=real_tkinter_modules.Menu)
    mock_save = mocker.patch.object(gui_app, "save_attachment")

    gui_app._add_attachment_context_commands(menu, msg)

    # Check menu command added
    menu.add_command.assert_called_once()
    kwargs = menu.add_command.call_args[1]
    assert "Save Attachment (document.pdf)" in kwargs["label"]

    # Execute command callback
    cmd = kwargs["command"]
    cmd()
    mock_save.assert_called_once_with("document.pdf", 0)


def test_add_attachment_context_commands_multiple(gui_app, mocker, real_tkinter_modules):
    msg = MagicMock()
    msg.attachments = ["image.png", "archive.zip"]

    menu = real_tkinter_modules.Menu(gui_app.root, tearoff=0)
    mock_add_cascade = mocker.patch.object(menu, "add_cascade")
    mocker.patch.object(gui_app, "save_attachment")

    gui_app._add_attachment_context_commands(menu, msg)

    # Check sub-menu cascade added
    mock_add_cascade.assert_called_once()
    kwargs = mock_add_cascade.call_args[1]
    assert kwargs["label"] == "Save Attachment..."


def test_show_list_context_menu_with_attachments(gui_app, mocker):
    msg = MagicMock()
    msg.header.msgsubject = "Test Attachment"
    msg.header.msgfrom = "Alice"
    msg.header.msgto = "Bob"
    msg.header.msgnum = 1
    msg.refnum = None
    msg.confnum = 101
    msg.bbs_name = "BBS"
    msg.bbs_id = "BBS"
    msg.attachments = ["file.txt"]

    gui_app.messages = [msg]
    gui_app.board_dict = {101: "General"}

    mocker.patch.object(gui_app.message_list, "identify_region", return_value="cell")
    mocker.patch.object(gui_app.message_list, "identify_row", return_value="0")
    mocker.patch.object(gui_app.message_list, "selection_set")
    mocker.patch.object(gui_app.message_list, "focus")

    mock_menu_class = mocker.patch("tkinter.Menu")
    mock_menu_inst = mock_menu_class.return_value

    event = MagicMock(x=10, y=10, x_root=100, y_root=200)
    gui_app._show_list_context_menu(event)

    # Verify that add_command was called with Save Attachment label
    labels = [call[1].get("label") for call in mock_menu_inst.add_command.call_args_list if "label" in call[1]]
    assert any("Save Attachment (file.txt)" in l for l in labels if l)


def test_show_text_context_menu_with_attachments(gui_app, mocker):
    msg = MagicMock()
    msg.header.msgsubject = "Test Attachment Text Menu"
    msg.header.msgfrom = "Alice"
    msg.header.msgto = "Bob"
    msg.header.msgnum = 2
    msg.refnum = None
    msg.confnum = 101
    msg.bbs_name = "BBS"
    msg.bbs_id = "BBS"
    msg.attachments = ["test.dat"]

    gui_app.messages = [msg]
    gui_app.board_dict = {101: "General"}

    mocker.patch.object(gui_app.message_list, "selection", return_value=["0"])
    mocker.patch.object(gui_app.detail_text, "tag_ranges", return_value=())

    mock_menu_class = mocker.patch("tkinter.Menu")
    mock_menu_inst = mock_menu_class.return_value

    event = MagicMock(x=10, y=10, x_root=100, y_root=200)
    gui_app._show_text_context_menu(event)

    labels = [call[1].get("label") for call in mock_menu_inst.add_command.call_args_list if "label" in call[1]]
    assert any("Save Attachment (test.dat)" in l for l in labels if l)
