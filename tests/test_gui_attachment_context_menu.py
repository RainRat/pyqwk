from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp


class DummyEvent:
    def __init__(self, x=10, y=10, x_root=100, y_root=100):
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root


class DummyHeader:
    def __init__(self, msgnum=1, confnum=1, msgsubject="Subject", msgfrom="Author", msgto="Recipient", is_private=False):
        self.msgnum = msgnum
        self.confnum = confnum
        self.msgsubject = msgsubject
        self.msgfrom = msgfrom
        self.msgto = msgto
        self.is_private = is_private


class DummyMessage:
    def __init__(self, msgnum=1, confnum=1, subject="Subject", author="Author", recipient="Recipient", attachments=None, refnum=None):
        self.header = DummyHeader(msgnum=msgnum, confnum=confnum, msgsubject=subject, msgfrom=author, msgto=recipient)
        self.attachments = attachments or []
        self.refnum = refnum
        self.bbs_name = "Test BBS"
        self.bbs_id = "TESTBBS"
        self.confnum = confnum
        self.text = "Hello world"


def test_single_attachment_list_context_menu(real_tkinter_modules):
    root = real_tkinter_modules.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        msg = DummyMessage(attachments=["image.png"])
        app.messages = [msg]
        app.message_list.insert("", real_tkinter_modules.END, iid="0", text="Subject", values=("", "1", "Author", "Recipient", "", "", "", "", "", ""))
        app.message_list.identify_region = MagicMock(return_value="cell")
        app.message_list.identify_row = MagicMock(return_value="0")

        posted_menus = []
        orig_post = real_tkinter_modules.Menu.post

        def mock_post(menu_obj, x, y):
            posted_menus.append(menu_obj)

        real_tkinter_modules.Menu.post = mock_post
        try:
            app._show_list_context_menu(DummyEvent())
        finally:
            real_tkinter_modules.Menu.post = orig_post

        assert len(posted_menus) == 1
        menu = posted_menus[0]

        labels = []
        for i in range(menu.index("end") + 1):
            try:
                labels.append(menu.entrycget(i, "label"))
            except Exception:
                pass

        assert "Save Attachment (image.png)" in labels
    finally:
        root.destroy()


def test_multiple_attachments_text_context_menu(real_tkinter_modules):
    root = real_tkinter_modules.Tk()
    root.withdraw()
    try:
        app = QwkGuiApp(root)
        msg = DummyMessage(attachments=["doc.pdf", "archive.zip"])
        app.messages = [msg]
        app.message_list.insert("", real_tkinter_modules.END, iid="0", text="Subject", values=("", "1", "Author", "Recipient", "", "", "", "", "", ""))
        app.message_list.selection = MagicMock(return_value=("0",))

        posted_menus = []
        orig_post = real_tkinter_modules.Menu.post

        def mock_post(menu_obj, x, y):
            posted_menus.append(menu_obj)

        real_tkinter_modules.Menu.post = mock_post
        try:
            app._show_text_context_menu(DummyEvent())
        finally:
            real_tkinter_modules.Menu.post = orig_post

        assert len(posted_menus) == 1
        menu = posted_menus[0]

        labels = []
        for i in range(menu.index("end") + 1):
            try:
                labels.append(menu.entrycget(i, "label"))
            except Exception:
                pass

        assert "Save Attachment (2)" in labels
    finally:
        root.destroy()
