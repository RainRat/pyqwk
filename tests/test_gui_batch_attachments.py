import sys
import os
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

def test_extract_all_attachments(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Setup messages with attachments
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='All', msgfrom='User', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )

    # Message with UUE attachment
    uue_text = "begin 644 test.txt\n#0V%T\n`\nend"
    message = ParsedMessage(
        text=uue_text,
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    app.messages = [message]

    def get_children_side_effect(parent=""):
        if parent == "":
            return ["0"]
        return []
    app.message_list.get_children.side_effect = get_children_side_effect

    # Mock askdirectory to return tmp_path
    mock_gui_deps["filedialog"].askdirectory.return_value = str(tmp_path)

    # Trigger extraction
    app.extract_all_attachments()

    # Check if file was created
    target_file = tmp_path / "test.txt"
    assert target_file.exists()
    assert target_file.read_text().strip() == "Cat"

def test_save_individual_attachment(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Setup message with attachment
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='All', msgfrom='User', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )

    uue_text = "begin 644 test_save.txt\n#0V%T\n`\nend"
    message = ParsedMessage(
        text=uue_text,
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    app.messages = [message]
    app.message_list.selection.return_value = ["0"]

    # Mock asksaveasfilename
    save_path = tmp_path / "saved_test.txt"
    mock_gui_deps["filedialog"].asksaveasfilename.return_value = str(save_path)

    # Trigger individual save
    app.save_attachment("test_save.txt", 0)

    # Check if file was created
    assert save_path.exists()
    assert save_path.read_text().strip() == "Cat"
