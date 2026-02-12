import sys
from unittest.mock import MagicMock, patch, call, ANY
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture(autouse=True)
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

def test_num_column_configuration(mock_gui_deps):
    app = get_app()
    # Check if 'Num' is in columns
    args, kwargs = mock_gui_deps["ttk"].Treeview.call_args
    assert "Num" in kwargs["columns"]

    # Check if heading is set
    app.message_list.heading.assert_any_call("Num", text="Num", anchor=mock_gui_deps["tk"].W, command=ANY)

    # Check if column is configured
    app.message_list.column.assert_any_call("Num", minwidth=50, width=60, anchor=mock_gui_deps["tk"].E)

def test_load_messages_populates_num(mock_gui_deps):
    app = get_app()
    with patch("pyqwk.gui.load_data") as mock_load_data, \
         patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
         patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
         patch("pyqwk.gui.process_message") as mock_process_message:

        mock_load_data.return_value = (bytearray(), {1: "General"})
        header = MessageHeader(
            status=' ', msgnum=123, msgdate='01-01-90', msgtime='12:00',
            msgto='All', msgfrom='User', msgsubject='Subject',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        mock_parse_messages.return_value = [
            ParsedMessage(text="Body", msgnum=123, refnum=None, confnum=1, header=header)
        ]
        mock_matches_filters.return_value = True
        mock_process_message.return_value = "Processed Body"

        app.load_messages("test.qwk")

        # Verify insert was called with the correct values (Num should be the first value)
        found = False
        for call_args in app.message_list.insert.call_args_list:
            args, kwargs = call_args
            values = kwargs.get("values", [])
            if values and values[0] == 123:
                found = True
                break
        assert found, "Insert not called with msgnum 123 in values[0]"

def test_sort_column_numeric(mock_gui_deps):
    app = get_app()
    app.message_list.get_children.return_value = ["item1", "item2"]

    # Mock set returning string numbers
    app.message_list.set.side_effect = lambda k, col: "100" if k == "item1" else "20"
    app.threaded_var.get.return_value = False

    # Sort Ascending
    app.sort_column("Num", False)
    # 20 should come before 100
    app.message_list.move.assert_has_calls([call("item2", "", 0), call("item1", "", 1)])

    # Sort Descending
    app.message_list.move.reset_mock()
    app.sort_column("Num", True)
    # 100 should come before 20
    app.message_list.move.assert_has_calls([call("item1", "", 0), call("item2", "", 1)])
