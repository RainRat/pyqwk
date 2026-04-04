import sys
from unittest.mock import MagicMock, patch, ANY
import pytest
import tkinter as tk

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ParsedMessage, MessageHeader, BBSInfo, ConferenceMap

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

        # Tkinter constants
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
        mock_tk.INSERT = "insert"

        # Mock classes/types
        class TclError(Exception):
            pass
        mock_tk.TclError = TclError

        # Mock Combobox
        # We need distinct mock objects for bbs_combo and conf_combo
        bbs_combo = MagicMock()
        conf_combo = MagicMock()

        # side_effect to return different mocks on successive calls
        mock_ttk.Combobox.side_effect = [bbs_combo, conf_combo]

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "bbs_combo": bbs_combo,
            "conf_combo": conf_combo,
        }

def get_app(initial_paths=None):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root, initial_paths=initial_paths)

def test_bbs_filter_population(mock_gui_deps):
    app = get_app()

    # Mock archives from two different BBSes
    header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")

    bbs1_info = BBSInfo(name="BBS One", bbs_id="BBS1")
    bbs2_info = BBSInfo(name="BBS Two", bbs_id="BBS2")

    msg1 = ParsedMessage("Msg 1", 1, None, 1, header)
    msg2 = ParsedMessage("Msg 2", 2, None, 1, header)

    with patch("pyqwk.gui.load_data") as mock_load_data, \
         patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
         patch("pyqwk.gui.matches_filters", return_value=True):

        board_dict1 = ConferenceMap({1: "General"})
        board_dict1.bbs_info = bbs1_info

        board_dict2 = ConferenceMap({1: "General"})
        board_dict2.bbs_info = bbs2_info

        mock_load_data.side_effect = [
            (bytearray(), board_dict1),
            (bytearray(), board_dict2)
        ]

        mock_parse_messages.side_effect = [
            [msg1], # Discovery phase (though it's not strictly necessary for this test, current implementation calls it)
            [msg1], # Loading phase
            [msg2], # Discovery phase
            [msg2]  # Loading phase
        ]

        app.load_messages(["file1.qwk", "file2.qwk"])

        # Check if bbs_combo was populated
        # Values should be ["All BBSes (2)", "BBS One (1)", "BBS Two (1)"]
        # In our case it was the first Combobox created
        expected_values = ["All BBSes (2)", "BBS One (1)", "BBS Two (1)"]
        app.bbs_combo.__setitem__.assert_any_call('values', expected_values)
        assert app.bbs_mapping["BBS One (1)"] == "BBS1"
        assert app.bbs_mapping["BBS Two (1)"] == "BBS2"

def test_bbs_filter_selection(mock_gui_deps):
    app = get_app()

    # Setup mock data and state
    app.bbs_mapping = {"BBS One (1)": "BBS1"}
    app.bbs_combo.get.return_value = "BBS One (1)"

    settings = app._current_settings()
    assert settings.bbs_names == ["BBS1"]

def test_pivot_filter_bbs(mock_gui_deps):
    app = get_app()
    # Resetting mocks since get_app creates them via side_effect
    app.bbs_combo = MagicMock()
    app.bbs_combo.__getitem__.return_value = ["All BBSes (2)", "BBS One (1)", "BBS Two (1)"]

    with patch.object(app, "reload_messages"):
        app._pivot_filter(bbs_name="BBS Two")
        app.bbs_combo.current.assert_called_with(2)
        app.reload_messages.assert_called_once()
