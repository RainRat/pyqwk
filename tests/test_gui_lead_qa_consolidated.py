import os
import tkinter as tk
from unittest.mock import MagicMock, patch, ANY
import pytest

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader


@pytest.fixture
def mock_app():
    mock_root = MagicMock()
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.font"),
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.simpledialog"),
    ):
        mock_tk.StringVar.side_effect = lambda *a, **kw: MagicMock()
        mock_tk.BooleanVar.side_effect = lambda *a, **kw: MagicMock()
        mock_tk.IntVar.side_effect = lambda *a, **kw: MagicMock()
        mock_tk.END = "end"

        mock_tree = MagicMock()
        mock_ttk.Treeview.return_value = mock_tree
        mock_tree.get_children.return_value = []
        mock_tree.item.return_value = {"tags": []}

        app = QwkGuiApp(mock_root)
        app.messages = []
        app.message_list = mock_tree
        app.detail_text = MagicMock()
        app.search_entry = MagicMock()
        app.search_var = MagicMock()
        app.search_count_label = MagicMock()
        app.root = mock_root
        app.bbs_combo = MagicMock()
        app.conf_combo = MagicMock()

        app.reload_messages = MagicMock()
        app._update_status_bar = MagicMock()
        app._render_message = MagicMock()
        app._select_by_index = MagicMock()
        app._apply_zebra_striping = MagicMock()

        yield app


@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.font"),
    ):
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "combo": mock_combo,
        }


@pytest.fixture
def gui_app():
    root = MagicMock()
    root.title.return_value = "pyqwk - Graphical Reader"
    root.after = MagicMock()
    with (
        patch("pyqwk.gui.tk") as m_tk,
        patch("pyqwk.gui.ttk") as m_ttk,
        patch("pyqwk.gui.simpledialog"),
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.filedialog"),
    ):
        m_tk.BooleanVar.side_effect = lambda *a, **kw: MagicMock()
        m_tk.StringVar.side_effect = lambda *a, **kw: MagicMock()
        m_tk.IntVar.side_effect = lambda *a, **kw: MagicMock()
        m_tk.END = "end"

        m_ttk.Label.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Button.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Checkbutton.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Entry.side_effect = lambda *a, **kw: MagicMock()
        m_ttk.Combobox.side_effect = lambda *a, **kw: MagicMock()

        app = QwkGuiApp(root)
        app.current_paths = ["test.qwk"]

        app.search_var.get.return_value = ""
        app.exclude_var.get.return_value = ""
        app.min_words_var.get.return_value = ""
        app.max_words_var.get.return_value = ""
        app.clean_var.get.return_value = False

        app.bbs_combo.get.return_value = "All BBSes"
        app.conf_combo.get.return_value = "All Conferences"
        app.bbs_combo.get.side_effect = None

        app.has_attach_var.get.return_value = False
        app.mine_var.get.return_value = False
        app.on_this_day_var.get.return_value = False
        app.has_links_var.get.return_value = False
        app.has_emails_var.get.return_value = False
        app.has_phones_var.get.return_value = False
        app.has_ansi_var.get.return_value = False
        app.has_msg_links_var.get.return_value = False
        app.private_var.get.return_value = True

        h1 = MessageHeader(" ", 101, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, "")
        app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]

        app.message_list.selection.return_value = []
        app.message_list.exists.return_value = True

        yield app


# --- Tests from test_lead_qa_gui_gap_closure_v2.py ---

def test_is_any_filter_active_gaps(mock_app):
    app = mock_app
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"
    app.min_words_var.get.return_value = ""
    app.max_words_var.get.return_value = ""
    app.private_var.get.return_value = True
    for var in [app.has_attach_var, app.mine_var, app.on_this_day_var, app.has_links_var,
                app.has_emails_var, app.has_phones_var, app.has_ansi_var, app.has_msg_links_var]:
        var.get.return_value = False

    assert app._is_any_filter_active() is False

    app.conf_combo.get.return_value = "1: General"
    assert app._is_any_filter_active() is True
    app.conf_combo.get.return_value = "All Conferences"

    app.mine_var.get.return_value = True
    assert app._is_any_filter_active() is True
    app.mine_var.get.return_value = False

    app.private_var.get.return_value = False
    assert app._is_any_filter_active() is True
    app.private_var.get.return_value = True

    app.min_words_var.get.return_value = "10"
    assert app._is_any_filter_active() is True
    app.min_words_var.get.return_value = ""
    app.max_words_var.get.return_value = "100"
    assert app._is_any_filter_active() is True


def test_navigate_conference_empty_values(mock_app):
    app = mock_app
    app.conf_combo.__getitem__.return_value = []
    app._navigate_conference(1)
    app.conf_combo.current.assert_not_called()


