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

        # Test with label parameter
        app._copy_to_clipboard("Sample Text", label="Subject")
        app.status_label.config.assert_called_with(text="Copied Subject to clipboard")

        # Test without label parameter
        app._copy_to_clipboard("Sample Text")
        app.status_label.config.assert_called_with(text="Copied text to clipboard")
