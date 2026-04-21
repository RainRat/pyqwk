import sys
from unittest.mock import MagicMock, patch
import pytest
import os

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
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.simpledialog"):

        # Ensure distinct mocks for each Variable call to avoid crosstalk
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        return app

def test_compute_stats_no_extension():
    """Test handling of attachments without extensions in statistics calculation (core.py line 4253)."""
    body = "Hello\nbegin 644 noextension\n!\nend\n"
    msg = ParsedMessage(body, 1, None, 1, MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, ""))

    stats = _compute_stats_from_messages(iter([msg]))

    top_types = {t["extension"]: t["count"] for t in stats["top_attachment_types"]}
    assert "(no extension)" in top_types
    assert top_types["(no extension)"] == 1

def test_is_any_filter_active_search(app):
    """Test _is_any_filter_active returns True when search is active (gui.py line 223)."""
    app.search_var.get.return_value = "query"
    assert app._is_any_filter_active() is True

def test_is_any_filter_active_conf(app):
    """Test _is_any_filter_active returns True when conference filter is active (gui.py line 231)."""
    app.search_var.get.return_value = ""
    with patch.object(app, "bbs_combo") as m_bbs, \
         patch.object(app, "conf_combo") as m_conf:
        m_bbs.get.return_value = "All BBSes"
        m_conf.get.return_value = "1: General"
        assert app._is_any_filter_active() is True

def test_is_any_filter_active_bool_vars(app):
    """Test _is_any_filter_active returns True when a boolean filter is active (gui.py line 243)."""
    app.search_var.get.return_value = ""
    with patch.object(app, "bbs_combo") as m_bbs, \
         patch.object(app, "conf_combo") as m_conf:
        m_bbs.get.return_value = "All BBSes"
        m_conf.get.return_value = "All Conferences"

        # Test each boolean variable
        for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                    app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
            # Reset all
            for v in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                        app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
                v.get.return_value = False

            var.get.return_value = True
            assert app._is_any_filter_active() is True

def test_show_stats_attachment_charts_and_callback(app):
    """Test rendering of attachment charts and their search pivot callbacks (gui.py lines 1846-1848, 1892, 1895)."""
    stats = {
        "file": "Test",
        "total_messages": 1,
        "matching_messages": 1,
        "attachments_count": 1,
        "dates": {"earliest": "2024-01-01T12:00:00", "latest": "2024-01-01T12:00:00"},
        "private_count": 0,
        "reply_count": 0,
        "reply_rate": 0.0,
        "avg_message_length": 10.0,
        "year_distribution": {},
        "month_distribution": {},
        "authors": [],
        "recipients": [],
        "conferences": [],
        "subjects": [],
        "keywords": [],
        "day_of_week": {},
        "hour_of_day": {},
        "top_attachments": [{"name": "file.txt", "count": 1}],
        "top_attachment_types": [{"extension": ".txt", "count": 1}]
    }

    with patch("pyqwk.gui.tk.Toplevel") as mock_top, \
         patch("pyqwk.gui.tk.Text") as mock_text, \
         patch.object(app, "reload_messages") as mock_reload:

        # We need the inner callback to be triggered
        # The render_gui_bar_chart function is nested in show_stats

        # To test the callback, we can't easily reach it because it's local.
        # But we can verify show_stats calls tag_bind with the expected callback logic.

        # We'll mock the tag_bind to capture the callback
        captured_callbacks = {}
        def mock_tag_bind(tag, event, cb):
            captured_callbacks[tag] = cb

        mock_text_inst = mock_text.return_value
        mock_text_inst.tag_bind.side_effect = mock_tag_bind

        # We need to mock calculate_archive_stats as it's called inside show_stats_window
        with patch("pyqwk.gui.calculate_archive_stats", return_value=stats):
            app.current_paths = ["test.qwk"]
            app.show_stats_window()

        # Check that tag_bind was called for the attachment
        # The tag is f"filter_search_{title_hash}_{i}"
        # We don't know the hash easily, but we can look through captured_callbacks

        search_callback = None
        for tag, cb in captured_callbacks.items():
            if tag.startswith("filter_search_"):
                search_callback = cb
                break

        assert search_callback is not None

        # Execute the callback
        search_callback(MagicMock())

        # Verify it set the search_var and reloaded messages
        app.search_var.set.assert_called_with("file.txt")
        mock_reload.assert_called_once()

        # Also verify Top Attachment Types was rendered (line 1895)
        # This is harder to verify precisely without checking text content,
        # but the fact that show_stats finished means it hit those lines.
        # We can check that insert was called with ".txt"

        found_ext = False
        for call in mock_text_inst.insert.call_args_list:
            if ".txt" in str(call):
                found_ext = True
                break
        assert found_ext
