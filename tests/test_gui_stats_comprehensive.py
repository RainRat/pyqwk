import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
class MockTclError(Exception):
    pass

if "tkinter" in sys.modules:
    existing_tk = sys.modules["tkinter"]
    existing_tk.TclError = MockTclError
else:
    mock_tk = MagicMock()
    mock_tk.TclError = MockTclError
    sys.modules["tkinter"] = mock_tk

if "tkinter.ttk" not in sys.modules:
    sys.modules["tkinter.ttk"] = MagicMock()
if "tkinter.filedialog" not in sys.modules:
    sys.modules["tkinter.filedialog"] = MagicMock()
if "tkinter.messagebox" not in sys.modules:
    sys.modules["tkinter.messagebox"] = MagicMock()
if "tkinter.simpledialog" not in sys.modules:
    sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()

    with patch("tkinter.BooleanVar", return_value=MagicMock()), \
         patch("tkinter.StringVar", return_value=MagicMock()), \
         patch("tkinter.ttk.Treeview", return_value=MagicMock()) as mock_tree, \
         patch("tkinter.Text", return_value=MagicMock()) as mock_text, \
         patch("tkinter.ttk.Combobox") as mock_combo:

        a = QwkGuiApp(root)
        a.message_list = mock_tree.return_value
        a.detail_text = mock_text.return_value
        a.bbs_combo = mock_combo.return_value
        a.conf_combo = mock_combo.return_value

        return a

def test_show_stats_window_renders_all_entities_for_multiple_archives(app):
    app.current_paths = ["test1.qwk", "test2.qwk"]

    full_stats = {
        'file': 'Multiple Archives',
        'matching_messages': 10,
        'total_messages': 20,
        'attachments_count': 5,
        'dates': {'earliest': None, 'latest': None},
        'private_count': 2,
        'reply_rate': 20.0,
        'reply_count': 2,
        'avg_message_length': 150.0,
        'year_distribution': {'2023': 10},
        'month_distribution': {'2023-01': 10},
        'authors': [{'name': 'Author A', 'count': 5}],
        'recipients': [{'name': 'Recipient B', 'count': 5}],
        'bbses': [{'name': 'BBS X', 'count': 10}],
        'conferences': [{'number': 1, 'name': 'General', 'count': 10}],
        'subjects': [{'subject': 'Re: Test', 'count': 5}],
        'keywords': [{'word': 'qwk', 'count': 10}],
        'links': [{'url': 'http://example.com', 'count': 5}],
        'emails': [{'email': 'test@example.com', 'count': 3}],
        'phones': [{'phone': '555-1234', 'count': 2}],
        'day_of_week': {'Monday': 10},
        'hour_of_day': {'12': 10}
    }

    with patch("pyqwk.gui.calculate_archive_stats", return_value=full_stats), \
         patch("pyqwk.gui.tk.Toplevel") as mock_toplevel_cls, \
         patch("pyqwk.gui.tk.Text") as mock_text_cls:

        mock_win = MagicMock()
        mock_toplevel_cls.return_value = mock_win
        mock_txt = MagicMock()
        mock_text_cls.return_value = mock_txt

        app.show_stats_window()

        mock_win.title.assert_called_with("Statistics - 2 archives")

        rendered_text = []
        for call in mock_txt.insert.call_args_list:
            if isinstance(call.args[1], str):
                rendered_text.append(call.args[1])

        content = "".join(rendered_text)
        assert "Top Emails" in content
        assert "test@example.com" in content
        assert "Top Phone Numbers" in content
        assert "555-1234" in content
        assert "Top Links" in content
        assert "http://example.com" in content
        assert "Date Range" not in content

def test_show_stats_window_handles_calculation_errors(app):
    app.current_paths = ["test.qwk"]

    with patch("pyqwk.gui.calculate_archive_stats", side_effect=Exception("Stats error")), \
         patch("pyqwk.gui.messagebox.showerror") as mock_error:

        app.show_stats_window()
        mock_error.assert_called_with("Statistics Error", "Stats error")
        assert app.status_label.config.call_args_list[-1][1]['text'] == "Error calculating statistics"
