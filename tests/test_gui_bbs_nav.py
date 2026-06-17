from unittest.mock import MagicMock, patch
import sys

def test_navigate_bbs():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'):

        from pyqwk.gui import QwkGuiApp

        # Setup app
        app = QwkGuiApp(mock_root)

        # Configure mock BBS combo
        # We need to mock how __getitem__ works for "values"
        app.bbs_combo = MagicMock()
        values = ["BBS 1", "BBS 2", "BBS 3"]
        app.bbs_combo.__getitem__.side_effect = lambda key: values if key == "values" else None
        app.bbs_combo.current.return_value = 0

        # Mock reload_messages to avoid heavy lifting
        app.reload_messages = MagicMock()

        # Test navigation forward
        app._navigate_bbs(1)
        app.bbs_combo.current.assert_called_with(1)
        app.reload_messages.assert_called()

        # Test navigation backward (wrap around)
        app.bbs_combo.current.return_value = 0
        app._navigate_bbs(-1)
        app.bbs_combo.current.assert_called_with(2)

def test_bbs_navigation_buttons_present():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'):

        from pyqwk.gui import QwkGuiApp

        # We need to track the created buttons and their commands
        button_commands = []

        def mock_button_init(master, **kwargs):
            btn = MagicMock()
            if 'command' in kwargs:
                button_commands.append(kwargs['command'])
            return btn

        mock_ttk.Button.side_effect = mock_button_init

        app = QwkGuiApp(mock_root)

        # Verify that _navigate_bbs is being used in some of the buttons
        # We can mock _navigate_bbs and trigger the commands to see if it's called
        app._navigate_bbs = MagicMock()

        found_prev = False
        found_next = False

        for cmd in button_commands:
            if callable(cmd):
                # Reset mock for each call
                app._navigate_bbs.reset_mock()
                try:
                    cmd()
                    if app._navigate_bbs.called:
                        args = app._navigate_bbs.call_args[0]
                        if args == (-1,):
                            found_prev = True
                        elif args == (1,):
                            found_next = True
                except:
                    pass

        assert found_prev, "BBS Prev button not found or not linked to _navigate_bbs(-1)"
        assert found_next, "BBS Next button not found or not linked to _navigate_bbs(1)"

def test_welcome_screen_updated():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk') as mock_tk, \
         patch('pyqwk.gui.ttk'), \
         patch('pyqwk.gui.font'):

        from pyqwk.gui import QwkGuiApp

        mock_text = MagicMock()
        mock_tk.Text.return_value = mock_text

        app = QwkGuiApp(mock_root)
        app._render_welcome_screen()

        # Check if "{ / }" and "Prev / Next BBS" were inserted
        found_shortcut = False
        for call in mock_text.insert.call_args_list:
            args, _ = call
            if len(args) > 1:
                content = str(args[1])
                if "{ / }" in content or "Prev / Next BBS" in content:
                    found_shortcut = True
                    break

        assert found_shortcut
