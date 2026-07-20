from unittest.mock import MagicMock, patch
import pytest

def test_ui_filters_clear_button():
    mock_root = MagicMock()
    mock_root.after.return_value = "timer1"

    with patch('pyqwk.gui.tk') as mock_tk, \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'):

        # Mock BooleanVar to hold its own state so we can verify resets
        boolean_vars = {}
        def mock_boolean_var(value=False, **kwargs):
            m_var = MagicMock()
            m_var._val = value
            m_var.get.side_effect = lambda: m_var._val
            def set_val(v):
                m_var._val = v
            m_var.set.side_effect = set_val
            return m_var

        mock_tk.BooleanVar.side_effect = mock_boolean_var
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        # Capture button instances and their configurations
        button_commands = []
        def mock_button_init(master, **kwargs):
            btn = MagicMock()
            if 'command' in kwargs:
                button_commands.append(kwargs['command'])
            return btn
        mock_ttk.Button.side_effect = mock_button_init

        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        # Ensure the helper method is present
        assert hasattr(app, "_reset_visibility_filters")

        # Manually alter some variables to non-default states
        app.private_var.set(False)
        app.has_attach_var.set(True)
        app.mine_var.set(True)
        app.on_this_day_var.set(True)
        app.has_links_var.set(True)
        app.has_emails_var.set(True)
        app.has_phones_var.set(True)
        app.has_ansi_var.set(True)
        app.has_msg_links_var.set(True)

        # Run helper directly to see if it resets correctly
        with patch.object(app, "reload_messages") as mock_reload:
            app._reset_visibility_filters()

            # Defaults: private_var should be True, others False
            assert app.private_var.get() is True
            assert app.has_attach_var.get() is False
            assert app.mine_var.get() is False
            assert app.on_this_day_var.get() is False
            assert app.has_links_var.get() is False
            assert app.has_emails_var.get() is False
            assert app.has_phones_var.get() is False
            assert app.has_ansi_var.get() is False
            assert app.has_msg_links_var.get() is False

            mock_reload.assert_called_once()

        # Re-set variables to test via the button command
        app.private_var.set(False)
        app.has_attach_var.set(True)

        # Trigger the clear button command
        found_reset_btn = False
        for cmd in button_commands:
            if cmd == app._reset_visibility_filters:
                found_reset_btn = True
                with patch.object(app, "reload_messages") as mock_reload_2:
                    cmd()
                    assert app.private_var.get() is True
                    assert app.has_attach_var.get() is False
                    mock_reload_2.assert_called_once()
                break

        assert found_reset_btn, "Filters clear button command not found or not mapped to _reset_visibility_filters"
