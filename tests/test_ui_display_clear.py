from unittest.mock import MagicMock, patch
import pytest

# Ensure we mock dependencies or use existing patterns
def test_reset_display_options_with_mocks():
    """Verify reset_display_options correctly updates variables and invokes reloads."""
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
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

        from pyqwk.gui import QwkGuiApp
        root = MagicMock()
        app = QwkGuiApp(root)

        # Set non-default values on the mock variables
        app.threaded_var.get.return_value = True
        app.clean_var.get.return_value = True
        app.wrap_var.get.return_value = False
        app.ansi_var.get.return_value = True
        app.redact_pii_var.get.return_value = True
        app.embed_attach_var.get.return_value = True

        with patch.object(app, "reload_messages") as mock_reload, \
             patch.object(app, "_update_wrap") as mock_update_wrap:

            app._reset_display_options()

            # Verify variables set calls
            app.threaded_var.set.assert_called_with(False)
            app.clean_var.set.assert_called_with(False)
            app.wrap_var.set.assert_called_with(True)
            app.ansi_var.set.assert_called_with(False)
            app.redact_pii_var.set.assert_called_with(False)
            app.embed_attach_var.set.assert_called_with(False)

            mock_update_wrap.assert_called_once()
            mock_reload.assert_called_once()
