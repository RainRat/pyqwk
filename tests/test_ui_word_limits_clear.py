from unittest.mock import MagicMock, patch
import sys

def test_word_limits_clear_button():
    mock_root = MagicMock()
    # Ensure root.after doesn't fail
    mock_root.after.return_value = "timer1"

    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'):

        from pyqwk.gui import QwkGuiApp

        # Capture button commands
        button_commands = []
        def mock_button_init(master, **kwargs):
            btn = MagicMock()
            if 'command' in kwargs:
                button_commands.append(kwargs['command'])
            return btn
        mock_ttk.Button.side_effect = mock_button_init

        app = QwkGuiApp(mock_root)

        # Mock variables to track calls
        app.min_words_var = MagicMock()
        app.max_words_var = MagicMock()

        # Find the button that clears them
        found_clear_btn = False
        for cmd in button_commands:
            if callable(cmd):
                app.min_words_var.set.reset_mock()
                app.max_words_var.set.reset_mock()
                try:
                    cmd()
                    if app.min_words_var.set.called and app.max_words_var.set.called:
                        if app.min_words_var.set.call_args[0][0] == "" and \
                           app.max_words_var.set.call_args[0][0] == "":
                            found_clear_btn = True
                            break
                except Exception:
                    # Some buttons might fail when called in isolation with mocks
                    pass

        assert found_clear_btn, "Clear button (✕) for word limits not found or not working correctly"
