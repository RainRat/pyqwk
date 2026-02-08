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
         patch("pyqwk.gui.ttk") as mock_ttk:

        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m
        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)

        # Ensure END is available
        mock_tk.END = "end"

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }

def test_search_highlighting(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    # Setup search term
    app.search_var.get.return_value = "highlight"

    # Setup a message
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='All', msgfrom='User', msgsubject='Subject with highlight',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )
    msg = ParsedMessage(text="Body with highlight word", msgnum=1, refnum=None, confnum=1, header=header)
    app.messages = [msg]
    app.board_dict = {1: "General"}

    # Mock the search method of detail_text to return some positions then None
    app.detail_text.search.side_effect = ["1.10", "2.5", None]

    # Render message
    app._render_message(0)

    # Verify tag_add was called for the two matches returned by mock search
    assert app.detail_text.tag_add.call_count == 2
    app.detail_text.tag_add.assert_any_call("search_highlight", "1.10", "1.10+9c")
    app.detail_text.tag_add.assert_any_call("search_highlight", "2.5", "2.5+9c")
    app.detail_text.tag_raise.assert_called_with("search_highlight")

def test_no_search_no_highlighting(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    # Setup empty search term
    app.search_var.get.return_value = ""

    # Setup a message
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
        msgto='All', msgfrom='User', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=1, nettag=''
    )
    msg = ParsedMessage(text="Body text", msgnum=1, refnum=None, confnum=1, header=header)
    app.messages = [msg]
    app.board_dict = {1: "General"}

    # Render message
    app._render_message(0)

    # Verify tag_add was NOT called for search_highlight
    for call_args in app.detail_text.tag_add.call_args_list:
        assert call_args[0][0] != "search_highlight"
