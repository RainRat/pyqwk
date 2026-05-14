from unittest.mock import MagicMock, patch
import pytest
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters, _get_message_mapping, _write_html, _write_markdown, _write_text, BBSInfo

# --- Core Coverage Tests ---

def create_msg(text="Hello world", author="Alice", to="Bob", subject="Greetings", confnum=1, bbs_name="MyBBS"):
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto=to, msgfrom=author, msgsubject=subject, msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    return ParsedMessage(text=text, msgnum=1, refnum=None, confnum=confnum, header=header, bbs_name=bbs_name)

def _make_settings(**kwargs):
    defaults = dict(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="utf-8", regex=False, include_toc=True, my_name=None
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)

def test_exclude_recipients_coverage():
    msg = create_msg(to="TargetUser")
    settings = _make_settings(exclude_recipients=["TargetUser"])
    assert matches_filters(msg, settings, set()) is False

def test_get_message_mapping_bbs_info_user_name_fallback():
    msg = create_msg(author="Alice")
    msg.bbs_info = BBSInfo(user_name="BBSUser")
    mapping = _get_message_mapping(msg, 1)
    assert mapping["my_name"] == "BBSUser"

def test_export_user_name_fallback_html(tmp_path):
    msg = create_msg()
    settings = _make_settings(format="html", include_toc=True, my_name=None)
    bbs_info = BBSInfo(user_name="BBS_User_Name")
    output = tmp_path / "test.html"
    _write_html([msg], str(output), settings=settings, bbs_info=bbs_info)
    content = output.read_text()
    assert "User Name:" in content
    assert "BBS_User_Name" in content

def test_export_user_name_fallback_markdown(tmp_path):
    msg = create_msg()
    settings = _make_settings(format="markdown", include_toc=True, my_name=None)
    bbs_info = BBSInfo(user_name="BBS_User_Name")
    output = tmp_path / "test.md"
    _write_markdown([msg], str(output), settings=settings, bbs_info=bbs_info)
    content = output.read_text()
    assert "**User Name:** BBS_User_Name" in content

def test_export_user_name_fallback_text(capsys):
    msg = create_msg()
    settings = _make_settings(format="text", include_toc=True, my_name=None)
    bbs_info = BBSInfo(user_name="BBS_User_Name")
    _write_text([msg], None, settings=settings, bbs_info=bbs_info)
    captured = capsys.readouterr()
    assert "User:     BBS_User_Name" in captured.out

def test_parse_messages_truncated_error():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="To", msgfrom="From", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=2, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    data = bytearray(b"Produced by pyqwk".ljust(128))
    data.extend(header.to_bytes())
    from pyqwk.core import parse_messages, MessagesDatFormatError
    with pytest.raises(MessagesDatFormatError) as excinfo:
        list(parse_messages(data, None))
    assert "truncated" in str(excinfo.value)

# --- GUI Coverage Tests ---

@pytest.fixture
def mock_gui():
    mock_root = MagicMock()
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.font"),
        patch("pyqwk.gui.messagebox") as mock_msgbox,
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.simpledialog") as mock_simpledialog,
    ):
        def make_mock_var(val=""):
            m = MagicMock()
            m.get.return_value = val
            return m
        mock_tk.StringVar.side_effect = lambda **kwargs: make_mock_var(kwargs.get("value", ""))
        mock_tk.BooleanVar.side_effect = lambda **kwargs: make_mock_var(kwargs.get("value", False))
        mock_tk.IntVar.side_effect = lambda **kwargs: make_mock_var(kwargs.get("value", 0))
        mock_tree = MagicMock()
        mock_ttk.Treeview.return_value = mock_tree
        mock_tree.get_children.return_value = []
        mock_tree.item.return_value = {"tags": []}
        mock_text = MagicMock()
        mock_tk.Text.return_value = mock_text
        app = QwkGuiApp(mock_root)
        app.messages = []
        app.message_list = mock_tree
        app.detail_text = mock_text
        app.search_entry = MagicMock()
        app.search_var = make_mock_var("")
        app.exclude_var = make_mock_var("")
        app.search_count_label = MagicMock()
        app.root = mock_root
        app.bbs_combo = MagicMock()
        app.conf_combo = MagicMock()
        app.reload_messages = MagicMock()
        app._update_status_bar = MagicMock()
        app._render_message = MagicMock()
        app._select_by_index = MagicMock()
        app._apply_zebra_striping = MagicMock()
        app.clear_filters = MagicMock()
        app._is_any_filter_active = MagicMock(return_value=True)
        app.msgbox = mock_msgbox
        app.simpledialog = mock_simpledialog
        app._find_message_index = MagicMock()
        yield app

