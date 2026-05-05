import sys
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import ParsedMessage, MessageHeader

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp


@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, patch("pyqwk.gui.ttk") as mock_ttk:
        mock_tk.END = "end"
        mock_tk.INSERT = "insert"

        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }


def test_gui_message_list_icons_and_tags(mock_gui_deps):
    """Verify that private messages and attachments show correct icons and tags in the treeview."""
    root = MagicMock()
    app = QwkGuiApp(root)

    # 1. Private message with attachments (Index 0, even in 0-based, so NO zebra stripe)
    h1 = MessageHeader(
        status="*",  # '*' is private
        msgnum=101,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Sender",
        msgsubject="Private with Attach",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    m1 = ParsedMessage(
        text="Body",
        msgnum=101,
        refnum=None,
        confnum=1,
        header=h1,
        attachments=["file.zip"],
    )

    # 2. Public message without attachments (Index 1, odd, YES zebra stripe)
    h2 = MessageHeader(
        status=" ",  # ' ' is public
        msgnum=102,
        msgdate="01-01-23",
        msgtime="12:05",
        msgto="All",
        msgfrom="Sender",
        msgsubject="Public No Attach",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    m2 = ParsedMessage(
        text="Body", msgnum=102, refnum=None, confnum=1, header=h2, attachments=[]
    )

    # 3. Private message without attachments (Index 2, even, NO zebra stripe)
    h3 = MessageHeader(
        status="*",
        msgnum=103,
        msgdate="01-01-23",
        msgtime="12:10",
        msgto="Recipient",
        msgfrom="Sender",
        msgsubject="Private No Attach",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    m3 = ParsedMessage(
        text="Body", msgnum=103, refnum=None, confnum=1, header=h3, attachments=None
    )

    # 4. Private message with attachments (Index 3, odd, YES zebra stripe AND private tag)
    h4 = MessageHeader(
        status="*",
        msgnum=104,
        msgdate="01-01-23",
        msgtime="12:15",
        msgto="Recipient",
        msgfrom="Sender",
        msgsubject="Private odd index",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    m4 = ParsedMessage(
        text="Body",
        msgnum=104,
        refnum=None,
        confnum=1,
        header=h4,
        attachments=["image.png"],
    )

    messages = [m1, m2, m3, m4]
    board_dict = {1: "General"}

    # Mock load_data to return our test messages
    with (
        patch("pyqwk.gui.load_data", return_value=(messages, board_dict)),
        patch("pyqwk.gui.matches_filters", return_value=True),
        patch("pyqwk.gui.process_message", side_effect=lambda t, *args: t),
    ):
        app.load_messages("dummy.qwk")

    # Verify Treeview insertions

    # Message 1: Private (🔒) + Attach (📎), Tag: private
    app.message_list.insert.assert_any_call(
        "",
        "end",
        iid="0",
        text="Private with Attach",
        values=(
            "🔒📎",
            101,
            "Sender",
            "Recipient",
            "01-01-23 12:00",
            "4 B",
            "General",
            "",
        ),
        open=True,
        tags=("private",),
    )

    # Message 2: Public, No Attach, Tag: even
    app.message_list.insert.assert_any_call(
        "",
        "end",
        iid="1",
        text="Public No Attach",
        values=("", 102, "Sender", "All", "01-01-23 12:05", "4 B", "General", ""),
        open=True,
        tags=("even",),
    )

    # Message 3: Private (🔒), No Attach, Tag: private
    app.message_list.insert.assert_any_call(
        "",
        "end",
        iid="2",
        text="Private No Attach",
        values=(
            "🔒",
            103,
            "Sender",
            "Recipient",
            "01-01-23 12:10",
            "4 B",
            "General",
            "",
        ),
        open=True,
        tags=("private",),
    )

    # Message 4: Private (🔒) + Attach (📎), Tag: even, private
    app.message_list.insert.assert_any_call(
        "",
        "end",
        iid="3",
        text="Private odd index",
        values=(
            "🔒📎",
            104,
            "Sender",
            "Recipient",
            "01-01-23 12:15",
            "4 B",
            "General",
            "",
        ),
        open=True,
        tags=("even", "private"),
    )
