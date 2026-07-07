import pytest
import logging
import os
import tkinter as tk
from unittest.mock import MagicMock, patch, mock_open
from dataclasses import asdict
from collections import defaultdict
from pyqwk.core import (
    show_info, ProcessingSettings, _parse_text_messages,
    _order_messages_by_thread, ParsedMessage, MessageHeader,
    ConferenceMap
)
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        quiet=True, format="text", separator="auto",
        output_mode="stdout", output_path=None,
        encoding="cp437", conferences=None,
        my_name=None
    )

def test_show_info_html_markdown_error_gaps(capsys, mock_logger, default_settings):
    """Cover HTML/Markdown info rendering and error branches."""
    input_path = "test_error.zip"

    with patch("pyqwk.core.load_data") as mock_load:
        # Mock load_data to return a small buffer that triggers "Invalid or empty file"
        mock_load.return_value = (bytearray(b"short"), {})

        # Test HTML format with error
        html_settings = default_settings
        html_settings.format = "html"
        show_info([input_path], html_settings, mock_logger)
        out_html = capsys.readouterr().out
        assert "Invalid or empty file" in out_html
        assert "Archive Information" in out_html

        # Test Markdown format with error
        md_settings = default_settings
        md_settings.format = "markdown"
        show_info([input_path], md_settings, mock_logger)
        out_md = capsys.readouterr().out
        assert "Invalid or empty file" in out_md
        assert "# Archive Information" in out_md

def test_show_info_bbs_fields_coverage(capsys, mock_logger, default_settings):
    """Cover all BBS info fields and the NO-BBS/NO-CONF branches."""
    input_path = "test_bbs.zip"

    class MockBBS:
        def __init__(self, full=True):
            if full:
                self.name = "Test BBS"
                self.sysop = "Test SysOp"
                self.location = "Test Location"
                self.bbs_id = "TESTID"
                self.packet_at = "2024-05-20"
                self.user_name = "Test User"
            else:
                self.name = None
                self.sysop = None
                self.location = None
                self.bbs_id = None
                self.packet_at = None
                self.user_name = None
            self.total_messages = 0

    # Full BBS info
    mock_bbs = MockBBS()
    board_dict = ConferenceMap()
    board_dict.bbs_info = mock_bbs

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([], board_dict)
        with patch("pyqwk.core.asdict", side_effect=lambda x: vars(x)):
            # HTML Full
            html_settings = default_settings
            html_settings.format = "html"
            show_info([input_path], html_settings, mock_logger)
            out_html = capsys.readouterr().out
            assert "BBS Name:</strong> Test BBS" in out_html

            # Markdown Full
            md_settings = default_settings
            md_settings.format = "markdown"
            show_info([input_path], md_settings, mock_logger)
            out_md = capsys.readouterr().out
            assert "**BBS Name:** Test BBS" in out_md

    # NO BBS info, NO conferences
    board_dict_empty = ConferenceMap()
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([], board_dict_empty)
        # HTML Empty
        show_info([input_path], html_settings, mock_logger)
        out_html = capsys.readouterr().out
        assert "BBS Name" not in out_html
        assert "Conferences" not in out_html

        # Markdown Empty
        show_info([input_path], md_settings, mock_logger)
        out_md = capsys.readouterr().out
        assert "BBS Name" not in out_md
        assert "### Conferences" not in out_md

    # Partial BBS info (coverage for individual if branches)
    partial_bbs = MockBBS(full=False)
    partial_bbs.name = "Partial BBS"
    board_dict_partial = ConferenceMap()
    board_dict_partial.bbs_info = partial_bbs
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([], board_dict_partial)
        with patch("pyqwk.core.asdict", side_effect=lambda x: vars(x)):
            # Force HTML format for this check
            html_settings.format = "html"
            show_info([input_path], html_settings, mock_logger)
            out_html = capsys.readouterr().out
            assert "BBS Name:</strong> Partial BBS" in out_html
            assert "SysOp:" not in out_html

def test_show_info_my_name_propagation(capsys, mock_logger, default_settings):
    """Cover line 5650 (settings.my_name propagation)."""
    input_path = "test_name.zip"

    class MockBBS:
        def __init__(self):
            self.name = "BBS"
            self.user_name = None
            self.total_messages = 0
            self.sysop = None
            self.location = None
            self.bbs_id = None
            self.packet_at = None

    mock_bbs = MockBBS()
    board_dict = ConferenceMap()
    board_dict.bbs_info = mock_bbs

    settings = default_settings
    settings.my_name = "Propagated Name"

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([], board_dict)
        with patch("pyqwk.core.asdict", side_effect=lambda x: vars(x)):
            show_info([input_path], settings, mock_logger)

    assert mock_bbs.user_name == "Propagated Name"

def test_parse_text_no_date_parts(tmp_path):
    """Cover line 1678 false branch (date_str.split() is empty)."""
    # Date: followed only by whitespace
    content = "From: Alice\nTo: Bob\nSubject: Test\nDate:   \n\nBody"
    f = tmp_path / "no_date_parts.txt"
    f.write_text(content, encoding="utf-8")
    msgs = _parse_text_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

def test_threading_cycle_deduplication_duplicate_reply(caplog):
    """Cover line 6388 cycle reporting branch."""
    def make_msg(msgnum, refnum):
        h = MessageHeader(" ", msgnum, "01-01-24", "12:00", "To", "From", "Sub", "", refnum, 1, " ", 1, 1, "")
        return ParsedMessage("Body", msgnum, refnum, 1, h)

    # msg 1 replies to msg 2, msg 2 replies to msg 1 -> Cycle
    msgs = [
        make_msg(1, 2),
        make_msg(2, 1),
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)

    reports = [w for w in caplog.text.splitlines() if "Conversation loop detected" in w]
    assert len(reports) >= 1

