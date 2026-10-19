from unittest.mock import MagicMock, patch
import pytest
from pyqwk.gui import QwkGuiApp


@pytest.fixture
def mock_gui_env():
    """Shared fixture for mocking GUI dependencies."""
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.font"),
    ):
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        # Tkinter constants
        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }


def test_clear_filter_field_search_resets_and_reloads(mock_gui_env):
    """Verify that _clear_filter_field clears search variable and focuses entry."""
    root = MagicMock()
    app = QwkGuiApp(root)

    app.search_var = MagicMock()
    app.search_entry = MagicMock()

    with patch.object(app, "reload_messages") as mock_reload:
        app._clear_filter_field("search_var", "search_entry")

        app.search_var.set.assert_called_once_with("")
        mock_reload.assert_called_once()
        app.search_entry.focus_set.assert_called_once()


def test_clear_filter_field_exclude_resets_and_reloads(mock_gui_env):
    """Verify that _clear_filter_field clears exclude variable and focuses entry."""
    root = MagicMock()
    app = QwkGuiApp(root)

    app.exclude_var = MagicMock()
    app.exclude_entry = MagicMock()

    with patch.object(app, "reload_messages") as mock_reload:
        app._clear_filter_field("exclude_var", "exclude_entry")

        app.exclude_var.set.assert_called_once_with("")
        mock_reload.assert_called_once()
        app.exclude_entry.focus_set.assert_called_once()


def test_reset_display_options_restores_defaults(mock_gui_env):
    """Verify reset_display_options correctly updates variables and invokes reloads."""
    root = MagicMock()
    app = QwkGuiApp(root)

    app.threaded_var.get.return_value = True
    app.clean_var.get.return_value = True
    app.wrap_var.get.return_value = False
    app.ansi_var.get.return_value = True
    app.redact_pii_var.get.return_value = True
    app.embed_attach_var.get.return_value = True

    with (
        patch.object(app, "reload_messages") as mock_reload,
        patch.object(app, "_update_wrap") as mock_update_wrap,
    ):
        app._reset_display_options()

        app.threaded_var.set.assert_called_with(False)
        app.clean_var.set.assert_called_with(False)
        app.wrap_var.set.assert_called_with(True)
        app.ansi_var.set.assert_called_with(False)
        app.redact_pii_var.set.assert_called_with(False)
        app.embed_attach_var.set.assert_called_with(False)

        mock_update_wrap.assert_called_once()
        mock_reload.assert_called_once()


def test_reset_word_limits_clears_min_max_and_reloads(mock_gui_env):
    """Verify _reset_word_limits clears min and max word variables and reloads."""
    root = MagicMock()
    app = QwkGuiApp(root)

    app.min_words_var = MagicMock()
    app.max_words_var = MagicMock()

    with patch.object(app, "reload_messages") as mock_reload:
        app._reset_word_limits()

        app.min_words_var.set.assert_called_once_with("")
        app.max_words_var.set.assert_called_once_with("")
        mock_reload.assert_called_once()


def test_clear_search_when_word_limit_entry_focused(mock_gui_env):
    """Verify clear_search resets word limits when word limit entry field has focus."""
    root = MagicMock()
    app = QwkGuiApp(root)

    app.min_words_entry = MagicMock()
    app.max_words_entry = MagicMock()
    app.min_words_var = MagicMock()
    app.max_words_var = MagicMock()
    app.min_words_var.get.return_value = "10"
    app.max_words_var.get.return_value = ""

    root.focus_get.return_value = app.min_words_entry

    with patch.object(app, "reload_messages") as mock_reload:
        app.clear_search()

        app.min_words_var.set.assert_called_with("")
        app.max_words_var.set.assert_called_with("")
        mock_reload.assert_called_once()
