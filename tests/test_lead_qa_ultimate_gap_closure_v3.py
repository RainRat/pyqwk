import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch
import datetime
import io
from pyqwk.gui import QwkGuiApp
from pyqwk.core import (
    ProcessingSettings, ParsedMessage, MessageHeader,
    ConferenceMap, process_merged_files
)

def test_gui_stats_rendering_gaps():
    """Cover conversation analysis and fastest responders in the stats window."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.root = root
            app.current_paths = ["test.zip"]
            app.logger = MagicMock()
            app.status_label = MagicMock()
            app._current_settings = MagicMock()
            app._update_status_bar = MagicMock()

            stats = {
                "file": "test.zip",
                "matching_messages": 10,
                "total_messages": 10,
                "dates": {"earliest": "2024-01-01T00:00:00", "latest": "2024-01-01T01:00:00"},
                "private_count": 0,
                "attachments_count": 0,
                "reply_count": 5,
                "reply_rate": 50.0,
                "avg_message_length": 100,
                "authors": [], "recipients": [], "bbses": [], "conferences": [],
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
                with patch("tkinter.Toplevel"):
                    with patch("tkinter.Text") as mock_text:
                        app.show_stats_window()

def test_gui_sorting_words_gaps():
    """Cover both object-based and fallback-based word count sorting."""
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.message_list = MagicMock()
            app.messages = []
            app._apply_zebra_striping = MagicMock()
            app._reset_column_headers = MagicMock()

            # 1. Object-based sorting
            msg = MagicMock(spec=ParsedMessage)
            msg.header = MagicMock(spec=MessageHeader)
            msg.text = "one two three"
            app.messages = [msg]
            app.message_list.get_children.return_value = ["0"]

            app.sort_column("Words", False)

            # 2. Fallback-based sorting
            app.message_list.get_children.return_value = ["999"]
            app.message_list.set.return_value = "42"
            app.sort_column("Words", False)

            app.message_list.set.return_value = "invalid"
            app.sort_column("Words", False)

def test_core_process_merged_files_limit_break():
    """Cover line 3700 in core.py."""
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format="text", separator="auto",
        output_mode="stdout", output_path=None,
        encoding="cp437", limit=1, sort="num", quiet=True
    )
    msg1 = ParsedMessage("msg1", 1, None, 1, MessageHeader(" ", 1, "01-01-24", "10:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))
    msg2 = ParsedMessage("msg2", 2, None, 1, MessageHeader(" ", 2, "01-01-24", "10:05", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""))
    bd = ConferenceMap({1: "Conf1"})

    logger = MagicMock()
    with patch("pyqwk.core.load_data", return_value=([msg1, msg2], bd)):
        with patch("sys.stdout", new=io.StringIO()):
            process_merged_files(["test.qwk"], settings, logger)
