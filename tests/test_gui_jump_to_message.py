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
        h3 = MessageHeader(" ", 103, "01-01-23", "12:10", "To3", "From3", "Subj3", "", None, 1, " ", 2, 1, "")

        app.messages = [
            ParsedMessage("Text 1", 101, None, 1, h1),
            ParsedMessage("Text 2", 102, None, 1, h2),
            ParsedMessage("Text 3", 103, None, 2, h3),
        ]

        # Mock message_list behavior
        app.message_list.exists.return_value = True

        # Ensure filters appear inactive
        app.search_var.get.return_value = ""
        app.bbs_combo.get.return_value = "All BBSes"
        app.conf_combo.get.return_value = "All Conferences"
        for var in [app.has_attach_var, app.mine_var, app.on_this_day_var,
                    app.has_links_var, app.has_emails_var, app.has_phones_var, app.has_ansi_var]:
            var.get.return_value = False

        return app

def test_prompt_jump_to_message_success(app_with_messages):
    app = app_with_messages

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=102):
        app.prompt_jump_to_message()

    # Should select message with index 1 (msgnum 102)
    app.message_list.selection_set.assert_called_with("1")
    app.message_list.see.assert_called_with("1")

def test_prompt_jump_to_message_not_found(app_with_messages):
    app = app_with_messages

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=999), \
         patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.prompt_jump_to_message()

    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]

def test_prompt_jump_to_message_cancel(app_with_messages):
    app = app_with_messages

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=None):
        app.prompt_jump_to_message()

    app.message_list.selection_set.assert_not_called()

def test_prompt_jump_to_message_prefer_current_conf(app_with_messages):
    app = app_with_messages

    # Add another message with same msgnum but different conf
    h4 = MessageHeader(" ", 102, "01-01-23", "12:15", "To4", "From4", "Subj4", "", None, 1, " ", 2, 1, "")
    app.messages.append(ParsedMessage("Text 4", 102, None, 2, h4))

    # Set current selection to a message in conf 2 (index 2)
    app.message_list.selection.return_value = ["2"]

    with patch("pyqwk.gui.simpledialog.askinteger", return_value=102):
        app.prompt_jump_to_message()

    # Should prefer message 102 in conf 2 (which is index 3)
    app.message_list.selection_set.assert_called_with("3")

def test_jump_to_message_explicit(app_with_messages):
    app = app_with_messages

    app.jump_to_message(2, 103)
    app.message_list.selection_set.assert_called_with("2")

def test_jump_to_message_explicit_not_found(app_with_messages):
    app = app_with_messages

    with patch("pyqwk.gui.messagebox.showinfo") as mock_info:
        app.jump_to_message(1, 999)

    mock_info.assert_called_once()
    assert "999" in mock_info.call_args[0][1]
