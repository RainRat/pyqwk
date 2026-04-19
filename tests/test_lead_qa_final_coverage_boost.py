import sys
from unittest.mock import MagicMock, patch
import pytest
import hashlib

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader, _compute_stats_from_messages

@pytest.fixture
def app():
    root = MagicMock()
    with patch("pyqwk.gui.tk") as mock_tk,          patch("pyqwk.gui.ttk") as mock_ttk,          patch("pyqwk.gui.simpledialog"):

        # Ensure distinct mocks for each Variable call to avoid crosstalk
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        return app

def test_attachment_no_extension_stats():
    """Test _compute_stats_from_messages with an attachment lacking an extension (core.py:4253)."""
    h1 = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    # Message with an attachment that has no extension
    msg = ParsedMessage("Text", 1, None, 1, h1)
    msg.attachments = ["README", "LICENSE"] # Both have no extension

    stats = _compute_stats_from_messages(iter([msg]))

    ext_counts = {t["extension"]: t["count"] for t in stats["top_attachment_types"]}
    assert ext_counts["(no extension)"] == 2

def test_is_any_filter_active_search(app):
    """Test _is_any_filter_active returns True when search_var is set (gui.py:223)."""
    app.search_var.get.return_value = "query"
    assert app._is_any_filter_active() is True

def test_is_any_filter_active_conf(app):
    """Test _is_any_filter_active returns True when conf_combo is set (gui.py:231)."""
    app.search_var.get.return_value = ""
    with patch.object(app, "bbs_combo") as m_bbs,          patch.object(app, "conf_combo") as m_conf:
        m_bbs.get.return_value = "All BBSes"
        m_conf.get.return_value = "1 General"
        assert app._is_any_filter_active() is True

def test_is_any_filter_active_bool_vars(app):
    """Test _is_any_filter_active returns True when a boolean filter is set (gui.py:243)."""
    app.search_var.get.return_value = ""
    with patch.object(app, "bbs_combo") as m_bbs,          patch.object(app, "conf_combo") as m_conf:
        m_bbs.get.return_value = "All BBSes"
        m_conf.get.return_value = "All Conferences"

        # Test each boolean variable
        for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                    app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
            var.get.return_value = True
            assert app._is_any_filter_active() is True
            var.get.return_value = False

def test_stats_window_search_pivot_and_attachment_types(app):
    """Test search pivot and attachment types rendering in stats window (gui.py:1846-1848, 1892, 1895)."""
    app.current_paths = ["test.qwk"]
    stats = {
        'file': 'test.qwk', 'matching_messages': 1, 'total_messages': 1,
        'attachments_count': 1, 'dates': {'earliest': None, 'latest': None},
        'private_count': 0, 'reply_rate': 0.0, 'reply_count': 0, 'avg_message_length': 0.0,
        'year_distribution': {}, 'month_distribution': {}, 'authors': [], 'recipients': [],
        'bbses': [], 'conferences': [], 'subjects': [], 'keywords': [], 'links': [], 'emails': [], 'phones': [],
        'day_of_week': {}, 'hour_of_day': {},
        'top_attachments': [{'name': 'file.txt', 'count': 1}],
        'top_attachment_types': [{'extension': '.txt', 'count': 1}]
    }

    with patch("pyqwk.gui.calculate_archive_stats", return_value=stats),          patch("pyqwk.gui.tk.Toplevel") as mock_toplevel_cls,          patch("pyqwk.gui.tk.Text") as mock_text_cls:

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

        # Check search pivot for attachments
        title_hash = hashlib.md5("Top Attachments".encode()).hexdigest()[:8]
        search_tags = [tag for tag in tag_callbacks if tag.startswith(f"filter_search_{title_hash}")]
        assert len(search_tags) == 1

        with patch.object(app, "reload_messages") as mock_reload:
            tag_callbacks[search_tags[0]](None)
            app.search_var.set.assert_called_with("file.txt")
            mock_reload.assert_called_once()
            mock_win.destroy.assert_called()

        # Verify Top Attachment Types was rendered
        # Use find_calls to be more robust
        all_inserts = []
        for call in mock_txt.insert.call_args_list:
            # call is ((index, content, tag), {})
            if len(call[0]) >= 2:
                all_inserts.append(str(call[0][1]))

        assert any("Top Attachment Types" in text for text in all_inserts)
