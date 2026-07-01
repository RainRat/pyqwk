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
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):
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


def setup_tree_mock(app, root_items):
    app._get_all_tree_items = MagicMock(return_value=root_items)


def test_gui_renders_attachments(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="All",
        msgfrom="User",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    message = ParsedMessage(
        text="Body",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        attachments=["file1.zip", "image.jpg"],
    )

    app.messages = [message]
    app.board_dict = {1: "General"}

    # Trigger rendering of the message
    app._render_message(0)

    # Check if "Attach: " label was inserted
    app.detail_text.insert.assert_any_call(
        mock_gui_deps["tk"].END, f"{'Attach:':<8} ", "header_meta_label"
    )
    # Check if attachment names were inserted as links
    msg_id = id(message)
    app.detail_text.insert.assert_any_call(
        mock_gui_deps["tk"].END, "file1.zip", ("link", "header_meta", f"attach_link_{msg_id}_0")
    )
    app.detail_text.insert.assert_any_call(
        mock_gui_deps["tk"].END, "image.jpg", ("link", "header_meta", f"attach_link_{msg_id}_1")
    )



def test_extract_all_attachments_base(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="All",
        msgfrom="User",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
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
    setup_tree_mock(app, ["0"])

    # Mock askdirectory to return tmp_path
    mock_gui_deps["filedialog"].askdirectory.return_value = str(tmp_path)

    # Trigger extraction
    app.extract_all_attachments()

    # Check if file was created
    target_file = tmp_path / "test.txt"
    assert target_file.exists()
    assert target_file.read_text().strip() == "Cat"


def test_save_individual_attachment_base(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="All",
        msgfrom="User",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
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


def test_save_attachment_no_selection(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    app.message_list.selection.return_value = []

    app.save_attachment("test.zip", 0)
    mock_gui_deps["filedialog"].asksaveasfilename.assert_not_called()


def test_save_attachment_missing_text(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    app.messages = [
        ParsedMessage(text="", msgnum=1, refnum=None, confnum=1, header=header)
    ]
    app.message_list.selection.return_value = ["0"]

    app.save_attachment("test.zip", 0)
    mock_gui_deps["filedialog"].asksaveasfilename.assert_not_called()


def test_save_attachment_invalid_index(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    # Message with one attachment
    app.messages = [
        ParsedMessage(
            text="begin 644 t.txt\n`\nend",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
        )
    ]
    app.message_list.selection.return_value = ["0"]

    # Try to save index 1 (out of bounds)
    app.save_attachment("test.zip", 1)
    mock_gui_deps["filedialog"].asksaveasfilename.assert_not_called()


def test_save_attachment_exception_handling(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    app.messages = [
        ParsedMessage(
            text="begin 644 t.txt\n#0V%T\n`\nend",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
        )
    ]
    app.message_list.selection.return_value = ["0"]

    mock_gui_deps["filedialog"].asksaveasfilename.return_value = "/invalid/path/t.txt"

    original_open = open

    def mock_open(file, mode="r", **kwargs):
        if "/invalid/path" in str(file):
            raise IOError("Mock Permission Denied")
        return original_open(file, mode, **kwargs)

    with patch("builtins.open", side_effect=mock_open):
        app.save_attachment("t.txt", 0)
        mock_gui_deps["messagebox"].showerror.assert_called_once()
        assert "Mock Permission Denied" in str(
            mock_gui_deps["messagebox"].showerror.call_args
        )


def test_extract_all_attachments_empty_messages(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    app.messages = []

    app.extract_all_attachments()
    mock_gui_deps["messagebox"].showwarning.assert_called_once()
    mock_gui_deps["filedialog"].askdirectory.assert_not_called()


def test_extract_all_attachments_cancelled_folder(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)
    app.messages = [
        ParsedMessage(text="body", msgnum=1, refnum=None, confnum=1, header=MagicMock())
    ]
    mock_gui_deps["filedialog"].askdirectory.return_value = ""

    app._get_all_tree_items = MagicMock()
    app.extract_all_attachments()
    app._get_all_tree_items.assert_not_called()


def test_extract_all_attachments_missing_text(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)
    app.messages = [
        ParsedMessage(text="", msgnum=1, refnum=None, confnum=1, header=MagicMock())
    ]
    setup_tree_mock(app, ["0"])
    mock_gui_deps["filedialog"].askdirectory.return_value = str(tmp_path)

    app.extract_all_attachments()
    # No files should be written
    assert not list(tmp_path.glob("*"))


def test_extract_all_attachments_collision_and_empty_name(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )

    # 1. Collision test: two attachments with same name in same message
    text_collision = "begin 644 c.txt\n#0V%T\n`\nend\nbegin 644 c.txt\n#0V%T\n`\nend"
    # 2. Empty name test: use '/' which has empty basename on Unix
    text_empty_name = "begin 644 /\n#0V%T\n`\nend"

    app.messages = [
        ParsedMessage(
            text=text_collision, msgnum=1, refnum=None, confnum=1, header=header
        ),
        ParsedMessage(
            text=text_empty_name, msgnum=2, refnum=None, confnum=1, header=header
        ),
    ]
    setup_tree_mock(app, ["0", "1"])
    mock_gui_deps["filedialog"].askdirectory.return_value = str(tmp_path)

    app.extract_all_attachments()

    assert (tmp_path / "c.txt").exists()
    assert (tmp_path / "c_1.txt").exists()
    assert (tmp_path / "attachment.bin").exists()


def test_extract_all_attachments_exception_handling(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    app.messages = [
        ParsedMessage(
            text="begin 644 t.txt\n#0V%T\n`\nend",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
        )
    ]
    setup_tree_mock(app, ["0"])
    mock_gui_deps["filedialog"].askdirectory.return_value = str(tmp_path)

    original_open = open

    def mock_open(file, mode="r", **kwargs):
        if str(tmp_path) in str(file):
            raise IOError("Batch Failure")
        return original_open(file, mode, **kwargs)

    with patch("builtins.open", side_effect=mock_open):
        app.extract_all_attachments()
        mock_gui_deps["messagebox"].showerror.assert_called_once()
        assert "Batch Failure" in str(mock_gui_deps["messagebox"].showerror.call_args)


def test_extract_all_attachments_invalid_iid_skip(mock_gui_deps, tmp_path):
    root = MagicMock()
    app = QwkGuiApp(root)
    app.messages = [
        ParsedMessage(text="body", msgnum=1, refnum=None, confnum=1, header=MagicMock())
    ]
    setup_tree_mock(app, ["999"])
    mock_gui_deps["filedialog"].askdirectory.return_value = str(tmp_path)

    app.extract_all_attachments()
    mock_gui_deps["messagebox"].showinfo.assert_called_once()
