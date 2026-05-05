import sys
from unittest.mock import MagicMock, patch, ANY

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

    # Mock calculate_archive_stats
    mock_stats = {
        "file": "test.qwk",
        "total_messages": 10,
        "matching_messages": 10,
        "attachments_count": 1,
        "dates": {"earliest": "2023-01-01T12:00:00", "latest": "2023-01-01T13:00:00"},
        "authors": [{"name": "User", "count": 5}],
        "recipients": [],
        "conferences": [],
        "subjects": [],
        "keywords": [],
        "day_of_week": {"Monday": 10},
        "hour_of_day": {"12": 10},
        "year_distribution": {"2023": 10},
        "month_distribution": {"2023-01": 10},
        "private_count": 0,
        "reply_count": 0,
        "reply_rate": 0.0,
        "avg_message_length": 100.0,
    }

    with (
        patch(
            "pyqwk.gui.calculate_archive_stats", return_value=mock_stats
        ) as mock_calc,
        patch("pyqwk.gui.render_stats_as_text") as mock_render_cli,
        patch("pyqwk.gui.tk.Toplevel") as mock_toplevel,
    ):
        # We need to mock the Text widget inside show_stats_window
        mock_win = MagicMock()
        mock_toplevel.return_value = mock_win
        mock_txt = MagicMock()

        with patch("pyqwk.gui.tk.Text", return_value=mock_txt):
            app.show_stats_window()

        mock_calc.assert_called_once()
        # Verify CLI renderer is NOT called
        mock_render_cli.assert_not_called()
        mock_toplevel.assert_called_once()

        # Verify structured insertion
        mock_txt.insert.assert_any_call(ANY, "Statistics for: test.qwk\n\n", "h1")
        mock_txt.insert.assert_any_call(ANY, "\nYearly Activity\n", "h2")
        mock_txt.insert.assert_any_call(ANY, "\nTop Authors\n", "h2")


def test_stats_window_no_path(app):
    """Test that show_stats_window shows a warning if no archive is open."""
    app.current_path = None

    with patch("pyqwk.gui.messagebox.showwarning") as mock_warning:
        app.show_stats_window()
        mock_warning.assert_called_once()
