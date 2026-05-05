from unittest.mock import MagicMock, patch


def test_on_space_pressed_scrolling():
    """Verify that _on_space_pressed scrolls the text widget when not at the bottom."""
    mock_root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.font"):
        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        # Mock detail_text
        app.detail_text = MagicMock()
        # Mock yview to return (top, bottom) fractions
        app.detail_text.yview.return_value = (0.0, 0.5)

        # Simulate Space press
        event = MagicMock()
        event.keysym = "space"
        event.state = 0  # No Shift

        result = app._on_space_pressed(event)

        assert result == "break"
        app.detail_text.yview_scroll.assert_called_with(1, "pages")


def test_on_space_pressed_advance():
    """Verify that _on_space_pressed advances to the next message when at the bottom."""
    mock_root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.font"):
        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        # Mock detail_text at bottom
        app.detail_text = MagicMock()
        app.detail_text.yview.return_value = (0.5, 1.0)

        # Mock message advancement
        app._select_relative_message = MagicMock()

        # Simulate Space press
        event = MagicMock()
        event.keysym = "space"
        event.state = 0

        result = app._on_space_pressed(event)

        assert result == "break"
        app._select_relative_message.assert_called_with(1)


def test_on_shift_space_scrolling():
    """Verify that Shift+Space scrolls the text widget up when not at the top."""
    mock_root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.font"):
        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        # Mock detail_text not at top
        app.detail_text = MagicMock()
        app.detail_text.yview.return_value = (0.5, 1.0)

        # Simulate Shift+Space press
        event = MagicMock()
        event.keysym = "space"
        event.state = 0x1  # Shift mask

        result = app._on_space_pressed(event)

        assert result == "break"
        app.detail_text.yview_scroll.assert_called_with(-1, "pages")


def test_on_backspace_advance_back():
    """Verify that BackSpace advances to the previous message when at the top."""
    mock_root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.font"):
        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        # Mock detail_text at top
        app.detail_text = MagicMock()
        app.detail_text.yview.return_value = (0.0, 0.5)

        # Mock message advancement
        app._select_relative_message = MagicMock()

        # Simulate BackSpace press
        event = MagicMock()
        event.keysym = "BackSpace"
        event.state = 0

        result = app._on_space_pressed(event)

        assert result == "break"
        app._select_relative_message.assert_called_with(-1)


def test_space_ignored_when_search_focused():
    """Verify that Space is ignored when the search entry has focus."""
    mock_root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.font"):
        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        app.search_entry = MagicMock()
        mock_root.focus_get.return_value = app.search_entry

        event = MagicMock()
        event.keysym = "space"
        event.state = 0

        result = app._on_space_pressed(event)

        assert result is None