def test_is_any_filter_active_full_coverage(mock_gui):
    mock_gui._is_any_filter_active = QwkGuiApp._is_any_filter_active.__get__(mock_gui, QwkGuiApp)
    mock_gui.search_var.get.return_value = ""
    mock_gui.exclude_var.get.return_value = ""
    mock_gui.bbs_combo.get.return_value = "All BBSes"
    mock_gui.conf_combo.get.return_value = "All Conferences"
    vars_to_mock = [mock_gui.has_attach_var, mock_gui.mine_var, mock_gui.on_this_day_var, mock_gui.has_links_var, mock_gui.has_emails_var, mock_gui.has_phones_var, mock_gui.has_ansi_var]
    for v in vars_to_mock:
        v.get.return_value = False
    mock_gui.private_var.get.return_value = True
    assert mock_gui._is_any_filter_active() is False
    mock_gui.search_var.get.return_value = "findme"
    assert mock_gui._is_any_filter_active() is True
    mock_gui.search_var.get.return_value = ""
    mock_gui.exclude_var.get.return_value = "exclude_me"
    assert mock_gui._is_any_filter_active() is True
    mock_gui.exclude_var.get.return_value = ""
    mock_gui.bbs_combo.get.return_value = "My BBS"
    assert mock_gui._is_any_filter_active() is True
    mock_gui.bbs_combo.get.return_value = "All BBSes"
    mock_gui.conf_combo.get.return_value = "1: General"
    assert mock_gui._is_any_filter_active() is True
    mock_gui.conf_combo.get.return_value = "All Conferences"
    mock_gui.has_attach_var.get.return_value = True
    assert mock_gui._is_any_filter_active() is True
    mock_gui.has_attach_var.get.return_value = False
    mock_gui.private_var.get.return_value = False
    assert mock_gui._is_any_filter_active() is True

def test_pivot_filter_exclusions(mock_gui):
    mock_gui.exclude_var = MagicMock()
    mock_gui._pivot_filter(exclude_author="BadGuy")
    mock_gui.exclude_var.set.assert_any_call("BadGuy")
    mock_gui._pivot_filter(exclude_subject="Re: Topic")
    mock_gui.exclude_var.set.assert_any_call("topic")
    mock_gui._pivot_filter(exclude_bbs_name="EvilBBS")
    mock_gui.exclude_var.set.assert_any_call("EvilBBS")
    mock_gui._pivot_filter(exclude_conf_num=666)
    mock_gui.exclude_var.set.assert_any_call("666")

def test_message_link_jump_callback(mock_gui):
    mock_gui._render_message = QwkGuiApp._render_message.__get__(mock_gui, QwkGuiApp)
    header = MessageHeader(status=" ", msgnum=100, msgdate="01-01-23", msgtime="12:00", msgto="To", msgfrom="From", msgsubject="Subj", msgpassword="", refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" ")
    msg = ParsedMessage(text="Check msg #200", msgnum=100, refnum=None, confnum=1, header=header)
    mock_gui.messages = [msg]
    mock_gui.jump_to_message = MagicMock()
    mock_gui.clean_var.get.return_value = False
    bound_cmds = {}
    def fake_tag_bind(tag, event, cmd): bound_cmds[tag] = cmd
    mock_gui.detail_text.tag_bind.side_effect = fake_tag_bind
    mock_gui._render_message(0)
    link_tag = next(t for t in bound_cmds if t.startswith("msg_link"))
    callback = bound_cmds[link_tag]
    callback(None)
    mock_gui.jump_to_message.assert_called_with(1, 200)

def test_navigate_search_matches_index_error_handling(mock_gui):
    mock_gui._search_matches = [("1.0", "1.5")]
    mock_gui._current_match_idx = 0
    mock_gui.message_list.selection.return_value = ["not_an_int"]
    mock_gui._navigate_search_matches(0)
    mock_gui._update_status_bar.assert_called()

def test_on_search_shift_enter_fallback(mock_gui):
    mock_gui.root.focus_get.return_value = None
    mock_gui._on_search_shift_enter(None)
    mock_gui.reload_messages.assert_called()
    mock_gui.message_list.focus_set.assert_called()

def test_prompt_jump_to_message_reset_filters_coverage(mock_gui):
    mock_gui.messages = [1]
    mock_gui.simpledialog.askinteger.return_value = 123
    mock_gui._find_message_index.side_effect = [None, 5]
    mock_gui.msgbox.askyesno.return_value = True
    mock_gui.prompt_jump_to_message = QwkGuiApp.prompt_jump_to_message.__get__(mock_gui, QwkGuiApp)
    mock_gui.prompt_jump_to_message()
    mock_gui.clear_filters.assert_called()
    mock_gui._select_by_index.assert_called_with(5)

def test_jump_to_message_reset_filters_coverage(mock_gui):
    mock_gui._find_message_index.side_effect = [None, 10]
    mock_gui.msgbox.askyesno.return_value = True
    mock_gui.jump_to_message = QwkGuiApp.jump_to_message.__get__(mock_gui, QwkGuiApp)
    mock_gui.jump_to_message(1, 456)
    mock_gui.clear_filters.assert_called()
    mock_gui._select_by_index.assert_called_with(10)
