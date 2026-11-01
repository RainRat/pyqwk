from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp


def test_clear_filter_field_search_and_exclude():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.search_var = MagicMock()
        app.search_entry = MagicMock()
        app.exclude_var = MagicMock()
        app.exclude_entry = MagicMock()

        with patch.object(app, "reload_messages") as mock_reload:
            app._clear_filter_field("search_var", "search_entry")
            app.search_var.set.assert_called_once_with("")
            app.search_entry.focus_set.assert_called_once()

            app._clear_filter_field("exclude_var", "exclude_entry")
            app.exclude_var.set.assert_called_once_with("")
            app.exclude_entry.focus_set.assert_called_once()

            assert mock_reload.call_count == 2


def test_reset_word_limits_resets_vars_and_reloads():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.min_words_var = MagicMock()
        app.max_words_var = MagicMock()

        with patch.object(app, "reload_messages") as mock_reload:
            app._reset_word_limits()

            app.min_words_var.set.assert_called_once_with("")
            app.max_words_var.set.assert_called_once_with("")
            mock_reload.assert_called_once()


def test_clear_search_with_word_limits_focused():
    root = MagicMock()
    root.after.return_value = "timer1"

    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.font"),
    ):
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


def test_reset_display_options_resets_vars_and_updates_wrap():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

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
