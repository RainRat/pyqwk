import sys
from unittest.mock import ANY, MagicMock, patch

import pytest
from pyqwk.core import MessageHeader, ParsedMessage
from pyqwk.gui import QwkGuiApp, tk as gui_tk

try:
    TclErrorBase = gui_tk.TclError
    if not (isinstance(TclErrorBase, type) and issubclass(TclErrorBase, BaseException)):
        TclErrorBase = Exception
except AttributeError:
    TclErrorBase = Exception


class FakeTclError(TclErrorBase):
    pass


@pytest.fixture
def mock_app():
    root = MagicMock()
    root.title.return_value = "pyqwk - Graphical Reader"
    with patch.object(QwkGuiApp, "__init__", return_value=None):
        app = QwkGuiApp(root)
        app.root = root
        app.logger = MagicMock()
        app.messages = []
        app.total_msg_count = 0
        app.source_display_name = ""
        app.board_dict = {}
        app._cache = None
        app.my_name = "User"
        app.progress = MagicMock()
        app.column_labels = {"Subject": "Subject", "From": "From"}
        app.current_paths = ["test.qwk"]
        app.status_label = MagicMock()
        app.search_var = MagicMock()
        app.exclude_var = MagicMock()
        app.regex_var = MagicMock()
        app.clean_var = MagicMock()
        app.threaded_var = MagicMock()
        app.wrap_var = MagicMock()
        app.ansi_var = MagicMock()
        app.redact_pii_var = MagicMock()
        app.embed_attach_var = MagicMock()
        app.organize_by_bbs_var = MagicMock()
        app.organize_by_conf_var = MagicMock()
        app.organize_by_subject_var = MagicMock()
        app.organize_by_year_var = MagicMock()
        app.bbs_combo = MagicMock()
        app.conf_combo = MagicMock()
        app.min_words_var = MagicMock()
        app.max_words_var = MagicMock()
        app.private_var = MagicMock()
        app.has_attach_var = MagicMock()
        app.mine_var = MagicMock()
        app.on_this_day_var = MagicMock()
        app.has_links_var = MagicMock()
        app.has_emails_var = MagicMock()
        app.has_phones_var = MagicMock()
        app.has_ansi_var = MagicMock()
        app.has_msg_links_var = MagicMock()
        app.search_count_label = MagicMock()
        app.detail_text = MagicMock()
        app.search_entry = MagicMock()
        app.exclude_entry = MagicMock()
        app.message_list = MagicMock()
        app.message_list.get_children.return_value = []
        app.message_list.item.return_value = {"tags": []}
        app._apply_zebra_striping = MagicMock()
        app._search_matches = []
        app._current_match_idx = -1
        app._history_stack = []
        app.reload_messages = MagicMock()
        return app


# --- From test_lead_qa_gui_tclerror_coverage.py ---

def test_focus_exclude_tclerror_handler():
    root = MagicMock()
    with patch.object(QwkGuiApp, "__init__", return_value=None):
        app = QwkGuiApp(root)
        app.root = root
        app.detail_text = MagicMock()
        app.exclude_entry = MagicMock()
        app.exclude_var = MagicMock()

        app.detail_text.tag_ranges.side_effect = FakeTclError("Mock TclError")
        root.focus_get.return_value = None

        app._focus_exclude()

        app.detail_text.tag_ranges.assert_called_with("sel")
        app.exclude_entry.focus_set.assert_called_once()


# --- From test_lead_qa_gui_stats_save.py ---

def test_save_report_success(mock_app):
    buttons = []

    def mock_button(parent, **kwargs):
        btn = MagicMock()
        btn.kwargs = kwargs
        buttons.append(btn)
        return btn

    with (
        patch("pyqwk.gui.ttk.Button", side_effect=mock_button),
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.html") as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
        patch("pyqwk.core.show_stats") as mock_show_stats,
    ):
        mock_app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_called_once()
        args, _ = mock_show_stats.call_args
        assert args[0] == ["test.qwk"]
        assert args[1].format == "html"
        assert args[1].output_mode == "file"
        assert args[1].output_path == "report.html"
        mock_info.assert_called_once_with("Report Saved", ANY)


