import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader


@pytest.fixture
def app():
    root = MagicMock()
    root.title.return_value = "pyqwk - Graphical Reader"
    with (
        patch("pyqwk.gui.tk") as m_tk,
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.simpledialog"),
    ):
        m_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        m_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        m_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        # Define constants used in _navigate_search_matches
        m_tk.END = "end"

        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        app.detail_text = MagicMock()
        app.status_label = MagicMock()
        app.search_count_label = MagicMock()
        app.search_var.get.return_value = "test"
        return app


def test_render_message_with_pending_match(app):
    """Test that _render_message respects _pending_match_idx."""
    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    app.messages = [ParsedMessage("test test", 1, None, 1, header)]

    # Mock search to find two matches
    mock_count_var = MagicMock()
    mock_count_var.get.return_value = 4
    with patch("pyqwk.gui.tk.IntVar", return_value=mock_count_var):

        def mock_search(pattern, start, **kwargs):
            if start == "1.0":
                return "1.10"
            if start == "1.10+4c":
                return "1.20"
            return None

        app.detail_text.search.side_effect = mock_search
        app.detail_text.tag_ranges.return_value = []

        # Use -1 to land on the last match
        app._pending_match_idx = -1
        app._render_message(0)

        assert len(app._search_matches) == 2
        assert app._current_match_idx == 1
        assert app._pending_match_idx is None
        # 2nd match is at 1.20
        app.detail_text.see.assert_called_with("1.20")


def test_navigate_across_messages(app):
    """Test that _navigate_search_matches moves to the next message."""
    app._search_matches = [("1.0", "1.5")]
    app._current_match_idx = 0
    app._select_relative_message = MagicMock(return_value=True)

    # Move forward from the last match
    app._navigate_search_matches(1)

    app._select_relative_message.assert_called_with(1, force=True)
    assert app._pending_match_idx == 0


def test_navigate_across_messages_backward(app):
    """Test that _navigate_search_matches moves to the previous message."""
    app._search_matches = [("1.0", "1.5")]
    app._current_match_idx = 0
    app._select_relative_message = MagicMock(return_value=True)

    # Move backward from the first match
    app._navigate_search_matches(-1)

    app._select_relative_message.assert_called_with(-1, force=True)
    assert app._pending_match_idx == -1


def test_navigate_wrap_around_single_message(app):
    """Test that _navigate_search_matches wraps around in a single-message archive."""
    app._search_matches = [("1.0", "1.5"), ("2.0", "2.5")]
    app._current_match_idx = 1  # On last match
    app._select_relative_message = MagicMock(return_value=False)
    app._get_all_tree_items = MagicMock(return_value=["0"])
    app.message_list.selection.return_value = ("0",)

    with patch.object(app, "_render_message") as mock_render:
        # Mock _render_message to actually reset _pending_match_idx as the real one would
        def side_effect(idx):
            app._pending_match_idx = None

        mock_render.side_effect = side_effect

        # Move forward from the last match
        app._navigate_search_matches(1)

        # Should manually trigger render for same-message wrap
        mock_render.assert_called_with(0)
        assert app._pending_match_idx is None
