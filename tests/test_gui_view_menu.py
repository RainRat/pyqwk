import pytest
from unittest.mock import MagicMock, patch, ANY
import sys

# Define dummy entry classes to allow proper isinstance checks in tests
class DummyTkEntry:
    pass

class DummyTtkEntry:
    pass

# Mock tkinter before importing QwkGuiApp
mock_tk = MagicMock()
mock_tk.Entry = DummyTkEntry

mock_ttk = MagicMock()
mock_ttk.Entry = DummyTtkEntry

sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['tkinter.ttk'] = mock_ttk
sys.modules['tkinter.simpledialog'] = MagicMock()

import tkinter as tk
from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    # Mocking necessary attributes for initialization
    with patch('pyqwk.gui.ttk.Style'), \
         patch('pyqwk.gui.QwkGuiApp._render_welcome_screen'), \
         patch('pyqwk.gui.QwkGuiApp._build_menu'), \
         patch('pyqwk.gui.QwkGuiApp._build_toolbar'), \
         patch('pyqwk.gui.QwkGuiApp._build_status_bar'), \
         patch('pyqwk.gui.QwkGuiApp._build_layout'):
        app = QwkGuiApp(root)
        app.search_entry = MagicMock()
        app.exclude_entry = MagicMock()
        app.min_words_entry = MagicMock()
        app.max_words_entry = MagicMock()
        app.message_list = MagicMock()
        app.detail_text = MagicMock()
        app.detail_h_scrollbar = MagicMock()

        # Initialize display vars
        app.threaded_var = MagicMock()
        app.clean_var = MagicMock()
        app.wrap_var = MagicMock()
        app.ansi_var = MagicMock()
        app.redact_pii_var = MagicMock()
        app.embed_attach_var = MagicMock()
        return app

def test_view_menu_construction(app):
    # Test that we can call _build_menu with actual (unmocked) logic
    # We will mock the tk.Menu calls to verify how the View menu is built
    menubar_mock = MagicMock()
    file_menu_mock = MagicMock()
    edit_menu_mock = MagicMock()
    view_menu_mock = MagicMock()

    # Configure tk.Menu side effects to return our mocks sequentially
    def menu_side_effect(*args, **kwargs):
        if not hasattr(menu_side_effect, "count"):
            menu_side_effect.count = 0
        menu_side_effect.count += 1
        if menu_side_effect.count == 1:
            return menubar_mock
        elif menu_side_effect.count == 2:
            return file_menu_mock
        elif menu_side_effect.count == 3:
            return edit_menu_mock
        else:
            return view_menu_mock

    with patch('pyqwk.gui.tk.Menu', side_effect=menu_side_effect):
        app._build_menu()

        # Verify cascades are added with underline=0
        menubar_mock.add_cascade.assert_any_call(label="File", menu=file_menu_mock, underline=0)
        menubar_mock.add_cascade.assert_any_call(label="Edit", menu=edit_menu_mock, underline=0)
        menubar_mock.add_cascade.assert_any_call(label="View", menu=view_menu_mock, underline=0)

        # Verify view_menu_mock checkbutton entries
        view_menu_mock.add_checkbutton.assert_any_call(
            label="Conversations",
            variable=app.threaded_var,
            command=app.reload_messages,
            accelerator="Ctrl+T / T",
        )
        view_menu_mock.add_checkbutton.assert_any_call(
            label="Clean View",
            variable=app.clean_var,
            command=app.reload_messages,
            accelerator="C",
        )
        view_menu_mock.add_checkbutton.assert_any_call(
            label="Wrap Text",
            variable=app.wrap_var,
            command=app._update_wrap,
            accelerator="Ctrl+W / W",
        )
        view_menu_mock.add_checkbutton.assert_any_call(
            label="Remove Colors",
            variable=app.ansi_var,
            command=app.reload_messages,
        )

