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
