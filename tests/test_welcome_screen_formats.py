from unittest.mock import MagicMock, patch
import tkinter as tk

def test_welcome_screen_supported_formats():
    """Verify that the welcome screen lists all supported formats accurately."""
    mock_root = MagicMock()

    with patch("pyqwk.gui.tk") as patched_tk, \
         patch("pyqwk.gui.ttk"), \
         patch("pyqwk.gui.font"):

        from pyqwk.gui import QwkGuiApp

        # Setup the Text mock
        mock_detail_text = MagicMock()
        patched_tk.Text.return_value = mock_detail_text

        # Also need to mock BooleanVar and StringVar since they are used in __init__
        patched_tk.BooleanVar.return_value = MagicMock()
        patched_tk.StringVar.return_value = MagicMock()
        patched_tk.END = tk.END

        # Create instance
        app = QwkGuiApp(mock_root)
        app._render_welcome_screen()

        # Gather all inserted text
        inserted_text = ""
        for call in mock_detail_text.insert.call_args_list:
            args, _ = call
            if len(args) >= 2:
                inserted_text += str(args[1])

        # Check for new formats
        assert "RSS" in inserted_text
        assert "TAR" in inserted_text
        assert "ZIP" in inserted_text
        assert "HTML" in inserted_text
        assert "Plain Text" in inserted_text
        assert "REPLY.DAT" in inserted_text
        assert "MESSAGES.DAT" in inserted_text
