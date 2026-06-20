import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    _parse_json_messages,
    _xml_safe,
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)
import logging

def test_parse_json_metadata_records():
    # Line 1174: data.get("type") == "metadata"
    assert _parse_json_messages({"type": "metadata"}) == []

    # Line 1180: entry.get("type") == "metadata" in a list
    data = [
        {"type": "metadata", "other": "info"},
        {"header": {"confnum": 1, "msgnum": 101}, "text": "Hello"}
    ]
    msgs = _parse_json_messages(data)
    assert len(msgs) == 1
    assert msgs[0].msgnum == 101

def test_xml_safe_none_handling():
    # Line 3882: text is None
    assert _xml_safe(None) == ""

def test_process_merged_files_sort_buffer_exit_and_board_merge(tmp_path):
    # Setup for line 3694: break out of sort_buffer loop
    # Setup for lines 3530, 3532: board merge logic

    # Create a dummy message file
    msg_file = tmp_path / "test.json"
    msg_file.write_text('{"type": "qwk_archive", "conferences": {"1": "Conf1"}, "messages": [{"header": {"confnum": 1, "msgnum": 1}, "text": "M1"}]}')

    # Another one with different conference and BBS info
    msg_file2 = tmp_path / "test2.json"
    msg_file2.write_text('{"type": "qwk_archive", "bbs_info": {"name": "BBS2", "bbs_id": "ID2"}, "conferences": {"2": "Conf2"}, "messages": [{"header": {"confnum": 2, "msgnum": 2}, "text": "M2"}]}')

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="utf-8", sort="date", limit=1  # limit=1 will make handle_output return True after 1 msg
    )

    logger = logging.getLogger("test")

    # We use sort="date" to force non-streaming mode (sort_buffer)
    # We use limit=1 to trigger the 'break' in the sort_buffer loop (line 3694)

    with patch("sys.stdout", new=MagicMock()):
        process_merged_files([str(msg_file), str(msg_file2)], settings, logger)

    # To specifically hit 3530/3532, we need board_dict_to_use to already be initialized.
    # The first file initializes it. The second file merges into it.
    # Line 3530: if k not in board_dict_to_use: board_dict_to_use[k] = v
    # Line 3532: if bbs_info and not board_dict_to_use.bbs_info: board_dict_to_use.bbs_info = bbs_info

    # To hit 3532, the first file should NOT have bbs_info, and the second SHOULD.
    msg_file_no_bbs = tmp_path / "no_bbs.json"
    msg_file_no_bbs.write_text('{"type": "qwk_archive", "conferences": {"1": "Conf1"}, "messages": [{"header": {"confnum": 1, "msgnum": 1}, "text": "M1"}]}')

    with patch("sys.stdout", new=MagicMock()):
        process_merged_files([str(msg_file_no_bbs), str(msg_file2)], settings, logger)

def test_gui_bbs_shortcuts():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk'), \
         patch('pyqwk.gui.font'):
        from pyqwk.gui import QwkGuiApp
        app = QwkGuiApp(mock_root)
        app._navigate_bbs = MagicMock()

        # Line 508-509: braceleft / {
        event = MagicMock()
        event.keysym = "braceleft"
        event.char = "{"
        event.state = 0
        assert app._block_text_input(event) == "break"
        app._navigate_bbs.assert_called_with(-1)

        # Line 511-512: braceright / }
        app._navigate_bbs.reset_mock()
        event.keysym = "braceright"
        event.char = "}"
        assert app._block_text_input(event) == "break"
        app._navigate_bbs.assert_called_with(1)

def test_gui_navigate_bbs_edge_cases():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk'), \
         patch('pyqwk.gui.font'):
        from pyqwk.gui import QwkGuiApp
        app = QwkGuiApp(mock_root)
        app.bbs_combo = MagicMock()
        app.search_entry = MagicMock()
        app.exclude_entry = MagicMock()
        app.reload_messages = MagicMock()

        # Line 819: if not self.bbs_combo["values"]: return
        app.bbs_combo.__getitem__.return_value = []
        app._navigate_bbs(1)
        app.reload_messages.assert_not_called()

        # Line 824: focused_widget in (self.search_entry, self.exclude_entry)
        app.bbs_combo.__getitem__.return_value = ["BBS1", "BBS2"]
        mock_root.focus_get.return_value = app.search_entry
        app._navigate_bbs(1)
        app.reload_messages.assert_not_called()

        # Line 830: if current_idx == -1: new_idx = 0 if delta > 0 else num_values - 1
        mock_root.focus_get.return_value = None
        app.bbs_combo.current.return_value = -1
        app._navigate_bbs(1)
        app.bbs_combo.current.assert_called_with(0)

        app.bbs_combo.current.reset_mock()
        app.bbs_combo.current.return_value = -1
        app._navigate_bbs(-1)
        app.bbs_combo.current.assert_called_with(1) # last index

def test_gui_stats_conversation_and_extra_labels():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk') as mock_tk, \
         patch('pyqwk.gui.ttk'), \
         patch('pyqwk.gui.font'), \
         patch('pyqwk.gui.calculate_archive_stats') as mock_calc:
        from pyqwk.gui import QwkGuiApp

        # Setup stats with conversation data to hit 2590-2602 and top_responders 2664-2673
        stats = {
            "file": "test.qwk",
            "matching_messages": 10,
            "total_messages": 10,
            "attachments_count": 0,
            "dates": {"earliest": "2023-01-01T00:00:00", "latest": "2023-01-02T00:00:00"},
            "private_count": 0,
            "reply_rate": 50,
            "reply_count": 5,
            "avg_message_length": 100,
            "avg_word_count": 20,
            "conversation": {
                "thread_count": 2,
                "avg_thread_length": 5.0,
                "max_thread_length": 8,
                "avg_response_time": 3600,
                "min_response_time": 60,
                "top_responders": [
                    {"name": "User1", "count": 3, "avg_speed": 120}
                ]
            },
            "year_distribution": {"2023": 10},
            "month_distribution": {},
            "authors": [],
            "recipients": [],
            "bbses": [],
            "conferences": [],
            "subjects": [],
            "keywords": [],
            "links": [{"url": "http://test.com", "count": 1}], # to hit extra_label_map logic 2657?
            # Wait, 2657 is if extra_label_map and label in extra_label_map
            "emails": [],
            "phones": [],
            "top_attachments": [],
            "top_attachment_types": [],
            "day_of_week": {},
            "hour_of_day": {}
        }
        mock_calc.return_value = stats

        app = QwkGuiApp(mock_root)
        app.current_paths = ["test.qwk"]

        # Mock Text widget
        mock_text = MagicMock()
        mock_tk.Toplevel.return_value = MagicMock()
        mock_tk.Text.return_value = mock_text

        app.show_stats_window()

        # Verify conversation analysis was inserted (Lines 2590-2602)
        # We check for calls to insert
        found_conv = False
        for call in mock_text.insert.call_args_list:
            if "Conversation Analysis" in str(call):
                found_conv = True
                break
        assert found_conv

        # Line 2657: extra_label_map and label in extra_label_map
        # This is hit via render_gui_bar_chart when extra_label_map is provided.
        # Fastest Responders uses extra_label_map for speed_map.
        found_speed = False
        for call in mock_text.insert.call_args_list:
            if "(2.0m)" in str(call): # 120s = 2.0m
                found_speed = True
                break
        assert found_speed
