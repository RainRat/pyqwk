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
