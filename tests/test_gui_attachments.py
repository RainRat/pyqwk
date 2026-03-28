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

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.filedialog") as mock_fd, \
         patch("pyqwk.gui.messagebox") as mock_mb:

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
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }

def test_gui_renders_attachments(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='All', msgfrom='User', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )
    message = ParsedMessage(
        text="Body",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        attachments=["file1.zip", "image.jpg"]
    )

    app.messages = [message]
    app.board_dict = {1: "General"}

    # Trigger rendering of the message
    app._render_message(0)

    # Check if "Attachments: " label was inserted
    app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Attachments: ", "header_label")
    # Check if attachment names were inserted as links
    # Note: Using id(message) in tags
    msg_id = id(message)
    app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "file1.zip", ("link", f"attach_link_{msg_id}_0"))
    app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "image.jpg", ("link", f"attach_link_{msg_id}_1"))
