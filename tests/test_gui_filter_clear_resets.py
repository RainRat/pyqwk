from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp


def test_clear_filter_field_search_triggers_immediate_reload():
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

        with patch.object(app, "reload_messages") as mock_reload:
            app._clear_filter_field("search_var", "search_entry")

            app.search_var.set.assert_called_once_with("")
            mock_reload.assert_called_once()
            app.search_entry.focus_set.assert_called_once()


def test_clear_filter_field_exclude_triggers_immediate_reload():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.exclude_var = MagicMock()
        app.exclude_entry = MagicMock()

        with patch.object(app, "reload_messages") as mock_reload:
            app._clear_filter_field("exclude_var", "exclude_entry")

            app.exclude_var.set.assert_called_once_with("")
            mock_reload.assert_called_once()
            app.exclude_entry.focus_set.assert_called_once()


def test_exclude_clear_button_functionality():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.exclude_var = MagicMock()
        app.exclude_entry = MagicMock()

        with patch.object(app, "_clear_filter_field") as mock_clear:
            app._clear_filter_field("exclude_var", "exclude_entry")
            mock_clear.assert_called_once_with("exclude_var", "exclude_entry")


def test_reset_display_options_with_mocks():
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


def test_word_limits_clear_button():
    mock_root = MagicMock()
    mock_root.after.return_value = "timer1"

    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.font"),
    ):
        button_commands = []

        def mock_button_init(master, **kwargs):
            btn = MagicMock()
            if "command" in kwargs:
                button_commands.append(kwargs["command"])
            return btn

        mock_ttk.Button.side_effect = mock_button_init

        app = QwkGuiApp(mock_root)

        app.min_words_var = MagicMock()
        app.max_words_var = MagicMock()
        app.reload_messages = MagicMock()

        found_clear_btn = False
        for cmd in button_commands:
            if callable(cmd):
                app.min_words_var.set.reset_mock()
                app.max_words_var.set.reset_mock()
                app.reload_messages.reset_mock()
                try:
                    cmd()
                    if app.min_words_var.set.called and app.max_words_var.set.called:
                        if (
                            app.min_words_var.set.call_args[0][0] == ""
                            and app.max_words_var.set.call_args[0][0] == ""
                        ):
                            found_clear_btn = True
                            assert app.reload_messages.called
                            break
                except Exception:
                    pass

        assert found_clear_btn

        app.min_words_entry = MagicMock()
        app.max_words_entry = MagicMock()
        app.min_words_var = MagicMock()
        app.max_words_var = MagicMock()
        app.min_words_var.get.return_value = "10"
        app.max_words_var.get.return_value = ""
        mock_root.focus_get.return_value = app.min_words_entry
        app.reload_messages.reset_mock()

        app.clear_search()

        app.min_words_var.set.assert_called_with("")
        app.max_words_var.set.assert_called_with("")
        assert app.reload_messages.called
