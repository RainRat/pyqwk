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

def test_stats_window_interactivity(app):
    app.current_paths = ["test.qwk"]
    full_stats = {
        'file': 'test.qwk',
        'matching_messages': 1,
        'total_messages': 1,
        'attachments_count': 0,
        'dates': {'earliest': None, 'latest': None},
        'private_count': 0,
        'reply_rate': 0.0,
        'reply_count': 0,
        'avg_message_length': 0.0,
        'year_distribution': {},
        'month_distribution': {},
        'authors': [{'name': 'Target Author', 'count': 1}],
        'recipients': [{'name': 'Target Recipient', 'count': 1}],
        'bbses': [{'name': 'Target BBS', 'count': 1}],
        'conferences': [{'number': 101, 'name': 'Target Conf', 'count': 1}],
        'subjects': [],
        'keywords': [],
        'links': [],
        'emails': [],
        'phones': [],
        'day_of_week': {},
        'hour_of_day': {}
    }

    with patch("pyqwk.gui.calculate_archive_stats", return_value=full_stats), \
         patch("pyqwk.gui.tk.Toplevel") as mock_toplevel_cls, \
         patch("pyqwk.gui.tk.Text") as mock_text_cls:

        mock_win = MagicMock()
        mock_toplevel_cls.return_value = mock_win
        mock_txt = MagicMock()
        mock_text_cls.return_value = mock_txt

        # Dictionary to store tag callbacks for <Button-1>
        tag_callbacks = {}
        def mock_tag_bind(tag, event, callback):
            if event == "<Button-1>":
                tag_callbacks[tag] = callback
        mock_txt.tag_bind.side_effect = mock_tag_bind

        app.show_stats_window()

        # Verify instructional tip was inserted
        inserted_texts = [call.args[1] for call in mock_txt.insert.call_args_list if len(call.args) > 1]
        assert any("Tip: Click on Authors" in text for text in inserted_texts)

        # Find tags
        author_tags = [tag for tag in tag_callbacks if tag.startswith("filter_author")]
        bbs_tags = [tag for tag in tag_callbacks if tag.startswith("filter_bbs")]
        conf_tags = [tag for tag in tag_callbacks if tag.startswith("filter_conf")]

        # Top Authors and Top Recipients both use filter_type='author'
        assert len(author_tags) == 2
        assert len(bbs_tags) == 1
        assert len(conf_tags) == 1

        # Simulate click on Author
        with patch.object(app, "_pivot_filter") as mock_pivot:
            tag_callbacks[author_tags[0]](None)
            mock_pivot.assert_called_with(author='Target Author')
            mock_win.destroy.assert_called()

        # Simulate click on Recipient (also uses author filter)
        mock_win.destroy.reset_mock()
        with patch.object(app, "_pivot_filter") as mock_pivot:
            tag_callbacks[author_tags[1]](None)
            mock_pivot.assert_called_with(author='Target Recipient')
            mock_win.destroy.assert_called()

        # Simulate click on BBS
        mock_win.destroy.reset_mock()
        with patch.object(app, "_pivot_filter") as mock_pivot:
            tag_callbacks[bbs_tags[0]](None)
            mock_pivot.assert_called_with(bbs_name='Target BBS')
            mock_win.destroy.assert_called()

        # Simulate click on Conference
        mock_win.destroy.reset_mock()
        with patch.object(app, "_pivot_filter") as mock_pivot:
            tag_callbacks[conf_tags[0]](None)
            mock_pivot.assert_called_with(conf_num=101)
            mock_win.destroy.assert_called()
