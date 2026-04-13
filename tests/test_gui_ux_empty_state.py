import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
class MockTclError(Exception):
    pass

if "tkinter" in sys.modules:
    existing_tk = sys.modules["tkinter"]
    existing_tk.TclError = MockTclError
else:
    mock_tk = MagicMock()
    mock_tk.TclError = MockTclError
    sys.modules["tkinter"] = mock_tk

if "tkinter.ttk" not in sys.modules:
    sys.modules["tkinter.ttk"] = MagicMock()
if "tkinter.filedialog" not in sys.modules:
    sys.modules["tkinter.filedialog"] = MagicMock()
if "tkinter.messagebox" not in sys.modules:
    sys.modules["tkinter.messagebox"] = MagicMock()
if "tkinter.simpledialog" not in sys.modules:
    sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()

    with patch("tkinter.BooleanVar", return_value=MagicMock()), \
         patch("tkinter.StringVar", return_value=MagicMock()), \
         patch("tkinter.ttk.Treeview", return_value=MagicMock()) as mock_tree, \
         patch("tkinter.Text", return_value=MagicMock()) as mock_text, \
         patch("tkinter.ttk.Combobox"), \
         patch("tkinter.ttk.Label") as mock_label:

        a = QwkGuiApp(root)
        a.message_list = mock_tree.return_value
        a.detail_text = mock_text.return_value
        a.bbs_combo = MagicMock()
        a.conf_combo = MagicMock()
        a.search_count_label = mock_label.return_value

        # Reset common mocks
        a.detail_text.insert.reset_mock()
        a.detail_text.delete.reset_mock()
        a.search_count_label.config.reset_mock()

        return a

def test_render_empty_state_listing_filters(app):
    # Set up some active filters
    app.search_var.get.return_value = "vintage"
    app.regex_var.get.return_value = True
    app.bbs_combo.get.return_value = "The Cave BBS"
    app.conf_combo.get.return_value = "General"
    app.mine_var.get.return_value = True
    app.has_attach_var.get.return_value = True

    app._render_empty_state()

    # Verify basic structure
    inserted_texts = [call.args[1] for call in app.detail_text.insert.call_args_list if len(call.args) > 1]

    assert any("No Messages Found" in text for text in inserted_texts)
    assert any("Your current filters returned no results" in text for text in inserted_texts)

    # Verify specific filter reporting
    assert any("'vintage'" in text for text in inserted_texts)
    assert any("Regex Search" in text for text in inserted_texts)
    assert any("The Cave BBS" in text for text in inserted_texts)
    assert any("General" in text for text in inserted_texts)
    assert any("My Messages, Attachments" in text or ("My Messages" in text and "Attachments" in text) for text in inserted_texts)

    # Verify reset link and tip
    assert any("Reset all filters and search" in text for text in inserted_texts)
    assert any("Esc" in text for text in inserted_texts)

    # Verify match counter was cleared
    app.search_count_label.config.assert_called_with(text="")

def test_empty_state_reset_link_binding(app):
    # Dictionary to store tag callbacks
    tag_callbacks = {}
    def mock_tag_bind(tag, event, callback):
        tag_callbacks[tag] = callback
    app.detail_text.tag_bind.side_effect = mock_tag_bind

    with patch.object(app, "clear_filters") as mock_clear:
        app._render_empty_state()

        # Find the reset tag
        assert "reset_all" in tag_callbacks

        # Simulate click
        tag_callbacks["reset_all"](None)
        mock_clear.assert_called_once()

def test_load_messages_triggers_empty_state(app):
    # Mock load_data to return empty results
    from pyqwk.core import ConferenceMap
    empty_board = ConferenceMap()

    with patch("pyqwk.gui.load_data", return_value=([], empty_board)), \
         patch.object(app, "_render_empty_state") as mock_render_empty:

        app.load_messages(["empty.qwk"])

        mock_render_empty.assert_called_once()