def test_navigate_conference_no_selection_wrap(mock_app):
    app = mock_app
    app.conf_combo.__getitem__.return_value = ["A", "B", "C"]
    app.conf_combo.current.return_value = -1
    app.root.focus_get.return_value = None

    with patch.object(app, "reload_messages"):
        app._navigate_conference(-1)
        app.conf_combo.current.assert_called_with(2)


def test_on_space_pressed_scrolling_gaps(mock_app):
    app = mock_app
    app.root.focus_get.return_value = None

    app.detail_text.yview.return_value = (0.0, 0.5)
    event = MagicMock()
    event.keysym = "space"
    event.state = 0
    assert app._on_space_pressed(event) == "break"
    app.detail_text.yview_scroll.assert_called_with(1, "pages")

    app.detail_text.yview.return_value = (0.5, 1.0)
    event.keysym = "BackSpace"
    assert app._on_space_pressed(event) == "break"
    app.detail_text.yview_scroll.assert_called_with(-1, "pages")


def test_on_space_pressed_focus_ignored(mock_app):
    app = mock_app
    app.root.focus_get.return_value = app.search_entry
    event = MagicMock()
    assert app._on_space_pressed(event) is None


def test_block_text_input_brackets(mock_app):
    app = mock_app
    event = MagicMock()
    event.state = 0

    with patch.object(app, "_navigate_conference") as mock_nav:
        event.keysym = "bracketleft"
        event.char = "["
        assert app._block_text_input(event) == "break"
        mock_nav.assert_called_with(-1)

        event.keysym = "bracketright"
        event.char = "]"
        assert app._block_text_input(event) == "break"
        mock_nav.assert_called_with(1)


def test_pivot_filter_subject_exclude_gaps(mock_app):
    app = mock_app
    with patch.object(app, "reload_messages"):
        app._pivot_filter(subject="Re: Test Subject")
        app.search_var.set.assert_called_with("test subject")

        app._pivot_filter(exclude_subject="Fwd: Hidden")
        app.exclude_var.set.assert_called_with("hidden")

        app._pivot_filter(exclude_bbs_name="Old BBS")
        app.exclude_var.set.assert_called_with("Old BBS")

        app._pivot_filter(exclude_conf_num=123)
        app.exclude_var.set.assert_called_with("123")


# --- Tests from test_lead_qa_gui_gap_coverage.py ---

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
    with patch("pyqwk.gui.load_data", return_value=([], {})):
        mock_app.load_messages(["test.qwk"])


def test_pivot_filter_no_matches(mock_app):
    mock_app.bbs_combo.__getitem__.return_value = ["Other BBS"]
    mock_app.conf_combo.__getitem__.return_value = ["999: Other Conf"]

    mock_app._pivot_filter(bbs_name="Missing", conf_num=1)

    mock_app.bbs_combo.current.assert_not_called()
    mock_app.conf_combo.current.assert_not_called()


# --- Tests from test_lead_qa_gui_jump_reset_branches.py ---

def test_prompt_jump_to_message_filters_inactive_not_found(gui_app):
    assert gui_app._is_any_filter_active() is False

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.askyesno") as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        gui_app.prompt_jump_to_message()

    mock_ask.assert_not_called()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]


def test_prompt_jump_to_message_filters_active_user_declines_reset(gui_app):
    gui_app.search_var.get.return_value = "something"
    assert gui_app._is_any_filter_active() is True

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        gui_app.prompt_jump_to_message()

    mock_ask.assert_called_once()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]


def test_jump_to_message_filters_active_user_declines_reset(gui_app):
    gui_app.search_var.get.return_value = "something"

    with (
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        gui_app.jump_to_message(1, 999)

    mock_ask.assert_called_once()
    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]


def test_jump_to_message_specific_conf_fallback_fix(gui_app):
    gui_app.search_var.get.return_value = "something"

    with (
        patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info
    ):
        gui_app.jump_to_message(2, 101)

    mock_ask.assert_called_once()
    mock_info.assert_called_once()


# --- Tests from test_lead_qa_gui_nav_gaps.py ---

def test_navigate_conference_early_return_on_focus(mock_gui_deps, gui_app):
    app = gui_app
    app.search_entry = MagicMock()
    app.exclude_entry = MagicMock()
    values = ["All", "1: General"]
    app.conf_combo.__getitem__.side_effect = lambda k: values if k == "values" else None
    app.conf_combo.current.reset_mock()

    app.root.focus_get.return_value = app.search_entry
    app._navigate_conference(1)
    app.conf_combo.current.assert_not_called()

    app.root.focus_get.return_value = app.exclude_entry
    app._navigate_conference(1)
    app.conf_combo.current.assert_not_called()


