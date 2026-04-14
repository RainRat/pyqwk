import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def app_with_messages():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.simpledialog"):
        app = QwkGuiApp(root)
        app.current_paths = ["fake.qwk"]

        # Create some dummy messages
        h1 = MessageHeader(" ", 101, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, "")
        h2 = MessageHeader(" ", 102, "01-01-23", "12:05", "To2", "From2", "Subj2", "", None, 1, " ", 1, 1, "")

        app.full_messages = [
            ParsedMessage("Text 1", 101, None, 1, h1),
            ParsedMessage("Text 2", 102, None, 1, h2),
        ]
        app.messages = list(app.full_messages)

        # Mock message_list behavior
        app.message_list.exists.return_value = True

        # Ensure filters appear inactive
        app.search_var = MagicMock()
        app.search_var.get.return_value = ""
        app.bbs_combo = MagicMock()
        app.bbs_combo.get.return_value = "All BBSes"
        app.conf_combo = MagicMock()
        app.conf_combo.get.return_value = "All Conferences"

        app.has_attach_var = MagicMock()
        app.mine_var = MagicMock()
        app.on_this_day_var = MagicMock()
        app.has_links_var = MagicMock()
        app.has_emails_var = MagicMock()
        app.has_phones_var = MagicMock()
        app.has_ansi_var = MagicMock()

        for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                    app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
            var.get.return_value = False

        # Mock clear_filters
        def mock_clear_filters():
            app.messages = list(app.full_messages)
            app.search_var.get.return_value = ""
            app.bbs_combo.get.return_value = "All BBSes"
            app.conf_combo.get.return_value = "All Conferences"
            for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                        app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
                var.get.return_value = False

        app.clear_filters = MagicMock(side_effect=mock_clear_filters)

        return app

def test_prompt_jump_to_message_with_reset(app_with_messages):
    app = app_with_messages

    # Simulate a filter that hides message 102
    app.messages = [app.full_messages[0]]

    # Mock search_var to indicate filter is active
    app.search_var.get.return_value = "some filter"

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=102), \
         patch("pyqwk.gui.messagebox.askyesno", return_value=True) as mock_ask:
        app.prompt_jump_to_message()

    mock_ask.assert_called() # It might be called twice due to the __bool__ mock behavior
    assert "reset all filters" in mock_ask.call_args_list[0][0][1]

    # Should have selected message with index 1 (msgnum 102) after reset
    app.message_list.selection_set.assert_called_with("1")

def test_jump_to_message_with_reset_decline(app_with_messages):
    app = app_with_messages

    # Simulate a filter that hides message 102
    app.messages = [app.full_messages[0]]
    app.search_var.get.return_value = "some filter"

    with patch("pyqwk.gui.messagebox.askyesno", return_value=False) as mock_ask, \
         patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.jump_to_message(1, 102)

    mock_ask.assert_called()
    mock_info.assert_called_once()
    assert "Referenced message #102" in mock_info.call_args[0][1]
    app.message_list.selection_set.assert_not_called()

def test_prompt_jump_to_message_no_reset_needed(app_with_messages):
    app = app_with_messages
    app.search_var.get.return_value = "" # No filters

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=999), \
         patch("pyqwk.gui.messagebox.askyesno") as mock_ask, \
         patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.prompt_jump_to_message()

    # In my new logic, it still shows "Not Found" but doesn't prompt for reset if filters are inactive
    mock_ask.assert_not_called()
    mock_info.assert_called_once()

def test_is_any_filter_active(app_with_messages):
    app = app_with_messages

    # Default is inactive in our fixture setup
    assert app._is_any_filter_active() is False

    # Test search
    app.search_var.get.return_value = "test"
    assert app._is_any_filter_active() is True
    app.search_var.get.return_value = ""

    # Test BBS
    app.bbs_combo.get.return_value = "BBS 1"
    assert app._is_any_filter_active() is True
    app.bbs_combo.get.return_value = "All BBSes"

    # Test Conf
    app.conf_combo.get.return_value = "Conf 1"
    assert app._is_any_filter_active() is True
    app.conf_combo.get.return_value = "All Conferences"

    # Test boolean var
    app.mine_var.get.return_value = True
    assert app._is_any_filter_active() is True
