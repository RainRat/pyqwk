import sys
import pytest
from unittest.mock import MagicMock, patch
import runpy

# Mock tkinter before any pyqwk.gui imports to avoid Tcl/Tk errors in headless environment
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.simpledialog"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import extract_binaries, ProcessingSettings, show_stats
from pyqwk.gui import QwkGuiApp

def test_yenc_decoding_exception():
    """Trigger Exception block in yEnc decoding (core.py:259-260)."""
    text = "=ybegin line=128 size=10 name=test.bin\n=ypart begin=1 end=10\nABC\n=yend"
    # We patch ord to raise an exception during the yEnc loop
    with patch("pyqwk.core.ord", side_effect=RuntimeError("Mocked Error")):
        binaries = extract_binaries(text)
        assert len(binaries) == 0

def test_show_stats_merged_error():
    """Trigger error handling in show_stats (core.py:3542-3543)."""
    # Create a minimal ProcessingSettings instance
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='auto', output_mode='stdout',
        output_path=None, encoding='cp437', merge_stats=True
    )

    logger = MagicMock()
    # FileNotFoundError is in PROCESSING_EXCEPTIONS
    with patch("pyqwk.core.calculate_archive_stats", side_effect=FileNotFoundError("Failed")):
        show_stats(["test.qwk"], settings, logger)
        logger.error.assert_called_with("Error calculating merged stats: Failed")

@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()
    return QwkGuiApp(root)

def test_gui_clear_filters_exception(app):
    """Trigger fallback in clear_filters (gui.py:231-232)."""
    app.conf_combo = MagicMock()
    app.conf_combo.current.side_effect = Exception("Failed")
    app.clear_filters()
    app.conf_combo.set.assert_called_with("All Conferences")

def test_gui_open_folder_no_selection(app):
    """Cover early return in open_folder when no folder selected (gui.py:589)."""
    # Use patch("pyqwk.gui.filedialog.askdirectory") because it's imported as 'from tkinter import filedialog'
    with patch("pyqwk.gui.filedialog.askdirectory", return_value=""), \
         patch("pyqwk.gui.expand_paths") as mock_expand:
        app.open_folder()
        mock_expand.assert_not_called()

def test_gui_open_folder_no_archives(app):
    """Cover no archives found in folder (gui.py:593-594)."""
    with patch("pyqwk.gui.filedialog.askdirectory", return_value="/tmp"), \
         patch("pyqwk.gui.expand_paths", return_value=[]), \
         patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.open_folder()
        mock_info.assert_called_once()

def test_gui_show_stats_with_conferences(app):
    """Exercise conference chart rendering in gui.py (1140-1141)."""
    app.current_path = "test.qwk"
    stats = {
        "file": "test.qwk",
        "total_messages": 1,
        "matching_messages": 1,
        "attachments_count": 0,
        "dates": {"earliest": "2023-01-01", "latest": "2023-01-01"},
        "authors": [],
        "recipients": [],
        "conferences": [{"number": 1, "name": "General", "count": 1}],
        "subjects": [],
        "keywords": [],
        "day_of_week": {},
        "hour_of_day": {},
        "year_distribution": {},
        "month_distribution": {},
        "private_count": 0,
        "reply_count": 0,
        "reply_rate": 0.0,
        "avg_message_length": 10.0
    }
    with patch("pyqwk.gui.calculate_archive_stats", return_value=stats), \
         patch("pyqwk.gui.tk.Toplevel"), \
         patch("pyqwk.gui.tk.Text"):
        app.show_stats_window()

def test_cli_main_block():
    """Cover if __name__ == '__main__': block in cli.py (556)."""
    with patch("sys.argv", ["qwk", "--version"]):
        with pytest.raises(SystemExit) as excinfo:
             runpy.run_path("pyqwk/cli.py", run_name="__main__")
        assert excinfo.value.code == 0

def test_gui_main_block():
    """Cover if __name__ == '__main__': block in gui.py (1278)."""
    with patch("pyqwk.gui.main") as mock_main:
        with patch("sys.argv", ["gui.py", "--help"]):
            with pytest.raises(SystemExit):
                 runpy.run_path("pyqwk/gui.py", run_name="__main__")