def test_navigate_conference_unselected_combobox(mock_gui_deps, gui_app):
    app = gui_app
    values = ["All", "1: General", "2: Tech"]
    app.conf_combo.__getitem__.side_effect = lambda k: values if k == "values" else None
    app.conf_combo.current.return_value = -1

    with patch.object(app, "reload_messages"):
        app._navigate_conference(1)
        app.conf_combo.current.assert_any_call(0)

        app.conf_combo.current.reset_mock()
        app.conf_combo.current.return_value = -1
        app._navigate_conference(-1)
        app.conf_combo.current.assert_any_call(2)


# --- Tests from test_lead_qa_gui_navigation_final.py ---

def test_navigate_search_matches_cycling(gui_app):
    gui_app._search_matches = [("1.0", "1.5"), ("2.0", "2.5")]
    gui_app._current_match_idx = 0
    gui_app._select_relative_message = MagicMock(return_value=False)
    gui_app._get_all_tree_items = MagicMock(return_value=["0", "1"])

    gui_app._navigate_search_matches(1)
    assert gui_app._current_match_idx == 1
    gui_app.detail_text.tag_add.assert_called_with("current_search_highlight", "2.0", "2.5")
    gui_app.search_count_label.config.assert_called_with(text="2 / 2")

    gui_app._navigate_search_matches(1)
    gui_app.message_list.selection_set.assert_called_with("0")
    assert gui_app._pending_match_idx == 0

    gui_app._current_match_idx = 0
    gui_app.message_list.selection_set.reset_mock()

    gui_app._navigate_search_matches(-1)
    gui_app.message_list.selection_set.assert_called_with("1")
    assert gui_app._pending_match_idx == -1


def test_on_search_changed_debouncing(gui_app):
    gui_app._search_timer = "timer1"

    gui_app._on_search_changed()

    gui_app.root.after_cancel.assert_called_with("timer1")
    gui_app.root.after.assert_called_with(250, gui_app.reload_messages)
    assert gui_app._search_timer == gui_app.root.after.return_value


def test_on_search_enter_with_pending_timer(gui_app):
    gui_app._search_timer = "timer1"

    gui_app._on_search_enter(MagicMock())

    gui_app.root.after_cancel.assert_called_with("timer1")
    assert gui_app._search_timer is None
    gui_app.message_list.focus_set.assert_called_once()


def test_open_folder_success(gui_app):
    def mock_load_impl(paths):
        gui_app.current_paths = paths

    with (
        patch("pyqwk.gui.filedialog.askdirectory", return_value="/path/to/archives"),
        patch("pyqwk.gui.expand_paths", return_value=["/path/to/archives/test.qwk"]),
        patch.object(gui_app, "load_messages", side_effect=mock_load_impl) as mock_load,
    ):
        gui_app.open_folder()

        assert gui_app.current_paths == ["/path/to/archives/test.qwk"]
        mock_load.assert_called_with(["/path/to/archives/test.qwk"])


def test_open_folder_no_archives(gui_app):
    with (
        patch("pyqwk.gui.filedialog.askdirectory", return_value="/path/to/empty"),
        patch("pyqwk.gui.expand_paths", return_value=[]),
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        gui_app.open_folder()

        mock_info.assert_called_once()


# --- Tests from test_lead_qa_gui_remaining_gaps.py ---

def test_render_empty_state_private_hidden(mock_app):
    app = mock_app
    app.private_var.get.return_value = False
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"
    app.min_words_var.get.return_value = ""
    app.max_words_var.get.return_value = ""

    for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                app.has_links_var, app.has_emails_var, app.has_phones_var,
                app.has_ansi_var, app.has_msg_links_var]:
        var.get.return_value = False

    with patch.object(app, "_update_status_bar"), patch.object(app, "_render_hr"):
        app._render_empty_state()

    app.detail_text.insert.assert_any_call(ANY, "Private Hidden\n", "body")


def test_render_empty_state_search_only_no_bools(mock_app):
    app = mock_app
    app.private_var.get.return_value = True
    app.search_var.get.return_value = "query"
    app.exclude_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"
    app.min_words_var.get.return_value = ""
    app.max_words_var.get.return_value = ""

    for var in [
        app.has_attach_var,
        app.mine_var,
        app.on_this_day_var,
        app.has_links_var,
        app.has_emails_var,
        app.has_phones_var,
        app.has_ansi_var,
        app.has_msg_links_var,
    ]:
        var.get.return_value = False

    with patch.object(app, "_update_status_bar"), patch.object(app, "_render_hr"):
        app._render_empty_state()

    inserted_calls = [c.args[1] for c in app.detail_text.insert.call_args_list if len(c.args) > 1]
    assert any("'query'\n" in text for text in inserted_calls)


