import pytest
from unittest.mock import MagicMock, patch, ANY
import sys

# Mock tkinter before any pyqwk.gui imports to avoid TclError/Display issues
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
         patch("tkinter.IntVar", return_value=MagicMock()), \
         patch("tkinter.ttk.Treeview", return_value=MagicMock()) as mock_tree, \
         patch("tkinter.Text", return_value=MagicMock()) as mock_text, \
         patch("tkinter.ttk.Combobox") as mock_combo:

        a = QwkGuiApp(root)
        a.message_list = mock_tree.return_value
        a.detail_text = mock_text.return_value
        a.bbs_combo = mock_combo.return_value
        a.conf_combo = mock_combo.return_value

        # Mock reload_messages to avoid real file operations in tests
        a.reload_messages = MagicMock()

        return a

def test_stats_window_full_interactivity(app):
    app.current_paths = ["test.qwk"]
    full_stats = {
        'file': 'test.qwk',
        'matching_messages': 1,
        'total_messages': 1,
        'attachments_count': 1,
        'dates': {'earliest': '2023-01-01T00:00:00', 'latest': '2023-01-01T00:00:00'},
        'private_count': 0,
        'reply_rate': 0.0,
        'reply_count': 0,
        'avg_message_length': 100.0,
        'year_distribution': {'2023': 1},
        'month_distribution': {'2023-01': 1},
        'authors': [{'name': 'Author A', 'count': 1}],
        'recipients': [{'name': 'To B', 'count': 1}],
        'bbses': [{'name': 'BBS X', 'count': 1}],
        'conferences': [{'number': 1, 'name': 'General', 'count': 1}],
        'subjects': [{'subject': 'Subject S', 'count': 1}],
        'keywords': [{'word': 'Keyword K', 'count': 1}],
        'links': [{'url': 'http://link.com', 'count': 1}],
        'emails': [{'email': 'a@b.com', 'count': 1}],
        'phones': [{'phone': '123-456', 'count': 1}],
        'top_attachments': [{'name': 'file.txt', 'count': 1}],
        'top_attachment_types': [{'extension': '.txt', 'count': 1}],
        'day_of_week': {'Monday': 1},
        'hour_of_day': {'12': 1}
    }

    with patch("pyqwk.gui.calculate_archive_stats", return_value=full_stats), \
         patch("pyqwk.gui.tk.Toplevel") as mock_toplevel_cls, \
         patch("pyqwk.gui.tk.Text") as mock_text_cls:

        mock_win = MagicMock()
        mock_toplevel_cls.return_value = mock_win
        mock_txt = MagicMock()
        mock_text_cls.return_value = mock_txt

        tag_callbacks = {}
        def mock_tag_bind(tag, event, callback):
            if event == "<Button-1>":
                tag_callbacks[tag] = callback
        mock_txt.tag_bind.side_effect = mock_tag_bind

        app.show_stats_window()

        # Verify Escape key binding
        mock_win.bind.assert_any_call("<Escape>", ANY)

        # Verify new Tip text
        inserted_texts = [call.args[1] for call in mock_txt.insert.call_args_list if len(call.args) > 1]
        assert any("Tip: Click on any chart label" in text for text in inserted_texts)

        # Helper to find tag for a value
        def get_tag_for_value(value):
            padded_val = f"{value[:25]:<25}"
            for call in mock_txt.insert.call_args_list:
                if padded_val in str(call.args):
                    tags = call.args[2] if len(call.args) > 2 else []
                    if isinstance(tags, tuple):
                        for t in tags:
                            if t.startswith("filter_"):
                                return t
            return None

        # Test various interactive labels
        interactive_values = [
            'Subject S', 'Keyword K', 'http://link.com', 'a@b.com', '123-456', 'file.txt', '.txt'
        ]

        for val in interactive_values:
            tag = get_tag_for_value(val)
            assert tag is not None, f"Tag not found for {val}"
            assert tag in tag_callbacks, f"Callback not found for {val} (tag {tag})"

            # Reset and trigger callback
            app.search_var.set.reset_mock()
            tag_callbacks[tag](None)

            # Check if search_var was set to the value
            app.search_var.set.assert_called_once_with(val)
            # Check if reload_messages was called
            app.reload_messages.assert_called()