def test_save_report_cancelled(mock_app):
    buttons = []

    def mock_button(parent, **kwargs):
        btn = MagicMock()
        btn.kwargs = kwargs
        buttons.append(btn)
        return btn

    with (
        patch("pyqwk.gui.ttk.Button", side_effect=mock_button),
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="") as mock_ask,
        patch("pyqwk.core.show_stats") as mock_show_stats,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
    ):
        mock_app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_not_called()


def test_save_report_error(mock_app):
    buttons = []

    def mock_button(parent, **kwargs):
        btn = MagicMock()
        btn.kwargs = kwargs
        buttons.append(btn)
        return btn

    with (
        patch("pyqwk.gui.ttk.Button", side_effect=mock_button),
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.json") as mock_ask,
        patch("pyqwk.gui.messagebox.showerror") as mock_error,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
        patch("pyqwk.core.show_stats", side_effect=Exception("Disk full")) as mock_show_stats,
    ):
        mock_app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_called_once()
        mock_error.assert_any_call("Save Report Error", "Disk full")


# --- From test_lead_qa_gui_nav_gaps.py ---

def test_navigate_conference_early_return_on_focus(mock_app):
    values = ["All", "1: General"]
    mock_app.conf_combo.__getitem__.side_effect = lambda k: values if k == "values" else None
    mock_app.conf_combo.current.reset_mock()

    mock_app.root.focus_get.return_value = mock_app.search_entry
    mock_app._navigate_conference(1)
    mock_app.conf_combo.current.assert_not_called()

    mock_app.root.focus_get.return_value = mock_app.exclude_entry
    mock_app._navigate_conference(1)
    mock_app.conf_combo.current.assert_not_called()


def test_navigate_conference_unselected_combobox(mock_app):
    values = ["All", "1: General", "2: Tech"]
    mock_app.conf_combo.__getitem__.side_effect = lambda k: values if k == "values" else None
    mock_app.conf_combo.current.return_value = -1

    mock_app._navigate_conference(1)
    mock_app.conf_combo.current.assert_any_call(0)

    mock_app.conf_combo.current.reset_mock()
    mock_app.conf_combo.current.return_value = -1
    mock_app._navigate_conference(-1)
    mock_app.conf_combo.current.assert_any_call(2)


# --- From test_lead_qa_gui_jump_reset_branches.py ---

def test_prompt_jump_to_message_filters_inactive_not_found(mock_app):
    mock_app.search_var.get.return_value = ""
    mock_app.exclude_var.get.return_value = ""
    mock_app.min_words_var.get.return_value = ""
    mock_app.max_words_var.get.return_value = ""
    mock_app.bbs_combo.get.return_value = "All BBSes (100)"
    mock_app.conf_combo.get.return_value = "All Conferences (100)"
    mock_app.has_attach_var.get.return_value = False
    mock_app.mine_var.get.return_value = False
    mock_app.on_this_day_var.get.return_value = False
    mock_app.has_links_var.get.return_value = False
    mock_app.has_emails_var.get.return_value = False
    mock_app.has_phones_var.get.return_value = False
    mock_app.has_ansi_var.get.return_value = False
    mock_app.has_msg_links_var.get.return_value = False
    mock_app.private_var.get.return_value = True

    h1 = MessageHeader(" ", 101, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, "")
    mock_app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]
    mock_app.message_list.selection.return_value = []
    mock_app.message_list.exists.return_value = True

    assert mock_app._is_any_filter_active() is False

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.askyesno") as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        mock_app.prompt_jump_to_message()

    mock_ask.assert_not_called()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]


def test_prompt_jump_to_message_filters_active_user_declines_reset(mock_app):
    mock_app.search_var.get.return_value = "something"
    assert mock_app._is_any_filter_active() is True

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        mock_app.prompt_jump_to_message()

    mock_ask.assert_called_once()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]


