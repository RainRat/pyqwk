import sys
from unittest.mock import MagicMock, patch

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

import pytest
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    # Mock some methods that might be called during init
    root.after = MagicMock()
    return QwkGuiApp(root)

def test_stats_window_trigger(app):
    """Test that the statistics window can be triggered and calls calculate_archive_stats."""
    app.current_path = "test.qwk"
    app.logger = MagicMock()

    # Mock calculate_archive_stats and render_stats_as_text
    mock_stats = {"file": "test.qwk", "total_messages": 10, "matching_messages": 10, "attachments_count": 0, "dates": {"earliest": None, "latest": None}, "authors": [], "recipients": [], "conferences": [], "subjects": [], "keywords": [], "day_of_week": {}, "hour_of_day": {}, "year_distribution": {}, "month_distribution": {}, "private_count": 0, "reply_count": 0, "reply_rate": 0.0, "avg_message_length": 0.0}

    with patch("pyqwk.gui.calculate_archive_stats", return_value=mock_stats) as mock_calc, \
         patch("pyqwk.gui.render_stats_as_text", return_value="Mock Report") as mock_render, \
         patch("pyqwk.gui.tk.Toplevel") as mock_toplevel:

        app.show_stats_window()

        mock_calc.assert_called_once()
        mock_render.assert_called_once_with(mock_stats, use_colors=False)
        mock_toplevel.assert_called_once()

def test_stats_window_no_path(app):
    """Test that show_stats_window shows a warning if no archive is open."""
    app.current_path = None

    with patch("pyqwk.gui.messagebox.showwarning") as mock_warning:
        app.show_stats_window()
        mock_warning.assert_called_once()
