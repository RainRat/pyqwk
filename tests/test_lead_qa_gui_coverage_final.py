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
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.simpledialog"),
    ):
        # Ensure distinct mocks for each Variable call to avoid crosstalk
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        return app


def test_is_any_filter_active_private_false(app):
    """Test _is_any_filter_active returns True when private_var is False (line 246)."""
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""
    for var in [
        app.has_attach_var,
        app.mine_var,
        app.on_this_day_var,
        app.has_links_var,
        app.has_emails_var,
        app.has_phones_var,
        app.has_ansi_var,
    ]:
        var.get.return_value = False
    app.private_var.get.return_value = False

    with (
        patch.object(app, "bbs_combo") as m_bbs,
        patch.object(app, "conf_combo") as m_conf,
    ):
        m_bbs.get.return_value = "All BBSes"
        m_conf.get.return_value = "All Conferences"
        assert app._is_any_filter_active() is True


def test_is_any_filter_active_none(app):
    """Test _is_any_filter_active returns False when no filters are active."""
    app.search_var.get.return_value = ""
    app.exclude_var.get.return_value = ""
    for var in [
        app.has_attach_var,
        app.mine_var,
        app.on_this_day_var,
        app.has_links_var,
        app.has_emails_var,
        app.has_phones_var,
        app.has_ansi_var,
    ]:
        var.get.return_value = False
    app.private_var.get.return_value = True

    with (
        patch.object(app, "bbs_combo") as m_bbs,
        patch.object(app, "conf_combo") as m_conf,
    ):
        m_bbs.get.return_value = "All BBSes"
        m_conf.get.return_value = "All Conferences"
        assert app._is_any_filter_active() is False


def test_jump_to_message_found_after_reset(app):
    """Test jump_to_message finds message after filter reset (lines 1744-1745)."""
    h1 = MessageHeader(
        " ",
        101,
        "01-01-23",
        "12:00",
        "To1",
        "From1",
        "Subj1",
        "",
        None,
        1,
        " ",
        1,
        1,
        "",
    )
    app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]

    # Mock filters active
    with (
        patch.object(app, "_is_any_filter_active", return_value=True),
        patch("pyqwk.gui.messagebox.askyesno", return_value=True),
        patch.object(app, "clear_filters") as mock_clear,
        patch.object(app, "_find_message_index", side_effect=[None, 0]),
        patch.object(app, "_select_by_index") as mock_select,
    ):
        app.jump_to_message(1, 101)

        mock_clear.assert_called_once()
        mock_select.assert_called_with(0)


def test_prompt_jump_to_message_found_after_reset(app):
    """Test prompt_jump_to_message finds message after filter reset (lines 1713-1714)."""
    h1 = MessageHeader(
        " ",
        101,
        "01-01-23",
        "12:00",
        "To1",
        "From1",
        "Subj1",
        "",
        None,
        1,
        " ",
        1,
        1,
        "",
    )
    app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]

    # Mock filters active
    with (
        patch.object(app, "_is_any_filter_active", return_value=True),
        patch("pyqwk.gui.messagebox.askyesno", return_value=True),
        patch("pyqwk.gui.simpledialog.askinteger", return_value=101),
        patch.object(app, "clear_filters") as mock_clear,
        patch.object(app, "_find_message_index", side_effect=[None, 0]),
        patch.object(app, "_select_by_index") as mock_select,
    ):
        app.prompt_jump_to_message()

        mock_clear.assert_called_once()
        mock_select.assert_called_with(0)


def test_jump_to_message_not_found_decline_reset(app):
    """Test jump_to_message shows Not Found when user declines reset."""
    with (
        patch.object(app, "_is_any_filter_active", return_value=True),
        patch("pyqwk.gui.messagebox.askyesno", return_value=False),
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        app.jump_to_message(1, 999)
        mock_info.assert_called_once()


def test_prompt_jump_to_message_not_found_decline_reset(app):
    """Test prompt_jump_to_message shows Not Found when user declines reset."""
    h1 = MessageHeader(
        " ",
        101,
        "01-01-23",
        "12:00",
        "To1",
        "From1",
        "Subj1",
        "",
        None,
        1,
        " ",
        1,
        1,
        "",
    )
    app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]

    with (
        patch.object(app, "_is_any_filter_active", return_value=True),
        patch("pyqwk.gui.messagebox.askyesno", return_value=False),
        patch("pyqwk.gui.simpledialog.askinteger", return_value=999),
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        app.prompt_jump_to_message()
        mock_info.assert_called_once()


def test_jump_to_message_not_found_no_filters(app):
    """Test jump_to_message shows Not Found when no filters are active."""
    with (
        patch.object(app, "_is_any_filter_active", return_value=False),
        patch("pyqwk.gui.messagebox.showinfo") as mock_info,
    ):
        app.jump_to_message(1, 999)
        mock_info.assert_called_once()
