import os
import tkinter as tk
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader


def _make_header(msgnum=101, subject="Test"):
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="All",
        msgfrom="Alice",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
        msgsubject=subject,
    )


def test_add_attachment_context_commands_single(real_tkinter_modules):
    """Test _add_attachment_context_commands with a single attachment using real tkinter modules."""
    root = real_tkinter_modules.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        menu = real_tkinter_modules.Menu(root, tearoff=0)

        header = _make_header(101, "Attachment Test")
        msg = ParsedMessage(
            header=header,
            text="Sample text",
            msgnum=101,
            refnum=0,
            confnum=1,
            attachments=["test1.zip"],
        )

        app._add_attachment_context_commands(menu, msg)

        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) != "separator"]
        assert "Save Attachment: test1.zip" in labels
        assert "Extract All Attachments..." in labels
    finally:
        root.destroy()


def test_add_attachment_context_commands_multiple(real_tkinter_modules):
    """Test _add_attachment_context_commands with multiple attachments using real tkinter modules."""
    root = real_tkinter_modules.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        menu = real_tkinter_modules.Menu(root, tearoff=0)

        header = _make_header(102, "Multiple Attachments")
        msg = ParsedMessage(
            header=header,
            text="Sample text",
            msgnum=102,
            refnum=0,
            confnum=1,
            attachments=["file1.zip", "file2.gif"],
        )

        app._add_attachment_context_commands(menu, msg)

        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) != "separator"]
        assert "Save Attachment" in labels
        assert "Extract All Attachments..." in labels
    finally:
        root.destroy()


def test_add_attachment_context_commands_none(real_tkinter_modules):
    """Test _add_attachment_context_commands when message has no attachments using real tkinter modules."""
    root = real_tkinter_modules.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        menu = real_tkinter_modules.Menu(root, tearoff=0)

        header = _make_header(103, "No Attachments")
        msg = ParsedMessage(
            header=header,
            text="Sample text",
            msgnum=103,
            refnum=0,
            confnum=1,
            attachments=[],
        )

        app._add_attachment_context_commands(menu, msg)

        assert menu.index("end") is None
    finally:
        root.destroy()
