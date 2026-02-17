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

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk:

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
        }

def test_sort_indicators_update(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Mock message_list behavior
    app.message_list.get_children.return_value = ["item1", "item2"]
    app.message_list.set.side_effect = lambda k, col: "Value2" if k == "item1" else "Value1"
    app.threaded_var.get.return_value = False

    # 1. Initial sort by "From" (ascending)
    app.sort_column("From", False)

    # Check that "From" header has ascending arrow
    app.message_list.heading.assert_any_call("From", text="From ▲", command=ANY)
    # Check that other headers have no arrow
    app.message_list.heading.assert_any_call("Num", text="Num", command=ANY)

    # 2. Sort same column "From" (descending)
    app.message_list.heading.reset_mock()
    app.sort_column("From", True)
    app.message_list.heading.assert_any_call("From", text="From ▼", command=ANY)

    # 3. Sort different column "Num" (ascending)
    app.message_list.heading.reset_mock()
    app.sort_column("Num", False)
    app.message_list.heading.assert_any_call("Num", text="Num ▲", command=ANY)
    app.message_list.heading.assert_any_call("From", text="From", command=ANY)

def test_load_messages_resets_indicators(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    with patch("pyqwk.gui.load_data") as mock_load_data, \
         patch("pyqwk.gui.parse_messages") as mock_parse_messages:

        mock_load_data.return_value = (bytearray(b"Produced "), {})
        mock_parse_messages.return_value = []

        # Manually set an indicator
        app.message_list.heading("From", text="From ▲")

        app.load_messages("test.qwk")

        # Check that headers were reset
        app.message_list.heading.assert_any_call("From", text="From", command=ANY)
