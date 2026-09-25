import sys
from unittest.mock import MagicMock, patch
import pytest

mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp


def test_status_bar_displays_active_query_and_exclusion():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"):
        app = QwkGuiApp(root)

        app.status_label = MagicMock()
        app.search_var = MagicMock()
        app.search_var.get.return_value = "vintage"
        app.exclude_var = MagicMock()
        app.exclude_var.get.return_value = "spam"
        app._search_matches = []
        app.messages = []
        app.total_msg_count = 100
        app.source_display_name = "test.qwk"

        app._update_status_bar()

        app.status_label.config.assert_called_once()
        status_text = app.status_label.config.call_args[1]["text"]
        assert 'Query: "vintage"' in status_text
        assert 'Excluding: "spam"' in status_text
        assert "Showing 0 of 100 messages (Filtered) from test.qwk" in status_text


def test_status_bar_displays_unfiltered_summary_when_no_filters_active():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"):
        app = QwkGuiApp(root)

        app.status_label = MagicMock()
        app.search_var = MagicMock()
        app.search_var.get.return_value = ""
        app.exclude_var = MagicMock()
        app.exclude_var.get.return_value = ""
        app.bbs_combo = MagicMock()
        app.bbs_combo.get.return_value = "All BBSes"
        app.conf_combo = MagicMock()
        app.conf_combo.get.return_value = "All Conferences"
        app.min_words_var = MagicMock()
        app.min_words_var.get.return_value = ""
        app.max_words_var = MagicMock()
        app.max_words_var.get.return_value = ""

        app.private_var = MagicMock()
        app.private_var.get.return_value = True

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

        app._search_matches = []
        app.messages = [MagicMock()]
        app.total_msg_count = 1
        app.source_display_name = "test.qwk"

        app._update_status_bar()

        app.status_label.config.assert_called_once()
        status_text = app.status_label.config.call_args[1]["text"]
        assert "Showing 1 of 1 messages from test.qwk" in status_text
        assert "(Filtered)" not in status_text


def test_status_bar_displays_selected_message_index_with_total_and_filtered_indicators():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"):
        app = QwkGuiApp(root)

        app.status_label = MagicMock()
        app.search_var = MagicMock()
        app.search_var.get.return_value = "vintage"
        app.exclude_var = MagicMock()
        app.exclude_var.get.return_value = ""
        app._search_matches = []
        app.messages = [MagicMock(), MagicMock(), MagicMock()]
        app.total_msg_count = 50
        app.source_display_name = "test.qwk"

        app._update_status_bar(message_index=1)

        app.status_label.config.assert_called_once()
        status_text = app.status_label.config.call_args[1]["text"]
        assert 'Query: "vintage"' in status_text
        assert "Message 2 of 3 (Total: 50)" in status_text
        assert "from test.qwk (Filtered)" in status_text
