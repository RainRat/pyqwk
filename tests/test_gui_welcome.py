from unittest.mock import MagicMock, patch

# Ensure we have the mocks ready
mock_tk = MagicMock()
mock_ttk = MagicMock()

# Pre-setup some return values for things called in __init__
mock_tk.BooleanVar.return_value = MagicMock()
mock_tk.StringVar.return_value = MagicMock()


def test_welcome_screen_on_startup():
    """Verify that the welcome screen is rendered when no archive is provided."""
    mock_root = MagicMock()

    # We need to ensure pyqwk.gui is imported. If it was already imported,
    # we patch its internal 'tk' and 'ttk' references.
    with (
        patch("pyqwk.gui.tk") as patched_tk,
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.font") as patched_font,
        patch("pyqwk.gui.messagebox") as _,
        patch("pyqwk.gui.filedialog") as _,
        patch("pyqwk.gui.simpledialog") as _,
    ):
        # Now we can import it (it might already be in sys.modules)
        from pyqwk.gui import QwkGuiApp

        # Setup the Text mock
        mock_detail_text = MagicMock()
        patched_tk.Text.return_value = mock_detail_text

        # Also need to mock BooleanVar and StringVar since they are used in __init__
        patched_tk.BooleanVar.return_value = MagicMock()
        patched_tk.StringVar.return_value = MagicMock()

        # Create instance
        app = QwkGuiApp(mock_root)

        # Manually trigger the welcome screen call if needed,
        # but it should be called via root.after(100, self._render_welcome_screen)
        # In a unit test without a mainloop, we just call it directly to verify its logic.
        app._render_welcome_screen()

        # Check that welcome text was inserted
        found_welcome = False
        for call in mock_detail_text.insert.call_args_list:
            args, _ = call
            if len(args) > 1 and "Welcome to PyQWK" in str(args[1]):
                found_welcome = True
                break

        assert found_welcome, "Welcome screen text was not inserted into detail_text"


def test_no_welcome_screen_with_path():
    """Verify that current_path is set when an initial path is provided."""
    mock_root = MagicMock()
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.font"),
        patch("pyqwk.gui.load_data"),
    ):
        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root, initial_paths=["test.qwk"])
        assert app.current_path == "test.qwk"
