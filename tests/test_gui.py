import sys
import os
from unittest.mock import MagicMock, patch, call, ANY
import pytest
import datetime

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ProcessingSettings, ParsedMessage, MessageHeader

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

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "combo": mock_combo,
        }

def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)

class TestQwkGui:
    def test_initialization(self, mock_gui_deps):
        app = get_app()
        assert app.root is not None
        assert hasattr(app, 'message_list')
        app.root.bind.assert_any_call("<Control-o>", app.open_file)
        app.root.bind.assert_any_call("<Escape>", app.clear_search)

    def test_current_settings(self, mock_gui_deps):
        app = get_app()
        app.clean_var.get.return_value = True
        app.private_var.get.return_value = False
        app.search_var.get.return_value = "test search"

        # Test conference filtering in settings
        app.conf_combo.get.return_value = "1: General"
        app.conf_mapping = {"1: General": 1}

        settings = app._current_settings()
        assert isinstance(settings, ProcessingSettings)
        assert settings.private is False
        assert settings.search_term == "test search"
        assert settings.conferences == ["1"]

    def test_load_messages_success(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
             patch("pyqwk.gui.process_message") as mock_process_message, \
             patch.object(app, "on_message_selected"):

            # Test with BBS Info (covers line 464)
            mock_board_dict = MagicMock(spec=dict)
            mock_board_dict.get.return_value = "General"
            mock_board_dict.items.return_value = {1: "General"}.items()
            bbs_info = MagicMock()
            bbs_info.name = "Test BBS"
            mock_board_dict.bbs_info = bbs_info

            mock_load_data.return_value = (bytearray(), mock_board_dict)
            header = MessageHeader(
                status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
                msgto='All', msgfrom='User', msgsubject='Subject',
                msgpassword='', refnum=99, numblocks=1, msgflag=' ',
                confnum=1, lognum=1, nettag=''
            )
            mock_parse_messages.return_value = [
                ParsedMessage(text="Body", msgnum=1, refnum=99, confnum=1, header=header)
            ]
            mock_matches_filters.return_value = True
            mock_process_message.return_value = "Processed Body"

            app.load_messages("test.qwk")
            assert len(app.messages) == 1
            app.message_list.insert.assert_called()

            # Verify status bar contains BBS name
            calls = app.status_label.config.call_args_list
            texts = [c.kwargs['text'] for c in calls if 'text' in c.kwargs]
            assert "Test BBS" in texts[-1]

            # Verify Ref #: was rendered (covers lines 294-295)
            app._render_message(0)
            app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Ref #: ", "header_label")

    def test_load_messages_error(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data", side_effect=Exception("Load failed")):
            app.load_messages("bad.qwk")
            mock_gui_deps["messagebox"].showerror.assert_called_with("Failed to load QWK", "Load failed")

    def test_clear_conf_filter(self, mock_gui_deps):
        app = get_app()
        app.conf_combo.set("1: General")
        with patch.object(app, 'reload_messages') as mock_reload:
            app.clear_conf_filter()
            app.conf_combo.set.assert_called_with("All Conferences")
            mock_reload.assert_called_once()
            app.message_list.focus_set.assert_called_once()

    def test_on_message_selected(self, mock_gui_deps):
        app = get_app()
        # Test no selection (covers line 493)
        app.message_list.selection.return_value = ()
        app.on_message_selected()
        app.detail_text.delete.assert_not_called()

        # Test valid selection
        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='All', msgfrom='User', msgsubject='Subject',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        app.messages = [ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)]
        app.message_list.selection.return_value = ("0",)
        app.on_message_selected()
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Body", "body")

    def test_open_file_cancel(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["filedialog"].askopenfilename.return_value = ""
        app.open_file()
        assert app.current_path is None

    def test_open_file_select(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["filedialog"].askopenfilename.return_value = "selected.qwk"
        with patch.object(app, 'load_messages') as mock_load:
            app.open_file()
            assert app.current_path == "selected.qwk"
            mock_load.assert_called_with("selected.qwk")

    def test_sort_column(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.return_value = ["item1", "item2"]
        app.message_list.set.side_effect = lambda k, col: "Value2" if k == "item1" else "Value1"
        app.threaded_var.get.return_value = False
        app.sort_column("From", False)
        app.message_list.move.assert_has_calls([call("item2", "", 0), call("item1", "", 1)])

        # Test sorting by Subject (#0) (covers line 464)
        app.message_list.item.side_effect = lambda k, attr: {"text": "Subject B" if k == "item1" else "Subject A"}[attr]
        app.sort_column("#0", False)
        app.message_list.move.assert_any_call("item2", "", 0)

    def test_sort_column_fallback(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.return_value = ["item1"]
        # Trigger an exception inside the try block of sort_column
        # By having set return something that cannot be compared?
        # Or by having a custom exception in the loop.
        app.message_list.set.side_effect = lambda k, col: 123
        app.threaded_var.get.return_value = False
        # If we sort by non-numeric column with mixed types, it might fail?
        # Actually, let's just mock the sort to fail.
        with patch("pyqwk.gui._parse_qwk_date", side_effect=Exception("Sort error")):
            app.sort_column("Date", False)
        app.message_list.move.assert_called()

    def test_sort_column_threaded_disabled(self, mock_gui_deps):
        app = get_app()
        app.message_list.move.reset_mock()
        app.threaded_var.get.return_value = True
        app.sort_column("From", False)
        app.message_list.move.assert_not_called()

    def test_conference_population(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages:
            mock_load_data.return_value = (bytearray(), {1: "General", 2: "Tech"})
            mock_parse_messages.return_value = []
            app.load_messages("test.qwk")
            expected_values = ["All Conferences", "1: General", "2: Tech"]
            mock_gui_deps["combo"].__setitem__.assert_any_call('values', expected_values)
            assert app.conf_mapping == {"1: General": 1, "2: Tech": 2}

    def test_caching_mechanism(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages:
            mock_load_data.return_value = (bytearray(), {1: "General"})
            mock_parse_messages.return_value = []
            app.load_messages("test.qwk")
            assert mock_load_data.call_count == 1
            app.load_messages("test.qwk")
            assert mock_load_data.call_count == 1
            app.load_messages("other.qwk")
            assert mock_load_data.call_count == 2

    def test_sort_column_chronological(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.return_value = ["item1", "item2"]
        dates = {"item1": "12-10-93 12:00", "item2": "01-15-94 09:00"}
        app.message_list.set.side_effect = lambda k, col: dates[k]
        app.threaded_var.get.return_value = False
        app.sort_column("Date", False)
        app.message_list.move.assert_has_calls([call("item1", "", 0), call("item2", "", 1)])

    def test_sort_column_numeric(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.return_value = ["item1", "item2"]
        app.message_list.set.side_effect = lambda k, col: "100" if k == "item1" else "20"
        app.threaded_var.get.return_value = False
        app.sort_column("Num", False)
        app.message_list.move.assert_has_calls([call("item2", "", 0), call("item1", "", 1)])

    def test_search_bindings(self, mock_gui_deps):
        app = get_app()
        calls = app.search_entry.bind.call_args_list
        bound_events = [c[0][0] for c in calls]
        assert "<Return>" in bound_events
        assert "<Escape>" in bound_events

    def test_clear_search(self, mock_gui_deps):
        app = get_app()
        app.search_var.set("something")
        app.clear_search()
        app.search_var.set.assert_called_with("")
        app.message_list.focus_set.assert_called()

    def test_sort_indicators_update(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.return_value = ["item1"]
        app.message_list.set.return_value = "Val"
        app.threaded_var.get.return_value = False
        app.sort_column("From", False)
        app.message_list.heading.assert_any_call("From", text="From ▲", command=ANY)

    def test_status_bar_counts(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
             patch.object(app, "on_message_selected"):
            mock_load_data.return_value = (bytearray(), {1: "General"})
            header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
            mock_msgs = [ParsedMessage("Msg 1", 1, None, 1, header), ParsedMessage("Msg 2", 2, None, 1, header)]
            mock_parse_messages.return_value = mock_msgs
            mock_matches_filters.side_effect = [True, False]
            app.load_messages("test.qwk")
            calls = app.status_label.config.call_args_list
            texts = [c.kwargs['text'] for c in calls if 'text' in c.kwargs]
            assert "Showing 1 of 2 messages from test.qwk" in texts

    def test_search_highlighting(self, mock_gui_deps):
        app = get_app()
        app.search_var.get.return_value = "highlight"
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        msg = ParsedMessage("Body with highlight", 1, None, 1, header)
        app.messages = [msg]
        app.board_dict = {1: "General"}
        app.detail_text.search.side_effect = ["1.10", None]

        # Inject count_var behavior
        mock_iv = MagicMock()
        mock_iv.get.return_value = 9
        mock_gui_deps["tk"].IntVar.side_effect = None
        mock_gui_deps["tk"].IntVar.return_value = mock_iv

        app._render_message(0)
        # Check that tag_add was called with correct start and end positions
        app.detail_text.tag_add.assert_any_call("search_highlight", "1.10", "1.10+9c")

    def test_search_invalid_regex(self, mock_gui_deps):
        app = get_app()
        app.search_var.get.return_value = "[" # Invalid regex
        app.regex_var.get.return_value = True
        app.detail_text.search.side_effect = mock_gui_deps["tk"].TclError("invalid command name")
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        app.messages = [ParsedMessage("Body", 1, None, 1, header)]
        app.board_dict = {1: "General"}
        app._render_message(0)
        app.detail_text.search.assert_called()

    def test_search_zero_width_match(self, mock_gui_deps):
        app = get_app()
        app.search_var.get.return_value = "^"
        app.regex_var.get.return_value = True
        mock_count_var = MagicMock()
        mock_count_var.get.return_value = 0
        mock_gui_deps["tk"].IntVar.side_effect = None
        mock_gui_deps["tk"].IntVar.return_value = mock_count_var
        app.detail_text.search.side_effect = ["1.0", None]
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        app.messages = [ParsedMessage("Body", 1, None, 1, header)]
        app.board_dict = {1: "General"}
        app._render_message(0)
        assert app.detail_text.search.call_count == 2
        app.detail_text.search.assert_called_with("^", "1.0+1c", stopindex="end", nocase=True, regexp=True, count=ANY)

    def test_search_events_and_timers(self, mock_gui_deps):
        app = get_app()
        # Test _on_search_changed (covers lines 354-356)
        app._search_timer = "timer1"
        app._on_search_changed()
        app.root.after_cancel.assert_called_with("timer1")
        app.root.after.assert_called_with(250, app.reload_messages)

        # Test _on_search_enter (covers lines 360-361)
        with patch.object(app, "reload_messages") as mock_reload:
            app._on_search_enter(None)
            mock_reload.assert_called_once()
            app.message_list.focus_set.assert_called_once()

        # Test reload_messages with timer (covers lines 364-369)
        app._search_timer = "timer2"
        with patch.object(app, "load_messages") as mock_load:
            app.current_path = "path"
            app.reload_messages()
            app.root.after_cancel.assert_called_with("timer2")
            assert app._search_timer is None
            mock_load.assert_called_with("path")

    def test_quit_app(self, mock_gui_deps):
        app = get_app()
        app.quit_app()
        app.root.quit.assert_called_once()

    def test_load_messages_threaded(self, mock_gui_deps):
        app = get_app()
        app.threaded_var.get.return_value = True
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui._order_messages_by_thread") as mock_order, \
             patch.object(app, "on_message_selected"):
            mock_load_data.return_value = (bytearray(), {1: "General"})
            header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
            msg1 = ParsedMessage("Root", 1, None, 1, header, depth=0)
            msg2 = ParsedMessage("Child", 2, 1, 1, header, depth=1)
            mock_parse_messages.return_value = [msg1, msg2]
            mock_order.return_value = [msg1, msg2]
            app.load_messages("test.qwk")
            app.message_list.insert.assert_any_call("", "end", iid="0", text="Sub", values=ANY, open=True)
            app.message_list.insert.assert_any_call("0", "end", iid="1", text="Sub", values=ANY, open=True)

    def test_on_message_selected_value_error(self, mock_gui_deps):
        app = get_app()
        app.message_list.selection.return_value = ("not-an-int",)
        app.on_message_selected()
        app.detail_text.delete.assert_not_called()