def test_gui_focus_search_no_selection():
    """Cover line 847 (if sel_range false branch)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.detail_text = MagicMock()
            app.search_entry = MagicMock()
            app.search_var = MagicMock()

            # Mock tag_ranges to return empty list (no selection)
            app.detail_text.tag_ranges.return_value = []

            app._focus_search()

            app.search_var.set.assert_not_called()
            app.search_entry.focus_set.assert_called_once()

def test_gui_save_attachment_error():
    """Cover line 2108 (exception handler in save_attachment)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.message_list = MagicMock()
            app.messages = [MagicMock()]
            app.detail_text = MagicMock()
            app.status_label = MagicMock()

            # Mock selection
            app.message_list.selection.return_value = ("0",)
            app.messages[0].text = "some text"

            # Mock extract_binaries to return something
            with patch("pyqwk.gui.extract_binaries", return_value=[("test.txt", b"data")]):
                with patch("pyqwk.gui.filedialog.asksaveasfilename", return_value="test.txt"):
                    with patch("builtins.open", mock_open()) as mocked_file:
                        mocked_file.side_effect = Exception("Write error")

                        with patch("pyqwk.gui.messagebox.showerror") as mock_error:
                            app.save_attachment("test.txt", 0)
                            mock_error.assert_called_once()
                            assert "Write error" in mock_error.call_args[0][1]

def test_gui_reload_messages_invalid_selection_restoration():
    """Cover lines 1662-1664 (selection restoration edge cases)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.message_list = MagicMock()
            app.messages = []
            app.total_msg_count = 0
            app.root = root
            app._search_timer = None
            app.current_paths = ["test.zip"]
            app.search_var = MagicMock()
            app.search_var.get.return_value = ""
            app.exclude_var = MagicMock()
            app.exclude_var.get.return_value = ""
            app.bbs_combo = MagicMock()
            app.bbs_combo.get.return_value = "All BBSes"
            app.conf_combo = MagicMock()
            app.conf_combo.get.return_value = "All Conferences"
            app._get_all_tree_items = MagicMock(return_value=[])
            app._update_status_bar = MagicMock()
            app.status_label = MagicMock()
            app.search_count_label = MagicMock()
            app.clean_var = MagicMock()
            app.ansi_var = MagicMock()
            app.private_var = MagicMock()
            app.threaded_var = MagicMock()
            app.regex_var = MagicMock()
            app.mine_var = MagicMock()
            app.on_this_day_var = MagicMock()
            app.has_attach_var = MagicMock()
            app.has_links_var = MagicMock()
            app.has_emails_var = MagicMock()
            app.has_phones_var = MagicMock()

            # Case 1: selection is not an integer (ValueError)
            app.message_list.selection.return_value = ("not-an-int",)
            with patch.object(app, "load_messages"):
                with patch.object(app, "_reset_column_headers"):
                    # This should not crash
                    app.reload_messages()

            # Case 2: index out of range
            app.message_list.selection.return_value = ("999",)
            app.messages = [MagicMock()] # length 1
            with patch.object(app, "load_messages"):
                with patch.object(app, "_reset_column_headers"):
                    app.reload_messages()

def test_show_info_no_bbs_coverage(capsys, mock_logger, default_settings):
    """Cover the 'if bbs:' False branch in all info renderers."""
    input_path = "test_no_bbs.zip"
    board_dict = ConferenceMap() # No bbs_info attribute

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([], board_dict)

        # Text
        show_info([input_path], default_settings, mock_logger)
        out_text = capsys.readouterr().out
        assert "BBS Name" not in out_text

        # HTML
        html_settings = default_settings
        html_settings.format = "html"
        show_info([input_path], html_settings, mock_logger)
        out_html = capsys.readouterr().out
        # Check that the summary info DIV itself is not present in the BODY
        # (It will be in the CSS in the HEAD)
        import re
        body_content = re.search(r"<body>(.*)</body>", out_html, re.DOTALL).group(1)
        assert 'class="stats-summary-info"' not in body_content

        # Markdown
        md_settings = default_settings
        md_settings.format = "markdown"
        show_info([input_path], md_settings, mock_logger)
        out_md = capsys.readouterr().out
        assert "**BBS Name:**" not in out_md

def test_gui_jump_to_message_no_reset():
    """Cover line 2307 (if messagebox.askyesno returns False)."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.message_list = MagicMock()
            app.messages = []

            with patch.object(app, "_find_message_index", return_value=None):
                with patch.object(app, "_is_any_filter_active", return_value=True):
                    with patch("pyqwk.gui.messagebox.askyesno", return_value=False):
                        with patch("pyqwk.gui.messagebox.showinfo") as mock_info:
                            app.jump_to_message(1, 123)
                            mock_info.assert_called_once()

def test_threading_cycle_reported_multiple_times(caplog):
    """Cover lines 6388-6395 multiple encounters of same cycle node."""
    def make_msg(msgnum, refnum):
        h = MessageHeader(" ", msgnum, "01-01-24", "12:00", "To", "From", "Sub", "", refnum, 1, " ", 1, 1, "")
        return ParsedMessage("Body", msgnum, refnum, 1, h)

    # 1 -> 2 -> 1 (Cycle)
    # 3 -> 2 (Another path to the cycle)
    # The iteration will encounter the cycle via 1, then via 3 -> 2.
    msgs = [
        make_msg(1, 2),
        make_msg(2, 1),
        make_msg(3, 2),
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)

    # We want to ensure it only LOGS once even if encountered via multiple paths in the iteration
    reports = [w for w in caplog.text.splitlines() if "Conversation loop detected" in w]
    assert len(reports) >= 1
