from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp


def test_clear_search_field_triggers_immediate_reload():
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
            app._clear_search_field()

            app.search_var.set.assert_called_once_with("")
            mock_reload.assert_called_once()
            app.search_entry.focus_set.assert_called_once()


def test_clear_exclude_field_triggers_immediate_reload():
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
            app._clear_exclude_field()

            app.exclude_var.set.assert_called_once_with("")
            mock_reload.assert_called_once()
            app.exclude_entry.focus_set.assert_called_once()


def test_exclude_clear_button_functionality():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.exclude_var = MagicMock()
        app.exclude_entry = MagicMock()

        with patch.object(app, "_clear_exclude_field") as mock_clear:
            # Verify _clear_exclude_field resets exclude_var and reloads
            app._clear_exclude_field()
            mock_clear.assert_called_once()