def test_jump_to_message_filters_active_user_declines_reset(mock_app):
    mock_app.search_var.get.return_value = "something"

    with (
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        mock_app.jump_to_message(1, 999)

    mock_ask.assert_called_once()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]


def test_jump_to_message_specific_conf_fallback_fix(mock_app):
    mock_app.search_var.get.return_value = "something"

    with (
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        mock_app.jump_to_message(2, 101)

    mock_ask.assert_called_once()
    mock_info.assert_called_once()


# --- From test_lead_qa_gui_gap_coverage.py ---

def test_show_text_context_menu_no_selection(mock_app):
    mock_app.message_list.selection.return_value = []
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_app._show_text_context_menu(event)


def test_show_text_context_menu_invalid_index(mock_app):
    mock_app.message_list.selection.return_value = ["not_an_int"]
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_app._show_text_context_menu(event)


def test_show_text_context_menu_exception_in_msg_block(mock_app, message_factory):
    mock_app.messages = []
    mock_app.message_list.selection.return_value = ["0"]
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_app._show_text_context_menu(event)

    msg = message_factory(1, 0, "Test")
    mock_app.messages = [msg]
    mock_app.message_list.selection.return_value = ["0"]

    msg.header.msgfrom = "Author"
    msg.header.msgto = "To"
    msg.header.msgsubject = "Subject"
    msg.header.msgnum = 1

    class FailingString(str):
        def __init__(self, val):
            self.count = 0

        def strip(self, *args, **kwargs):
            self.count += 1
            if self.count > 1:
                raise ValueError("Failing inside second try block")
            return super().strip(*args, **kwargs)

    msg.header.msgfrom = FailingString("Author")

    with patch("pyqwk.gui.tk.Menu"):
        mock_app._show_text_context_menu(event)


def test_show_text_context_menu_empty_detail_selection(mock_app):
    mock_app.detail_text.tag_ranges.return_value = ("1.0", "1.1")
    mock_app.detail_text.get.return_value = "   "
    event = MagicMock()
    with patch("pyqwk.gui.tk.Menu"):
        mock_app._show_text_context_menu(event)


def test_search_from_selection_empty(mock_app):
    mock_app.detail_text.tag_ranges.return_value = ()
    mock_app._search_from_selection()
    mock_app.search_var.set.assert_not_called()


def test_search_from_selection_whitespace(mock_app):
    mock_app.detail_text.tag_ranges.return_value = ("1.0", "1.5")
    mock_app.detail_text.get.return_value = "    "
    mock_app._search_from_selection()
    mock_app.search_var.set.assert_not_called()


def test_find_message_index_no_tree_selection(mock_app, message_factory):
    msg = message_factory(1, 0, "Test")
    mock_app.messages = [msg]
    mock_app.message_list.selection.return_value = []

    idx = mock_app._find_message_index(1, None)
    assert idx == 0


def test_block_text_input_control_keys(mock_app):
    event = MagicMock()
    event.state = 0x4
    event.keysym = "c"
    assert mock_app._block_text_input(event) is None

    event.keysym = "a"
    assert mock_app._block_text_input(event) is None

    event.keysym = "v"
    assert mock_app._block_text_input(event) == "break"


def test_on_space_pressed_unhandled_key(mock_app):
    event = MagicMock()
    event.keysym = "Escape"
    mock_app.detail_text.yview.return_value = (0.0, 1.0)
    assert mock_app._on_space_pressed(event) is None


def test_current_settings_missing_mapping(mock_app):
    mock_app.bbs_combo = MagicMock()
    mock_app.bbs_combo.get.return_value = "All BBSes"
    mock_app.conf_combo = MagicMock()
    mock_app.conf_combo.get.return_value = "Not All Conferences"
    mock_app.conf_mapping = {}

    settings = mock_app._current_settings()
    assert settings.conferences is None


def test_navigate_search_matches_invalid_selection(mock_app):
    mock_app._search_matches = [("1.0", "1.5")]
    mock_app._current_match_idx = 0
    mock_app.message_list.selection.return_value = ["invalid"]
    mock_app._navigate_search_matches(1)


def test_sort_column_fallback_subject(mock_app):
    mock_app.message_list.get_children.return_value = ["iid_invalid"]
    mock_app.message_list.item.return_value = "Subject Text"

    mock_app.sort_column("#0", False)
    mock_app.message_list.item.assert_any_call("iid_invalid", "text")


def test_sort_column_fallback_other(mock_app):
    mock_app.message_list.get_children.return_value = ["iid_invalid"]
    mock_app.message_list.set.return_value = "Column Value"

    mock_app.sort_column("From", False)
    mock_app.message_list.set.assert_any_call("iid_invalid", "From")


def test_load_messages_invalid_selection_index(mock_app):
    mock_app.current_paths = ["test.qwk"]
    mock_app.message_list.selection.return_value = ["not_an_int"]
    mock_app._update_history_ui = MagicMock()
    with patch("pyqwk.gui.load_data", return_value=([], {})):
        mock_app.load_messages(["test.qwk"])


def test_pivot_filter_no_matches(mock_app):
    mock_app.bbs_combo.__getitem__.return_value = ["Other BBS"]
    mock_app.conf_combo.__getitem__.return_value = ["999: Other Conf"]

    mock_app._pivot_filter(bbs_name="Missing", conf_num=1)

    mock_app.bbs_combo.current.assert_not_called()
    mock_app.conf_combo.current.assert_not_called()


# --- From test_lead_qa_gui_gap_closure_v2.py ---

def test_is_any_filter_active_gaps(mock_app):
    mock_app.search_var.get.return_value = ""
    mock_app.exclude_var.get.return_value = ""
    mock_app.bbs_combo.get.return_value = "All BBSes"
    mock_app.conf_combo.get.return_value = "All Conferences"
    mock_app.min_words_var.get.return_value = ""
    mock_app.max_words_var.get.return_value = ""
    mock_app.private_var.get.return_value = True
    for var in [
        mock_app.has_attach_var,
        mock_app.mine_var,
        mock_app.on_this_day_var,
        mock_app.has_links_var,
        mock_app.has_emails_var,
        mock_app.has_phones_var,
        mock_app.has_ansi_var,
        mock_app.has_msg_links_var,
    ]:
        var.get.return_value = False

    assert mock_app._is_any_filter_active() is False

    mock_app.conf_combo.get.return_value = "1: General"
    assert mock_app._is_any_filter_active() is True
    mock_app.conf_combo.get.return_value = "All Conferences"

    mock_app.mine_var.get.return_value = True
    assert mock_app._is_any_filter_active() is True
    mock_app.mine_var.get.return_value = False

    mock_app.private_var.get.return_value = False
    assert mock_app._is_any_filter_active() is True
    mock_app.private_var.get.return_value = True

    mock_app.min_words_var.get.return_value = "10"
    assert mock_app._is_any_filter_active() is True
    mock_app.min_words_var.get.return_value = ""
    mock_app.max_words_var.get.return_value = "100"
    assert mock_app._is_any_filter_active() is True


def test_navigate_conference_empty_values(mock_app):
    mock_app.conf_combo.__getitem__.return_value = []
    mock_app._navigate_conference(1)
    mock_app.conf_combo.current.assert_not_called()


def test_navigate_conference_no_selection_wrap(mock_app):
    mock_app.conf_combo.__getitem__.return_value = ["A", "B", "C"]
    mock_app.conf_combo.current.return_value = -1
    mock_app.root.focus_get.return_value = None

    mock_app._navigate_conference(-1)
    mock_app.conf_combo.current.assert_called_with(2)


def test_on_space_pressed_scrolling_gaps(mock_app):
    mock_app.root.focus_get.return_value = None

    mock_app.detail_text.yview.return_value = (0.0, 0.5)
    event = MagicMock()
    event.keysym = "space"
    event.state = 0
    assert mock_app._on_space_pressed(event) == "break"
    mock_app.detail_text.yview_scroll.assert_called_with(1, "pages")

    mock_app.detail_text.yview.return_value = (0.5, 1.0)
    event.keysym = "BackSpace"
    assert mock_app._on_space_pressed(event) == "break"
    mock_app.detail_text.yview_scroll.assert_called_with(-1, "pages")


def test_on_space_pressed_focus_ignored(mock_app):
    mock_app.root.focus_get.return_value = mock_app.search_entry
    event = MagicMock()
    assert mock_app._on_space_pressed(event) is None


def test_block_text_input_brackets(mock_app):
    event = MagicMock()
    event.state = 0

    with patch.object(mock_app, "_navigate_conference") as mock_nav:
        event.keysym = "bracketleft"
        event.char = "["
        assert mock_app._block_text_input(event) == "break"
        mock_nav.assert_called_with(-1)

        event.keysym = "bracketright"
        event.char = "]"
        assert mock_app._block_text_input(event) == "break"
        mock_nav.assert_called_with(1)


def test_pivot_filter_subject_exclude_gaps(mock_app):
    mock_app._pivot_filter(subject="Re: Test Subject")
    mock_app.search_var.set.assert_called_with("test subject")

    mock_app._pivot_filter(exclude_subject="Fwd: Hidden")
    mock_app.exclude_var.set.assert_called_with("hidden")

    mock_app._pivot_filter(exclude_bbs_name="Old BBS")
    mock_app.exclude_var.set.assert_called_with("Old BBS")

    mock_app._pivot_filter(exclude_conf_num=123)
    mock_app.exclude_var.set.assert_called_with("123")


# --- From test_lead_qa_gui_remaining_gaps.py ---

def test_render_empty_state_private_hidden(mock_app):
    mock_app.private_var.get.return_value = False
    mock_app.search_var.get.return_value = ""
    mock_app.exclude_var.get.return_value = ""
    mock_app.bbs_combo.get.return_value = "All BBSes"
    mock_app.conf_combo.get.return_value = "All Conferences"
    mock_app.min_words_var.get.return_value = ""
    mock_app.max_words_var.get.return_value = ""

    for var in [
        mock_app.has_attach_var,
        mock_app.mine_var,
        mock_app.on_this_day_var,
        mock_app.has_links_var,
        mock_app.has_emails_var,
        mock_app.has_phones_var,
        mock_app.has_ansi_var,
        mock_app.has_msg_links_var,
    ]:
        var.get.return_value = False

    with patch.object(mock_app, "_update_status_bar"), patch.object(mock_app, "_render_hr"):
        mock_app._render_empty_state()

    mock_app.detail_text.insert.assert_any_call(ANY, "Private Hidden\n", "body")


def test_render_empty_state_search_only_no_bools(mock_app):
    mock_app.private_var.get.return_value = True
    mock_app.search_var.get.return_value = "query"
    mock_app.exclude_var.get.return_value = ""
    mock_app.bbs_combo.get.return_value = "All BBSes"
    mock_app.conf_combo.get.return_value = "All Conferences"
    mock_app.min_words_var.get.return_value = ""
    mock_app.max_words_var.get.return_value = ""

    for var in [
        mock_app.has_attach_var,
        mock_app.mine_var,
        mock_app.on_this_day_var,
        mock_app.has_links_var,
        mock_app.has_emails_var,
        mock_app.has_phones_var,
        mock_app.has_ansi_var,
        mock_app.has_msg_links_var,
    ]:
        var.get.return_value = False

    with patch.object(mock_app, "_update_status_bar"), patch.object(mock_app, "_render_hr"):
        mock_app._render_empty_state()

    inserted_calls = [c.args[1] for c in mock_app.detail_text.insert.call_args_list if len(c.args) > 1]
    assert any("'query'\n" in text for text in inserted_calls)


def test_reset_bbs_filter_exception(mock_app):
    mock_app.bbs_combo.current.side_effect = Exception("Tcl Error")

    mock_app._reset_bbs_filter()

    mock_app.bbs_combo.set.assert_called_with("All BBSes")
    mock_app.reload_messages.assert_called_once()


def test_reset_conf_filter_exception(mock_app):
    mock_app.conf_combo.current.side_effect = Exception("Tcl Error")

    mock_app._reset_conf_filter()

    mock_app.conf_combo.set.assert_called_with("All Conferences")
    mock_app.reload_messages.assert_called_once()


def test_focus_entry_field_missing_attribute(mock_app):
    mock_app._focus_entry_field("non_existent_entry", "some_var")
    mock_app.detail_text.tag_ranges.assert_not_called()


def test_reset_visibility_filters(mock_app):
    mock_app._reset_visibility_filters()

    mock_app.private_var.set.assert_called_once_with(True)
    mock_app.has_attach_var.set.assert_called_once_with(False)
    mock_app.mine_var.set.assert_called_once_with(False)
    mock_app.on_this_day_var.set.assert_called_once_with(False)
    mock_app.has_links_var.set.assert_called_once_with(False)
    mock_app.has_emails_var.set.assert_called_once_with(False)
    mock_app.has_phones_var.set.assert_called_once_with(False)
    mock_app.has_ansi_var.set.assert_called_once_with(False)
    mock_app.has_msg_links_var.set.assert_called_once_with(False)

    mock_app.reload_messages.assert_called_once()


# --- From test_lead_qa_gui_navigation_final.py ---

def test_navigate_search_matches_cycling(mock_app):
    mock_app._search_matches = [("1.0", "1.5"), ("2.0", "2.5")]
    mock_app._current_match_idx = 0
    mock_app._select_relative_message = MagicMock(return_value=False)
    mock_app._get_all_tree_items = MagicMock(return_value=["0", "1"])

    mock_app._navigate_search_matches(1)
    assert mock_app._current_match_idx == 1
    mock_app.detail_text.tag_add.assert_called_with("current_search_highlight", "2.0", "2.5")
    mock_app.search_count_label.config.assert_called_with(text="2 / 2")

    mock_app._navigate_search_matches(1)
    mock_app.message_list.selection_set.assert_called_with("0")
    assert mock_app._pending_match_idx == 0

    mock_app._current_match_idx = 0
    mock_app.message_list.selection_set.reset_mock()

    mock_app._navigate_search_matches(-1)
    mock_app.message_list.selection_set.assert_called_with("1")
    assert mock_app._pending_match_idx == -1


def test_on_search_changed_debouncing(mock_app):
    mock_app._search_timer = "timer1"

    mock_app._on_search_changed()

    mock_app.root.after_cancel.assert_called_with("timer1")
    mock_app.root.after.assert_called_with(250, mock_app.reload_messages)
    assert mock_app._search_timer == mock_app.root.after.return_value


def test_on_search_enter_with_pending_timer(mock_app):
    mock_app._search_timer = "timer1"

    mock_app._on_search_enter(MagicMock())

    mock_app.root.after_cancel.assert_called_with("timer1")
    assert mock_app._search_timer is None
    mock_app.message_list.focus_set.assert_called_once()


def test_open_folder_success(mock_app):
    def mock_load_impl(paths):
        mock_app.current_paths = paths

    with (
        patch("pyqwk.gui.filedialog.askdirectory", return_value="/path/to/archives"),
        patch("pyqwk.gui.expand_paths", return_value=["/path/to/archives/test.qwk"]),
        patch.object(mock_app, "load_messages", side_effect=mock_load_impl) as mock_load,
    ):
        mock_app.open_folder()

        assert mock_app.current_paths == ["/path/to/archives/test.qwk"]
        mock_load.assert_called_with(["/path/to/archives/test.qwk"])


def test_open_folder_no_archives(mock_app):
    with (
        patch("pyqwk.gui.filedialog.askdirectory", return_value="/path/to/empty"),
        patch("pyqwk.gui.expand_paths", return_value=[]),
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        mock_app.open_folder()

        mock_info.assert_called_once()
