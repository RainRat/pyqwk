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

# Set up common constants on the mock
mock_tk.END = "end"
mock_tk.INSERT = "insert"
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

# Configure Variable mocks BEFORE importing QwkGuiApp
def make_var(value=None):
    m = MagicMock()
    m.get.return_value = value
    return m

mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

from pyqwk.core import ParsedMessage, MessageHeader, BBSInfo, ConferenceMap
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_gui_deps():
    with patch("pyqwk.gui.tk", mock_tk), \
         patch("pyqwk.gui.ttk", mock_ttk), \
         patch("pyqwk.gui.filedialog") as mock_fd, \
         patch("pyqwk.gui.messagebox") as mock_mb:
        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }

def get_app():
    root = MagicMock()
    # Reset detail_text mock for each app instance
    app = QwkGuiApp(root)
    app.detail_text.tag_configure.reset_mock()
    app.detail_text.insert.reset_mock()
    return app

class TestGuiBadges:
    def test_badge_tag_configuration(self, mock_gui_deps):
        """Verify that the badge tags are configured in _build_layout."""
        app = get_app()
        # Tags are configured in _build_layout which is called during __init__
        # Since tags are added, we might need to re-instantiate or check mock calls
        # Actually QwkGuiApp calls _build_layout in __init__

        # Manually trigger it to ensure we capture the calls if __init__ was too early
        app._build_layout()

        app.detail_text.tag_configure.assert_any_call(
            "badge_private", background="#ffcccc", foreground="#990000",
            font=("TkDefaultFont", 8, "bold")
        )
        app.detail_text.tag_configure.assert_any_call(
            "badge_mine", background="#cce5ff", foreground="#004085",
            font=("TkDefaultFont", 8, "bold")
        )

    def test_render_message_with_badges(self, mock_gui_deps):
        """Verify that badges are inserted into the detail view when applicable."""
        app = get_app()

        # Mock a private message from the current user
        header = MessageHeader(
            status='*', # Private
            msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='Someone', msgfrom='JULES', msgsubject='Secret',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        msg = ParsedMessage("Hello world", 1, None, 1, header)
        app.messages = [msg]

        # Set up board_dict with BBS info containing the user's name
        board_dict = ConferenceMap({1: "General"})
        board_dict.bbs_info = BBSInfo(user_name="Jules")
        app.board_dict = board_dict

        app._render_message(0)

        # Verify PRIVATE badge insertion
        app.detail_text.insert.assert_any_call(mock_tk.END, " PRIVATE ", "badge_private")

        # Verify MINE badge insertion
        app.detail_text.insert.assert_any_call(mock_tk.END, " MINE ", "badge_mine")

    def test_render_message_without_badges(self, mock_gui_deps):
        """Verify that badges are NOT inserted for normal messages."""
        app = get_app()

        # Normal message from someone else
        header = MessageHeader(
            status=' ', # Not private
            msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='All', msgfrom='Bob', msgsubject='Topic',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        msg = ParsedMessage("Body", 1, None, 1, header)
        app.messages = [msg]

        board_dict = ConferenceMap({1: "General"})
        board_dict.bbs_info = BBSInfo(user_name="Jules")
        app.board_dict = board_dict

        app._render_message(0)

        # Verify badge tags were NOT used in insert calls
        for args, kwargs in app.detail_text.insert.call_args_list:
            if len(args) >= 3:
                assert args[2] != "badge_private"
                assert args[2] != "badge_mine"
            elif "tags" in kwargs:
                assert kwargs["tags"] != "badge_private"
                assert kwargs["tags"] != "badge_mine"
