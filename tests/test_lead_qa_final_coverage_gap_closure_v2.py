import pytest
import logging
import io
import tkinter as tk
from unittest.mock import MagicMock, patch, mock_open
from pyqwk.core import (
    _parse_json_messages, _xml_safe, process_merged_files,
    ProcessingSettings, ConferenceMap, BBSInfo, ParsedMessage,
    MessageHeader
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
        encoding="cp437"
    )

def test_parse_json_messages_metadata_and_single_dict():
    """Cover lines 1173-1176 in core.py."""
    # metadata type
    data_meta = {"type": "metadata"}
    assert _parse_json_messages(data_meta) == []

    # single dict (not a list, not qwk_archive, not metadata)
    data_single = {"header": {"confnum": 1, "msgnum": 100}, "text": "hello"}
    msgs = _parse_json_messages(data_single)
    assert len(msgs) == 1
    assert msgs[0].msgnum == 100

    # entry that is not a dict
    data_mixed = [data_single, "not-a-dict"]
    msgs = _parse_json_messages(data_mixed)
    assert len(msgs) == 1

def test_xml_safe_none():
    """Cover line 3882 in core.py."""
    assert _xml_safe(None) == ""

def test_process_merged_files_merge_logic_coverage(mock_logger, default_settings, tmp_path):
    """Cover lines 3530, 3532 (board_dict_to_use merging) and 3694 (sort limit break)."""
    # Create mock QWK data for two different archives
    settings = default_settings
    settings.sort = "num"
    settings.limit = 1

    msg1 = ParsedMessage("msg1", 1, None, 1, MessageHeader(" ", 1, "01-01-24", "10:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))
    msg2 = ParsedMessage("msg2", 2, None, 2, MessageHeader(" ", 2, "01-01-24", "11:00", "To", "From", "Sub", "", None, 1, " ", 2, 1, ""))

    bd1 = ConferenceMap({1: "Conf1"})
    bd1.bbs_info = None # First archive has no BBS info

    bd2 = ConferenceMap({2: "Conf2"})
    bd2.bbs_info = BBSInfo(name="BBS2")

    # Second msg to ensure limit break is hit in the sort buffer loop
    msg1_2 = ParsedMessage("msg1_2", 3, None, 1, MessageHeader(" ", 3, "01-01-24", "10:05", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))

    # We need to mock load_data to return these
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.side_effect = [
            ([msg1, msg1_2], bd1),
            ([msg2], bd2)
        ]

        # Test board_dict_to_use merging (lines 3530, 3532)
        # We pass two paths to trigger the merge logic
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["archive1.qwk", "archive2.qwk"], settings, mock_logger)
            output = mock_stdout.getvalue()
            # Verify handle_output limit break (line 3694)
            # settings.limit = 1, so it should only show msg2 (due to sort num reverse=False, msg1 comes first, but it is buffered)
            # Actually sort num is (conf, msgnum). msg1 is (1,1), msg1_2 is (1,3), msg2 is (2,2).
            # Order: msg1, msg1_2, msg2. Limit 1 means only msg1 should be processed.
            assert "msg1" in output
            assert "msg1_2" not in output
            assert "msg2" not in output

def test_gui_navigate_bbs_defensive_coverage():
    """Cover lines 819, 824, 830 in gui.py."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.bbs_combo = MagicMock()
            app.search_entry = MagicMock()
            app.exclude_entry = MagicMock()

            # Line 819: empty bbs values
            app.bbs_combo.__getitem__.return_value = []
            app._navigate_bbs(1)
            app.bbs_combo.current.assert_not_called()

            # Line 824: focused widget is search_entry
            app.bbs_combo.__getitem__.return_value = ["BBS1"]
            root.focus_get.return_value = app.search_entry
            app._navigate_bbs(1)
            app.bbs_combo.current.assert_not_called()

            # Line 830: current_idx == -1
            root.focus_get.return_value = None
            app.bbs_combo.current.return_value = -1
            app.bbs_combo.__getitem__.return_value = ["BBS1", "BBS2"]
            with patch.object(app, "reload_messages"):
                app._navigate_bbs(-1) # delta < 0
                app.bbs_combo.current.assert_any_call(1) # num_values - 1

def test_gui_block_text_input_bbs_nav_shortcuts():
    """Cover lines 508-509, 511-512 in gui.py."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app._navigate_bbs = MagicMock()

            event = MagicMock()

            # {
            event.keysym = "braceleft"
            event.char = "{"
            assert app._block_text_input(event) == "break"
            app._navigate_bbs.assert_called_with(-1)

            # }
            event.keysym = "braceright"
            event.char = "}"
            assert app._block_text_input(event) == "break"
            app._navigate_bbs.assert_called_with(1)

def test_gui_show_stats_window_conversation_coverage():
    """Cover lines 2590-2599, 2657, 2664-2668 in gui.py."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.current_paths = ["test.zip"]
            app.logger = MagicMock()
            app.status_label = MagicMock()
            app._update_status_bar = MagicMock()

            # Mock stats with conversation info
            stats = {
                "file": "test.zip",
                "matching_messages": 10,
                "total_messages": 10,
                "dates": {"earliest": "2024-01-01T00:00:00", "latest": "2024-01-01T01:00:00"},
                "private_count": 0,
                "reply_count": 5,
                "reply_rate": 50.0,
                "avg_message_length": 100,
                "authors": [{"name": "Alice", "count": 10}],
                "recipients": [], "bbses": [], "conferences": [],
                "subjects": [], "keywords": [], "links": [], "emails": [], "phones": [],
                "top_attachments": [], "top_attachment_types": [],
                "year_distribution": {"2024": 10},
                "month_distribution": {}, "day_of_week": {}, "hour_of_day": {},
                "conversation": {
                    "thread_count": 1,
                    "avg_thread_length": 5.0,
                    "max_thread_length": 5,
                    "avg_response_time": 3600,
                    "min_response_time": 60,
                    "top_responders": [{"name": "Alice", "count": 5, "avg_speed": 720}]
                }
            }

            with patch("pyqwk.gui.calculate_archive_stats", return_value=stats):
                with patch("pyqwk.gui.ProcessingSettings", return_value=MagicMock()):
                    with patch("tkinter.Toplevel"):
                        # show_stats_window calls _render_stats_html (injected into a Text widget)
                        app.show_stats_window()