def test_reset_bbs_filter_exception(mock_app):
    app = mock_app
    app.bbs_combo.current.side_effect = Exception("Tcl Error")

    app._reset_bbs_filter()

    app.bbs_combo.set.assert_called_with("All BBSes")
    app.reload_messages.assert_called_once()


def test_reset_conf_filter_exception(mock_app):
    app = mock_app
    app.conf_combo.current.side_effect = Exception("Tcl Error")

    app._reset_conf_filter()

    app.conf_combo.set.assert_called_with("All Conferences")
    app.reload_messages.assert_called_once()


def test_focus_entry_field_missing_attribute(mock_app):
    app = mock_app
    app._focus_entry_field("non_existent_entry", "some_var")
    app.detail_text.tag_ranges.assert_not_called()


def test_reset_visibility_filters(mock_app):
    app = mock_app

    app.private_var = MagicMock()
    app.has_attach_var = MagicMock()
    app.mine_var = MagicMock()
    app.on_this_day_var = MagicMock()
    app.has_links_var = MagicMock()
    app.has_emails_var = MagicMock()
    app.has_phones_var = MagicMock()
    app.has_ansi_var = MagicMock()
    app.has_msg_links_var = MagicMock()

    app._reset_visibility_filters()

    app.private_var.set.assert_called_once_with(True)
    app.has_attach_var.set.assert_called_once_with(False)
    app.mine_var.set.assert_called_once_with(False)
    app.on_this_day_var.set.assert_called_once_with(False)
    app.has_links_var.set.assert_called_once_with(False)
    app.has_emails_var.set.assert_called_once_with(False)
    app.has_phones_var.set.assert_called_once_with(False)
    app.has_ansi_var.set.assert_called_once_with(False)
    app.has_msg_links_var.set.assert_called_once_with(False)

    app.reload_messages.assert_called_once()


# --- Tests from test_lead_qa_gui_stats_save.py ---

def test_save_report_success(gui_app):
    gui_app.current_paths = ["test.qwk"]
    gui_app.logger = MagicMock()

    with (
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.html") as mock_ask,
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
        patch("pyqwk.core.show_stats") as mock_show_stats
    ):
        buttons = []

        def mock_button(parent, **kwargs):
            btn = MagicMock()
            btn.kwargs = kwargs
            buttons.append(btn)
            return btn

        with patch("pyqwk.gui.ttk.Button", side_effect=mock_button):
            gui_app.show_stats_window()

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


def test_save_report_cancelled(gui_app):
    gui_app.current_paths = ["test.qwk"]

    with (
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="") as mock_ask,
        patch("pyqwk.core.show_stats") as mock_show_stats,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"})
    ):
        buttons = []

        def mock_button(parent, **kwargs):
            btn = MagicMock()
            btn.kwargs = kwargs
            buttons.append(btn)
            return btn

        with patch("pyqwk.gui.ttk.Button", side_effect=mock_button):
            gui_app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_not_called()


def test_save_report_error(gui_app):
    gui_app.current_paths = ["test.qwk"]
    gui_app.logger = MagicMock()

    with (
        patch("pyqwk.gui.tk.Toplevel"),
        patch("pyqwk.gui.tk.Text"),
        patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="report.json") as mock_ask,
        patch("pyqwk.gui.messagebox.showerror") as mock_error,
        patch("pyqwk.gui.calculate_archive_stats", return_value={"file": "test.qwk"}),
        patch("pyqwk.core.show_stats", side_effect=Exception("Disk full")) as mock_show_stats
    ):
        buttons = []

        def mock_button(parent, **kwargs):
            btn = MagicMock()
            btn.kwargs = kwargs
            buttons.append(btn)
            return btn

        with patch("pyqwk.gui.ttk.Button", side_effect=mock_button):
            gui_app.show_stats_window()

        save_btn = next(b for b in buttons if b.kwargs.get("text") == "Save Report...")
        save_report_cmd = save_btn.kwargs["command"]

        save_report_cmd()

        mock_ask.assert_called_once()
        mock_show_stats.assert_called_once()
        mock_error.assert_any_call("Save Report Error", "Disk full")


# --- Tests from test_lead_qa_gui_tclerror_coverage.py ---

def test_focus_exclude_tclerror_handler():
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.detail_text = MagicMock()
            app.exclude_entry = MagicMock()
            app.exclude_var = MagicMock()

            app.detail_text.tag_ranges.side_effect = tk.TclError("Mock TclError")
            root.focus_get.return_value = None

            app._focus_exclude()

            app.detail_text.tag_ranges.assert_called_with("sel")
            app.exclude_entry.focus_set.assert_called_once()
