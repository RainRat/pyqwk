from unittest.mock import MagicMock, patch
from pyqwk.gui import QwkGuiApp


def test_copy_to_clipboard_status_feedback():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.status_label = MagicMock()

        # Test with label parameter and timer scheduling
        app._copy_to_clipboard("Sample Text", label="Subject")
        app.status_label.config.assert_called_with(text="Copied Subject to clipboard")
        app.root.after.assert_called_with(3000, app._restore_status_bar)

        # Test without label parameter
        app._copy_to_clipboard("Sample Text")
        app.status_label.config.assert_called_with(text="Copied text to clipboard")

        # Test timer cancellation on sequential copies
        timer_id = "timer123"
        app._status_timer = timer_id
        app._copy_to_clipboard("Another Text")
        app.root.after_cancel.assert_called_with(timer_id)

        # Test status restoration
        app._update_status_bar = MagicMock()
        app.message_list = MagicMock()
        app.message_list.selection.return_value = ("0",)
        app._restore_status_bar()
        assert app._status_timer is None
        app._update_status_bar.assert_called_once_with(0)


def test_copy_to_clipboard_after_cancel_exception():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)
        app.status_label = MagicMock()

        app._status_timer = "invalid_timer"
        app.root.after_cancel.side_effect = Exception("Invalid timer")
        app._copy_to_clipboard("Sample Text")
        assert app._status_timer is not None


def test_restore_status_bar_invalid_selection_index():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app._update_status_bar = MagicMock()
        app.message_list = MagicMock()
        app.message_list.selection.return_value = ("not_an_int",)
        app._restore_status_bar()
        app._update_status_bar.assert_called_once_with(None)


def test_show_status_message_schedules_restoration():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        app = QwkGuiApp(root)

        app.status_label = MagicMock()

        app._show_status_message("Test Status Message", timeout_ms=3000)
        app.status_label.config.assert_called_with(text="Test Status Message")
        app.root.after.assert_called_with(3000, app._restore_status_bar)

        # Verify go_back when empty history calls _show_status_message
        app._history_stack = []
        app.go_back()
        app.status_label.config.assert_called_with(text="No previous message in history")