def test_is_focus_in_entry(app):
    # Scenario 1: Focus is in search entry
    app.root.focus_get.return_value = app.search_entry
    assert app._is_focus_in_entry() is True

    # Scenario 2: Focus is in exclude entry
    app.root.focus_get.return_value = app.exclude_entry
    assert app._is_focus_in_entry() is True

    # Scenario 3: Focus is in min words entry
    app.root.focus_get.return_value = app.min_words_entry
    assert app._is_focus_in_entry() is True

    # Scenario 4: Focus is in max words entry
    app.root.focus_get.return_value = app.max_words_entry
    assert app._is_focus_in_entry() is True

    # Scenario 5: Focus is on an arbitrary Entry class instance
    with patch('pyqwk.gui.tk.Entry', DummyTkEntry), patch('pyqwk.gui.ttk.Entry', DummyTtkEntry):
        fake_entry = DummyTkEntry()
        app.root.focus_get.return_value = fake_entry
        assert app._is_focus_in_entry() is True

    # Scenario 6: Focus is on message list
    app.root.focus_get.return_value = app.message_list
    assert app._is_focus_in_entry() is False

def test_toggle_methods_when_not_focused_in_entry(app):
    app._is_focus_in_entry = MagicMock(return_value=False)

    # 1. Test _toggle_wrap
    app.wrap_var.get.return_value = True
    app._toggle_wrap()
    app.wrap_var.set.assert_called_with(False)

    # 2. Test _toggle_conversations
    app.threaded_var.get.return_value = False
    with patch.object(app, 'reload_messages') as mock_reload:
        app._toggle_conversations()
        app.threaded_var.set.assert_called_with(True)
        mock_reload.assert_called_once()

    # 3. Test _toggle_clean_view
    app.clean_var.get.return_value = True
    with patch.object(app, 'reload_messages') as mock_reload:
        app._toggle_clean_view()
        app.clean_var.set.assert_called_with(False)
        mock_reload.assert_called_once()

def test_toggle_methods_prevented_when_focused_in_entry(app):
    app._is_focus_in_entry = MagicMock(return_value=True)

    # Reset mocks
    app.wrap_var.set.reset_mock()
    app.threaded_var.set.reset_mock()
    app.clean_var.set.reset_mock()

    # Run toggles
    app._toggle_wrap()
    app._toggle_conversations()
    app._toggle_clean_view()

    # Confirm no changes were made
    app.wrap_var.set.assert_not_called()
    app.threaded_var.set.assert_not_called()
    app.clean_var.set.assert_not_called()

def test_keyboard_shortcut_bindings(app):
    # Test that keyboard bindings for display options exist on the root window
    app._build_menu()

    expected_bindings = [
        ("<Control-w>", app._toggle_wrap),
        ("<Control-W>", app._toggle_wrap),
        ("w", app._toggle_wrap),
        ("W", app._toggle_wrap),
        ("<Control-t>", app._toggle_conversations),
        ("<Control-T>", app._toggle_conversations),
        ("t", app._toggle_conversations),
        ("T", app._toggle_conversations),
        ("c", app._toggle_clean_view),
        ("C", app._toggle_clean_view),
    ]

    for key, handler in expected_bindings:
        app.root.bind.assert_any_call(key, handler)

def test_block_text_input_for_toggles(app):
    # Mock event for 'w'
    event_w = MagicMock()
    event_w.keysym.lower.return_value = 'w'
    event_w.state = 0

    with patch.object(app, '_toggle_wrap') as mock_toggle:
        result = app._block_text_input(event_w)
        assert result == "break"
        mock_toggle.assert_called_once()

    # Mock event for 't'
    event_t = MagicMock()
    event_t.keysym.lower.return_value = 't'
    event_t.state = 0

    with patch.object(app, '_toggle_conversations') as mock_toggle:
        result = app._block_text_input(event_t)
        assert result == "break"
        mock_toggle.assert_called_once()

    # Mock event for 'c'
    event_c = MagicMock()
    event_c.keysym.lower.return_value = 'c'
    event_c.state = 0

    with patch.object(app, '_toggle_clean_view') as mock_toggle:
        result = app._block_text_input(event_c)
        assert result == "break"
        mock_toggle.assert_called_once()
