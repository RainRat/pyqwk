from unittest.mock import MagicMock, patch
import pytest
from pyqwk.gui import QwkGuiApp


@pytest.fixture
def app():
    with (
        patch("pyqwk.gui.tk"),
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        root = MagicMock()
        root.after = MagicMock()
        app_inst = QwkGuiApp(root)
        app_inst.message_list = MagicMock()
        app_inst.detail_text = MagicMock()
        return app_inst


def test_on_message_list_activate_with_selection(app):
    """Test that activation transfers focus to detail_text and returns 'break' when selected."""
    app.message_list.selection.return_value = ("0",)
    res = app._on_message_list_activate()

    app.detail_text.focus_set.assert_called_once()
    assert res == "break"


def test_on_message_list_activate_without_selection(app):
    """Test that activation does nothing and returns None when no item is selected."""
    app.message_list.selection.return_value = ()
    res = app._on_message_list_activate()

    app.detail_text.focus_set.assert_not_called()
    assert res is None
