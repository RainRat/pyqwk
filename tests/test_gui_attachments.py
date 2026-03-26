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
    # In the updated code, each filename is inserted individually with a specific tag
    # Check if filenames were inserted
    inserted_texts = [c[0][1] for c in app.detail_text.insert.call_args_list]
    assert "file1.zip" in inserted_texts
    assert "image.jpg" in inserted_texts

def test_save_attachment_logic(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    msg = ParsedMessage(
        text="Dummy content with UUE\nbegin 644 test.txt\n!\r\n` \nend",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=MagicMock()
    )

    mock_gui_deps["filedialog"].asksaveasfilename.return_value = "/tmp/test.txt"

    with patch("pyqwk.gui.extract_binaries") as mock_ext, \
         patch("builtins.open", new_callable=MagicMock) as mock_open:
        mock_ext.return_value = [("test.txt", b"decoded")]

        app.save_attachment(msg, "test.txt")

        mock_open.assert_called_with("/tmp/test.txt", "wb")
        mock_open.return_value.__enter__.return_value.write.assert_called_with(b"decoded")

def test_extract_filtered_attachments_logic(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    msg = ParsedMessage(
        text="Content",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=MagicMock(),
        attachments=["test.bin"]
    )
    app.messages = [msg]

    mock_gui_deps["filedialog"].askdirectory.return_value = "/tmp/extract"

    with patch("pyqwk.gui.extract_binaries") as mock_ext, \
         patch("builtins.open", new_callable=MagicMock) as mock_open, \
         patch("os.path.exists", return_value=False):
        mock_ext.return_value = [("test.bin", b"data")]

        app.extract_filtered_attachments()

        mock_open.assert_called()
        assert "Successfully extracted 1 attachments" in mock_gui_deps["messagebox"].showinfo.call_args[0][1]
