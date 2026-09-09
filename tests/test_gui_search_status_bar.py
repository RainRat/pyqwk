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
        assert "Showing 0 of 100 messages from test.qwk" in status_text


def test_status_bar_displays_active_filters():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"):
        app = QwkGuiApp(root)

        app.status_label = MagicMock()
        app.search_var = MagicMock()
        app.search_var.get.return_value = ""
        app.exclude_var = MagicMock()
        app.exclude_var.get.return_value = ""

        app.bbs_combo = MagicMock()
        app.bbs_combo.get.return_value = "Digital BBS (10)"
        app.conf_combo = MagicMock()
        app.conf_combo.get.return_value = "General Chat (5)"

        app.min_words_var = MagicMock()
        app.min_words_var.get.return_value = "50"
        app.max_words_var = MagicMock()
        app.max_words_var.get.return_value = "500"

        app.private_var = MagicMock()
        app.private_var.get.return_value = False

        app.has_attach_var = MagicMock()
        app.has_attach_var.get.return_value = True
        app.mine_var = MagicMock()
        app.mine_var.get.return_value = True

        app._search_matches = []
        app.messages = []
        app.total_msg_count = 100
        app.source_display_name = "test.qwk"

        app._update_status_bar()

        app.status_label.config.assert_called_once()
        status_text = app.status_label.config.call_args[1]["text"]
        assert "Filters: BBS: Digital BBS (10), Conf: General Chat (5), Min Words: 50, Max Words: 500, Private Hidden, Attachments, My Messages" in status_text
