import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter for GUI tests
if "tkinter" not in sys.modules:
    mock_tk = MagicMock()
    mock_tk.TclError = type("TclError", (Exception,), {})
    sys.modules["tkinter"] = mock_tk
    sys.modules["tkinter.filedialog"] = MagicMock()
    sys.modules["tkinter.messagebox"] = MagicMock()
    sys.modules["tkinter.simpledialog"] = MagicMock()
    sys.modules["tkinter.ttk"] = MagicMock()

from pyqwk.core import ParsedMessage, MessageHeader, _compute_stats_from_messages
from pyqwk.gui import QwkGuiApp

def test_stats_no_extension_attachment():
    """Test _compute_stats_from_messages with attachment having no extension (core.py:4253)."""
    h1 = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    # "EXTLESS" has no dot, so no extension
    m1 = ParsedMessage("Body", 1, None, 1, h1, attachments=["EXTLESS"])

    stats = _compute_stats_from_messages([m1])

    found = False
    for item in stats["top_attachment_types"]:
        if item["extension"] == "(no extension)":
            found = True
            assert item["count"] == 1
    assert found

@pytest.fixture
def app():
    root = MagicMock()
    # Ensure distinct mocks for each Variable call
    with patch("pyqwk.gui.tk.BooleanVar", side_effect=lambda **kwargs: MagicMock()), \
         patch("pyqwk.gui.tk.StringVar", side_effect=lambda **kwargs: MagicMock()), \
         patch("pyqwk.gui.tk.IntVar", side_effect=lambda **kwargs: MagicMock()):
        a = QwkGuiApp(root)
        a.bbs_combo = MagicMock()
        a.conf_combo = MagicMock()
        return a

def test_is_any_filter_active_search(app):
    """Test _is_any_filter_active returns True when search is active (gui.py:223)."""
    app.search_var.get.return_value = "query"
    assert app._is_any_filter_active() is True

def test_is_any_filter_active_conf(app):
    """Test _is_any_filter_active returns True when conference filter is active (gui.py:231)."""
    app.search_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "Some Conference"
    assert app._is_any_filter_active() is True

def test_is_any_filter_active_boolean_vars(app):
    """Test _is_any_filter_active returns True when a boolean filter is active (gui.py:243)."""
    app.search_var.get.return_value = ""
    app.bbs_combo.get.return_value = "All BBSes"
    app.conf_combo.get.return_value = "All Conferences"

    # Test each boolean var
    for var_name in ["has_attach_var", "mine_var", "on_this_day_var",
                    "has_links_var", "has_emails_var", "has_phones_var", "has_ansi_var"]:
        var = getattr(app, var_name)
        var.get.return_value = True
        assert app._is_any_filter_active() is True
        var.get.return_value = False

def test_stats_attachment_rendering_and_pivot(app):
    """Test rendering of attachment stats and pivot click (gui.py:1846-1848, 1892, 1895)."""
    app.current_paths = ["test.qwk"]
    stats = {
        'file': 'test.qwk',
        'matching_messages': 1,
        'total_messages': 1,
        'attachments_count': 1,
        'dates': {'earliest': None, 'latest': None},
        'private_count': 0,
        'reply_rate': 0.0,
        'reply_count': 0,
        'avg_message_length': 0.0,
        'year_distribution': {},
        'month_distribution': {},
        'authors': [],
        'recipients': [],
        'bbses': [],
        'conferences': [],
        'subjects': [],
        'keywords': [],
        'links': [],
        'emails': [],
        'phones': [],
        'top_attachments': [{'name': 'FILE.ZIP', 'count': 1}],
        'top_attachment_types': [{'extension': '.zip', 'count': 1}],
        'day_of_week': {},
        'hour_of_day': {}
    }

    with patch("pyqwk.gui.calculate_archive_stats", return_value=stats), \
         patch("pyqwk.gui.tk.Toplevel") as mock_top, \
         patch("pyqwk.gui.tk.Text") as mock_text_cls:

        mock_win = MagicMock()
        mock_top.return_value = mock_win
        mock_txt = MagicMock()
        mock_text_cls.return_value = mock_txt

        tag_callbacks = {}
        def mock_tag_bind(tag, event, callback):
            if event == "<Button-1>":
                tag_callbacks[tag] = callback
        mock_txt.tag_bind.side_effect = mock_tag_bind

        app.show_stats_window()

        # Verify Top Attachments and Top Attachment Types were rendered
        # We can look for tags starting with filter_search
        search_tags = [t for t in tag_callbacks if t.startswith("filter_search")]
        assert len(search_tags) >= 1

        # Test the pivot callback for search (lines 1846-1848)
        with patch.object(app, "reload_messages") as mock_reload:
            tag_callbacks[search_tags[0]](None)
            app.search_var.set.assert_called_with("FILE.ZIP")
            mock_reload.assert_called_once()
            mock_win.destroy.assert_called_once()
