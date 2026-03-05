import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.filedialog") as mock_fd, \
         patch("pyqwk.gui.messagebox") as mock_mb:

        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)
        mock_tk.NORMAL = "normal"
        mock_tk.DISABLED = "disabled"
        mock_tk.END = "end"

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }

def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)

def test_export_messages_no_messages(mock_gui_deps):
    app = get_app()
    app.messages = []
    app.export_messages()
    mock_gui_deps["messagebox"].showwarning.assert_called_with("Export", "No messages to export.")

def test_export_messages_error_handling(mock_gui_deps):
    app = get_app()

    header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("Body", 1, None, 1, header)
    app.messages = [msg]
    app.board_dict = {1: "General"}

    # Avoid recursion in _get_all_tree_items
    app.message_list.get_children.return_value = []
    with patch.object(app, "_get_all_tree_items", return_value=["0"]):
        mock_gui_deps["filedialog"].asksaveasfilename.return_value = "export.txt"

        with patch("pyqwk.gui.write_messages", side_effect=Exception("Export failed")):
            app.export_messages()
            mock_gui_deps["messagebox"].showerror.assert_called_with("Export Failed", "Export failed")

def test_export_messages_skips_invalid_iid(mock_gui_deps):
    app = get_app()
    header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("Body", 1, None, 1, header)
    app.messages = [msg]
    app.board_dict = {1: "General"}

    # Mocking _get_all_tree_items to return an invalid iid (line 761)
    with patch.object(app, "_get_all_tree_items", return_value=["invalid"]):
        mock_gui_deps["filedialog"].asksaveasfilename.return_value = "export.txt"
        with patch("pyqwk.gui.write_messages") as mock_write:
            app.export_messages()
            # Verify that write_messages was called with an empty list
            mock_write.assert_called_once()
            args, _ = mock_write.call_args
            assert args[0] == []
