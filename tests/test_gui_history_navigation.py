import sys
from unittest.mock import MagicMock, patch, ANY
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
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):
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
        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        # Mock Progressbar
        mock_progress = MagicMock()
        mock_ttk.Progressbar.return_value = mock_progress

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "combo": mock_combo,
        }

def get_app(initial_paths=None):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root, initial_paths=initial_paths)

def test_history_initialization(mock_gui_deps):
    app = get_app()
    assert hasattr(app, "_history_stack")
    assert app._history_stack == []
    app.root.bind.assert_any_call("<Alt-Left>", app.go_back)
    mock_gui_deps["ttk"].Button.assert_any_call(
        ANY, text="Back", width=8, command=app.go_back, state="disabled"
    )

def test_push_current_to_history_no_selection(mock_gui_deps):
    app = get_app()
    app.message_list.selection.return_value = []
    app._push_current_to_history()
    assert app._history_stack == []

def test_push_current_to_history_with_selection(mock_gui_deps):
    app = get_app()
    app.message_list.selection.return_value = ["0"]

    header = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg = ParsedMessage(
        text="Hello",
        msgnum=101,
        refnum=None,
        confnum=1,
        header=header
    )
    app.messages = [msg]
    app._push_current_to_history()

    assert app._history_stack == [(1, 101)]
    app.back_btn.config.assert_any_call(state="normal")

def test_go_back_empty_history(mock_gui_deps):
    app = get_app()
    assert app._history_stack == []
    app.go_back()
    # verify no select was called
    assert not app.message_list.selection_set.called

def test_go_back_with_history_found(mock_gui_deps):
    app = get_app()
    app._history_stack = [(1, 101)]

    header = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg = ParsedMessage(
        text="Hello",
        msgnum=101,
        refnum=None,
        confnum=1,
        header=header
    )
    app.messages = [msg]

    # Mock find message index to return 0
    with patch.object(app, "_find_message_index", return_value=0) as mock_find:
        with patch.object(app, "_select_by_index") as mock_select:
            app.go_back()
            mock_find.assert_called_once_with(101, 1)
            mock_select.assert_called_once_with(0)
            assert app._history_stack == []
            app.back_btn.config.assert_any_call(state="disabled")

def test_go_back_with_history_not_found(mock_gui_deps):
    app = get_app()
    app._history_stack = [(1, 101)]

    with patch.object(app, "_find_message_index", return_value=None):
        with patch.object(app, "_is_any_filter_active", return_value=False):
            app.go_back()
            # messagebox.showinfo should be called
            mock_gui_deps["messagebox"].showinfo.assert_called_once()
            assert app._history_stack == []
            app.back_btn.config.assert_any_call(state="disabled")

def test_go_back_with_history_not_found_active_filters_reset(mock_gui_deps):
    app = get_app()
    app._history_stack = [(1, 101)]

    with patch.object(app, "_find_message_index", side_effect=[None, 0]) as mock_find:
        with patch.object(app, "_is_any_filter_active", return_value=True):
            mock_gui_deps["messagebox"].askyesno.return_value = True
            with patch.object(app, "clear_filters") as mock_clear:
                with patch.object(app, "_select_by_index") as mock_select:
                    app.go_back()
                    mock_clear.assert_called_once()
                    mock_select.assert_called_once_with(0)
                    assert app._history_stack == []
                    app.back_btn.config.assert_any_call(state="disabled")

def test_jump_to_message_pushes_history(mock_gui_deps):
    app = get_app()

    # Mock selection to push history
    app.message_list.selection.return_value = ["0"]
    header = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg = ParsedMessage(
        text="Hello",
        msgnum=101,
        refnum=None,
        confnum=1,
        header=header
    )
    app.messages = [msg]

    with patch.object(app, "_find_message_index", return_value=0):
        with patch.object(app, "_select_by_index") as mock_select:
            app.jump_to_message(1, 202)
            assert app._history_stack == [(1, 101)]
            mock_select.assert_called_once_with(0)

def test_load_messages_clears_history(mock_gui_deps):
    app = get_app()
    app._history_stack = [(1, 101)]

    # Let's mock load_data to return empty elements
    with patch("pyqwk.gui.load_data", return_value=([], {})):
        app.load_messages("dummy.qwk")
        assert app._history_stack == []
        app.back_btn.config.assert_any_call(state="disabled")
