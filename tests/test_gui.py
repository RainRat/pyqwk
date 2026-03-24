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

def get_app(initial_path=None):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root, initial_path=initial_path)

class TestQwkGui:
    def test_initialization(self, mock_gui_deps):
        app = get_app()
        assert app.root is not None
        assert hasattr(app, 'message_list')
        app.root.bind.assert_any_call("<Control-o>", app.open_file)
        app.root.bind.assert_any_call("<Control-s>", app.export_messages)
        app.root.bind.assert_any_call("<Escape>", app.clear_search)

        # Verify toolbar elements
        mock_gui_deps["ttk"].Label.assert_any_call(ANY, text="File:")
        mock_gui_deps["ttk"].Button.assert_any_call(ANY, text="Open", command=app.open_file)
        mock_gui_deps["ttk"].Button.assert_any_call(ANY, text="Export", command=app.export_messages)

    def test_current_settings(self, mock_gui_deps):
        app = get_app()
        app.clean_var.get.return_value = True
        app.private_var.get.return_value = True
        app.search_var.get.return_value = "test search"

        # Test conference filtering in settings
        app.conf_combo.get.return_value = "1: General"
        app.conf_mapping = {"1: General": 1}

        settings = app._current_settings()
        assert isinstance(settings, ProcessingSettings)
        assert settings.private is True
        assert settings.search_term == "test search"
        assert settings.conferences == ["1"]

    def test_load_messages_success(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
             patch("pyqwk.gui.process_message") as mock_process_message, \
             patch.object(app, "on_message_selected"):

            # Test with BBS Info
            mock_board_dict = MagicMock(spec=dict)
            mock_board_dict.get.return_value = "General"
            mock_board_dict.items.return_value = {1: "General"}.items()
            bbs_info = MagicMock()
            bbs_info.name = "Test BBS"
            bbs_info.user_name = "Mock User"
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
            app.message_list.insert.assert_called_with(
                '', 'end', iid='0', text='Subject',
                values=('', 1, 'User', 'All', '01-01-90 12:00', 'General', 'Test BBS'),
                open=True, tags=()
            )

            # Verify status bar contains BBS name
            calls = app.status_label.config.call_args_list
            texts = [c.kwargs['text'] for c in calls if 'text' in c.kwargs]
            assert "Test BBS" in texts[-1]

            # Verify Ref #: was rendered
            app._render_message(0)
            app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Ref #: ", "header_label")

    def test_load_messages_error(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data", side_effect=Exception("Load failed")):
            app.load_messages("bad.qwk")
            mock_gui_deps["messagebox"].showerror.assert_called_with("Failed to load QWK", "Load failed")

    def test_clear_filters(self, mock_gui_deps):
        app = get_app()
        app.conf_combo.set("1: General")
        app.has_attach_var.get.return_value = True
        app.mine_var.get.return_value = True
        with patch.object(app, 'reload_messages') as mock_reload:
            app.clear_filters()
            app.conf_combo.current.assert_called_with(0)
            app.has_attach_var.set.assert_called_with(False)
            app.mine_var.set.assert_called_with(False)
            mock_reload.assert_called_once()
            app.message_list.focus_set.assert_called_once()

    def test_on_message_selected(self, mock_gui_deps):
        app = get_app()
        # Test no selection
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
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Body", ("body",))

    def test_open_file_cancel(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["filedialog"].askopenfilenames.return_value = []
        app.open_file()
        assert app.current_path is None

    def test_open_file_select(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["filedialog"].askopenfilenames.return_value = ["selected.qwk"]
        with patch.object(app, 'load_messages') as mock_load:
            app.open_file()
            assert app.current_path == "selected.qwk"
            mock_load.assert_called_with(["selected.qwk"])

    def test_sort_column(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.side_effect = lambda parent="": ["item1", "item2"] if parent == "" else []
        app.message_list.set.side_effect = lambda k, col: "Value2" if k == "item1" else "Value1"
        app.threaded_var.get.return_value = False
        app.sort_column("From", False)
        app.message_list.move.assert_has_calls([call("item2", "", 0), call("item1", "", 1)])

        # Test sorting by Subject (#0)
        def mock_item(k, attr=None, **kwargs):
            if attr == "text":
                return "Subject B" if k == "item1" else "Subject A"
            if attr == "tags":
                return ()
            return None

        app.message_list.item.side_effect = mock_item
        app.sort_column("#0", False)
        app.message_list.move.assert_any_call("item2", "", 0)

    def test_sort_column_fallback_on_sort(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.side_effect = lambda parent="": ["item1"] if parent == "" else []
        app.message_list.set.return_value = "Value"
        app.threaded_var.get.return_value = False
        # Trigger an exception inside the try block but after l is populated
        with patch("pyqwk.gui._parse_qwk_date", side_effect=Exception("Sort error")):
            app.sort_column("Date", False)
        app.message_list.move.assert_called()

    def test_sort_column_fallback_on_retrieval(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.side_effect = lambda parent="": ["item1"] if parent == "" else []
        # Trigger an exception during list comprehension
        app.message_list.set.side_effect = Exception("Retrieval error")
        app.threaded_var.get.return_value = False
        # Should catch exception and NOT crash (and NOT sort since l is empty)
        app.sort_column("From", False)
        app.message_list.move.assert_not_called()

    def test_sort_column_threaded_enabled(self, mock_gui_deps):
        app = get_app()
        app.message_list.move.reset_mock()
        app.message_list.get_children.side_effect = lambda parent="": ["item1"] if parent == "" else []
        app.message_list.set.return_value = "Value"
        app.threaded_var.get.return_value = True
        app.sort_column("From", False)
        app.message_list.move.assert_called()

    def test_conference_population(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages:
            mock_load_data.return_value = (bytearray(), {1: "General", 2: "Tech"})
            mock_parse_messages.return_value = []
            app.load_messages("test.qwk")
            expected_values = ["All Conferences (0)", "1: General (0)", "2: Tech (0)"]
            mock_gui_deps["combo"].__setitem__.assert_any_call('values', expected_values)
            assert app.conf_mapping == {"1: General (0)": 1, "2: Tech (0)": 2}

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
        app.message_list.get_children.side_effect = lambda parent="": ["item1", "item2"] if parent == "" else []
        dates = {"item1": "12-10-93 12:00", "item2": "01-15-94 09:00"}
        app.message_list.set.side_effect = lambda k, col: dates[k]
        app.threaded_var.get.return_value = False
        app.sort_column("Date", False)
        app.message_list.move.assert_has_calls([call("item1", "", 0), call("item2", "", 1)])

    def test_sort_column_numeric(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.side_effect = lambda parent="": ["item1", "item2"] if parent == "" else []
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
        app.message_list.get_children.side_effect = lambda parent="": ["item1"] if parent == "" else []
        app.message_list.set.return_value = "Val"
        app.threaded_var.get.return_value = False
        app.sort_column("From", False)
        app.message_list.heading.assert_any_call("From", text="From ▲", anchor="w", command=ANY)

        # Verify Num header is right-aligned even when sorted
        app.sort_column("Num", False)
        app.message_list.heading.assert_any_call("Num", text="Num ▲", anchor="e", command=ANY)

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
            # matches_filters is called 3 times per message (BBS count, conf count, filter check)
            # For 2 messages, total 6 calls.
            # We want Msg 1 to show up (3x True) and Msg 2 conf count/filter to fail (or at least filter fail)
            mock_matches_filters.side_effect = [True, True, True, True, False, False]
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
        # Verify that auto-scroll was triggered for the first match
        app.detail_text.see.assert_called_with("1.10")

    def test_render_message_quotes(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        msg = ParsedMessage("Normal line\n> Quoted line\n", 1, None, 1, header)
        app.messages = [msg]
        app.board_dict = {1: "General"}
        app._render_message(0)

        # Verify normal line
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Normal line\n", ("body",))
        # Verify quoted line has both 'body' and 'quote' tags
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "> Quoted line\n", ("body", "quote"))

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
        # Test _on_search_changed
        app._search_timer = "timer1"
        app._on_search_changed()
        app.root.after_cancel.assert_called_with("timer1")
        app.root.after.assert_called_with(250, app.reload_messages)

        # Test _on_search_enter
        with patch.object(app, "reload_messages") as mock_reload:
            app._on_search_enter(None)
            mock_reload.assert_called_once()
            app.message_list.focus_set.assert_called_once()

        # Test reload_messages with timer
        app._search_timer = "timer2"
        with patch.object(app, "load_messages") as mock_load:
            app.current_path = "path"
            app.reload_messages()
            app.root.after_cancel.assert_called_with("timer2")
            assert app._search_timer is None
            mock_load.assert_called_with(["path"])

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
            app.message_list.insert.assert_any_call("", "end", iid="0", text="Sub", values=ANY, open=True, tags=ANY)
            app.message_list.insert.assert_any_call("0", "end", iid="1", text="Sub", values=ANY, open=True, tags=ANY)

    def test_on_message_selected_value_error(self, mock_gui_deps):
        app = get_app()
        app.message_list.selection.return_value = ("not-an-int",)
        app.on_message_selected()
        app.detail_text.delete.assert_not_called()

    def test_jump_to_message_found(self, mock_gui_deps):
        app = get_app()
        header1 = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        header2 = MessageHeader(' ', 2, "01-01-90", "12:05", "To", "From", "Sub", "", 1, 1, " ", 1, 1, "")
        app.messages = [
            ParsedMessage("Msg 1", 1, None, 1, header1),
            ParsedMessage("Msg 2", 2, 1, 1, header2)
        ]
        app.message_list.exists.return_value = True

        with patch.object(app, "on_message_selected"):
            app.jump_to_message(1, 1) # Jump to conf 1, msg 1

        app.message_list.selection_set.assert_called_with("0")
        app.message_list.see.assert_called_with("0")
        app.message_list.focus.assert_called_with("0")

    def test_jump_to_message_not_found(self, mock_gui_deps):
        app = get_app()
        app.messages = []
        app.jump_to_message(1, 999)
        mock_gui_deps["messagebox"].showinfo.assert_called_with(
            "Not Found", "Referenced message #999 was not found in the current view."
        )

    def test_selection_restoration_success(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        msg = ParsedMessage("Body", 1, None, 1, header)
        app.messages = [msg]

        app.message_list.selection.return_value = ("0",)
        app.message_list.exists.return_value = True

        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
             patch("pyqwk.gui.process_message") as mock_process_message, \
             patch.object(app, "on_message_selected"):

            mock_load_data.return_value = (bytearray(), {1: "General"})
            mock_parse_messages.return_value = [msg]
            mock_matches_filters.return_value = True
            mock_process_message.return_value = "Body"

            app.load_messages("test.qwk")

            app.message_list.selection_set.assert_called_with("0")
            app.message_list.focus.assert_called_with("0")

    def test_selection_restoration_fallback(self, mock_gui_deps):
        app = get_app()
        header1 = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub1", "", None, 1, " ", 1, 1, "")
        header2 = MessageHeader(' ', 2, "01-01-90", "12:05", "To", "From", "Sub2", "", None, 1, " ", 1, 1, "")
        msg1 = ParsedMessage("Body1", 1, None, 1, header1)
        msg2 = ParsedMessage("Body2", 2, None, 1, header2)
        app.messages = [msg1]

        app.message_list.selection.return_value = ("0",)
        app.message_list.get_children.return_value = ["0"]

        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
             patch("pyqwk.gui.process_message") as mock_process_message, \
             patch.object(app, "on_message_selected"):

            mock_load_data.return_value = (bytearray(), {1: "General"})
            mock_parse_messages.return_value = [msg2]
            mock_matches_filters.return_value = True
            mock_process_message.return_value = "Body2"

            app.load_messages("test.qwk")

            app.message_list.selection_set.assert_called_with("0")

    def test_selection_capture_invalid_iid_type(self, mock_gui_deps):
        app = get_app()
        app.messages = []
        app.message_list.selection.return_value = ("not-an-int",)
        with patch("pyqwk.gui.load_data", return_value=(bytearray(), {})):
            app.load_messages("test.qwk")

    def test_selection_capture_out_of_range_index(self, mock_gui_deps):
        app = get_app()
        app.messages = []
        app.message_list.selection.return_value = ("99",)
        with patch("pyqwk.gui.load_data", return_value=(bytearray(), {})):
            app.load_messages("test.qwk")

    def test_navigation_shortcuts(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        app.messages = [
            ParsedMessage("Msg 1", 1, None, 1, header),
            ParsedMessage("Msg 2", 2, None, 1, header),
            ParsedMessage("Msg 3", 3, None, 1, header),
        ]
        app.message_list.get_children.side_effect = lambda parent="": ["0", "1", "2"] if parent == "" else []

        # No selection initially -> select first
        app.message_list.selection.return_value = ()
        with patch.object(app, "on_message_selected"):
            app._select_relative_message(1)
            app.message_list.selection_set.assert_called_with("0")

        # Selection at index 0 -> move to index 1
        app.message_list.selection.return_value = ("0",)
        app._select_relative_message(1)
        app.message_list.selection_set.assert_called_with("1")

        # Selection at index 2 -> move to next (stay at 2)
        app.message_list.selection.return_value = ("2",)
        app._select_relative_message(1)
        app.message_list.selection_set.assert_called_with("2")

        # Move back
        app.message_list.selection.return_value = ("1",)
        app._select_relative_message(-1)
        app.message_list.selection_set.assert_called_with("0")

    def test_render_message_stripping(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='All             ', msgfrom='User            ', msgsubject='Subject         ',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        app.messages = [ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)]
        app.board_dict = {1: "General"}

        app._render_message(0)

        # Verify that stripped values were inserted
        # Subject is inserted first
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Subject\n\n", "header_subject")
        # Then From and To via insert_field
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "User\t", "header_value")
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "All\t", "header_value")

    def test_initial_path_loading(self, mock_gui_deps):
        """Test that passing an initial path to the constructor triggers loading."""
        with patch("pyqwk.gui.QwkGuiApp.load_messages"):
            app = get_app(initial_path="initial.qwk")
            assert app.current_path == "initial.qwk"
            # Since we use self.root.after, we need to check that it was scheduled
            app.root.after.assert_called_with(100, ANY)

    def test_title_update(self, mock_gui_deps):
        """Test that the window title is updated when a message is loaded."""
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages:

            mock_board_dict = MagicMock(spec=dict)
            mock_board_dict.get.return_value = "General"
            mock_board_dict.items.return_value = {1: "General"}.items()
            bbs_info = MagicMock()
            bbs_info.name = "Test BBS"
            mock_board_dict.bbs_info = bbs_info

            mock_load_data.return_value = (bytearray(), mock_board_dict)
            mock_parse_messages.return_value = []

            app.load_messages("test.qwk")
            app.root.title.assert_called_with("Test BBS (test.qwk) - PyQWK Reader")

    def test_export_messages_success(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        app.messages = [ParsedMessage("Body", 1, None, 1, header)]

        with patch.object(app, "_get_all_tree_items", return_value=["0"]):
            mock_gui_deps["filedialog"].asksaveasfilename.return_value = "export.json"

            with patch("pyqwk.gui.write_messages") as mock_write, \
                 patch("pyqwk.gui.process_message", return_value="Processed Body") as mock_process:
                app.export_messages()

                mock_process.assert_called_once()
                mock_write.assert_called_once()
                args, _ = mock_write.call_args
                
                # Verify that the exported message has the processed text
                exported_msgs = args[0]
                assert len(exported_msgs) == 1
                assert exported_msgs[0].text == "Processed Body"
                assert args[1] == "export.json"
                assert args[2].format == "json"
                mock_gui_deps["messagebox"].showinfo.assert_called()

    def test_export_messages_text_with_headers(self, mock_gui_deps):
        app = get_app()
        mock_header = MagicMock()
        mock_header.format_text.return_value = "HEADER\n"
        app.messages = [ParsedMessage("Body", 1, None, 1, mock_header)]

        with patch.object(app, "_get_all_tree_items", return_value=["0"]):
            mock_gui_deps["filedialog"].asksaveasfilename.return_value = "export.txt"

            with patch("pyqwk.gui.write_messages") as mock_write, \
                 patch("pyqwk.gui.process_message", return_value="Processed Body") as mock_process:
                app.export_messages()

                mock_process.assert_called_once()
                mock_header.format_text.assert_called_once()
                mock_write.assert_called_once()
                args, _ = mock_write.call_args
                
                exported_msgs = args[0]
                assert len(exported_msgs) == 1
                # Should contain both header and body
                assert exported_msgs[0].text == "HEADER\nProcessed Body"
                assert args[1] == "export.txt"
                assert args[2].format == "text"
                assert args[2].no_header is False

    def test_export_messages_no_messages(self, mock_gui_deps):
        app = get_app()
        app.messages = []
        app.export_messages()
        mock_gui_deps["messagebox"].showwarning.assert_called_with("Export", "No messages to export.")

    def test_export_messages_cancel(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, "")
        app.messages = [ParsedMessage("Body", 1, None, 1, header)]
        mock_gui_deps["filedialog"].asksaveasfilename.return_value = ""

        with patch("pyqwk.gui.write_messages") as mock_write:
            app.export_messages()
            mock_write.assert_not_called()

    def test_conference_discovery(self, mock_gui_deps):
        """Test that conferences found in messages.dat but not in CONTROL.DAT are discovered."""
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages:

            # CONTROL.DAT only knows about conf 1
            mock_load_data.return_value = (bytearray(b"data"), {1: "General"})

            # Message from conference 99 (not in CONTROL.DAT)
            header = MessageHeader(' ', 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 99, 1, "")
            msg = ParsedMessage("Msg in Conf 99", 1, None, 99, header)

            # parse_messages is called twice: once for discovery (headers_only=True) and once for actual loading
            mock_parse_messages.side_effect = [[msg], [msg]]

            app.load_messages("test.qwk")

            # Check if Conf 99 was added to dropdown
            # Values are ["All Conferences (1)", "1: General (0)", "99: Conference 99 (1)"]
            expected_values = ["All Conferences (1)", "1: General (0)", "99: Conference 99 (1)"]
            mock_gui_deps["combo"].__setitem__.assert_any_call('values', expected_values)
            assert app.conf_mapping["99: Conference 99 (1)"] == 99

            # Test exception handling in discovery phase
            # Reset cache to force a new load_data call
            app._cache = {}
            mock_parse_messages.side_effect = [Exception("Discovery error"), [msg]]

            # Should NOT crash and still load messages
            app.load_messages("test.qwk")
            assert len(app.messages) == 1

    def test_search_bar_navigation(self, mock_gui_deps):
        app = get_app()
        with patch.object(app, "_select_relative_message") as mock_select:
            # Simulate <Up> key event in search entry
            up_binding = None
            for call_args in app.search_entry.bind.call_args_list:
                if call_args[0][0] == "<Up>":
                    up_binding = call_args[0][1]
                    break
            assert up_binding is not None
            up_binding(MagicMock())
            mock_select.assert_called_with(-1, force=True)

            # Simulate <Down> key event in search entry
            down_binding = None
            for call_args in app.search_entry.bind.call_args_list:
                if call_args[0][0] == "<Down>":
                    down_binding = call_args[0][1]
                    break
            assert down_binding is not None
            down_binding(MagicMock())
            mock_select.assert_called_with(1, force=True)

    def test_focus_search(self, mock_gui_deps):
        app = get_app()
        app._focus_search()
        app.search_entry.focus_set.assert_called_once()
        app.search_entry.selection_range.assert_called_with(0, mock_gui_deps["tk"].END)
