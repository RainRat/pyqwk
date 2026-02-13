import sys
from unittest.mock import MagicMock, patch
import pytest
import os

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk:

        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m
        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)

        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }

def test_status_bar_counts(mock_gui_deps):
    with patch("pyqwk.gui.load_data") as mock_load_data, \
         patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
         patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
         patch("pyqwk.gui.process_message") as mock_process_message, \
         patch("pyqwk.gui.get_allowed_conferences") as mock_get_allowed_conferences:

        from pyqwk.gui import QwkGuiApp
        root = MagicMock()
        app = QwkGuiApp(root)

        # Setup mocks
        mock_load_data.return_value = (bytearray(), {1: "General"})

        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='All', msgfrom='User', msgsubject='Subject',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        # Create 5 messages
        mock_msgs = [
            ParsedMessage(text="Msg 1", msgnum=1, refnum=None, confnum=1, header=header),
            ParsedMessage(text="Msg 2", msgnum=2, refnum=None, confnum=1, header=header),
            ParsedMessage(text="Msg 3", msgnum=3, refnum=None, confnum=1, header=header),
            ParsedMessage(text="Msg 4", msgnum=4, refnum=None, confnum=1, header=header),
            ParsedMessage(text="Msg 5", msgnum=5, refnum=None, confnum=1, header=header),
        ]
        mock_parse_messages.return_value = iter(mock_msgs)

        # matches_filters returns True for only 2 of them
        mock_matches_filters.side_effect = [True, False, True, False, False]
        mock_process_message.side_effect = lambda text, *args: text
        mock_get_allowed_conferences.return_value = {1}

        # Trigger load_messages
        app.load_messages("test.qwk")

        # Expected status: "Showing 2 of 5 messages from test.qwk"
        # status_label.config is called with text="Loading..." first, then the result
        calls = app.status_label.config.call_args_list
        last_call_text = None
        for call in calls:
            if 'text' in call.kwargs:
                last_call_text = call.kwargs['text']

        assert last_call_text == "Showing 2 of 5 messages from test.qwk"
