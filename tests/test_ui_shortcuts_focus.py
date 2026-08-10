import pytest
from unittest.mock import MagicMock, patch

# Define dummy Entry classes for isinstance checks that accept any arguments and mock standard methods
class DummyTkEntry:
    def __init__(self, *args, **kwargs):
        self.focus_set = MagicMock()
        self.selection_range = MagicMock()
        self.bind = MagicMock()
        self.grid = MagicMock()
        self.pack = MagicMock()

class DummyTtkEntry:
    def __init__(self, *args, **kwargs):
        self.focus_set = MagicMock()
        self.selection_range = MagicMock()
        self.bind = MagicMock()
        self.grid = MagicMock()
        self.pack = MagicMock()

# Patch tkinter and ttk for pyqwk.gui
@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):
        mock_tk.Entry = DummyTkEntry
        mock_ttk.Entry = DummyTtkEntry

        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        # Tkinter constants
        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"

        # Mock Combobox
        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "combo": mock_combo,
        }

def test_shortcuts_prevented_when_entry_focused(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    # Use the instantiated entries
    # 1. Test _select_relative_message when an entry has focus
    app.messages = [MagicMock()]
    root.focus_get.return_value = app.min_words_entry
    # It should return False and not do selection because min_words_entry is focused (isinstance check)
    assert app._select_relative_message(1) is False

    # 2. Test _select_random_message when an entry has focus
    root.focus_get.return_value = app.max_words_entry
    with patch.object(app, "_get_all_tree_items", return_value=["item1"]):
        app._select_random_message()
        app.message_list.selection_set.assert_not_called()

    # 3. Test _navigate_combo when an entry has focus
    root.focus_get.return_value = app.search_entry
    combo = MagicMock()
    combo.__getitem__.return_value = ["val1", "val2"]
    app._navigate_combo(combo, 1)
    combo.current.assert_not_called()

    # 4. Test _on_space_pressed when an entry has focus
    root.focus_get.return_value = app.exclude_entry
    event = MagicMock()
    assert app._on_space_pressed(event) is None

    # 5. Test _focus_search when typing '/' in an entry (keysym="slash")
    root.focus_get.return_value = app.min_words_entry
    event = MagicMock()
    event.keysym = "slash"
    event.char = "/"
    with patch.object(app, "_focus_entry_field") as mock_focus_field:
        app._focus_search(event)
        mock_focus_field.assert_not_called()

def test_focus_search_with_slash_and_non_entry(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    app.message_list = MagicMock()

    # Case A: slash key pressed but treeview is focused -> should focus search!
    root.focus_get.return_value = app.message_list
    event = MagicMock()
    event.keysym = "slash"
    event.char = "/"
    with patch.object(app, "_focus_entry_field") as mock_focus_field:
        app._focus_search(event)
        mock_focus_field.assert_called_once_with("search_entry", "search_var")

    # Case B: non-slash event (e.g. Ctrl+F) and entry is focused -> should focus search!
    root.focus_get.return_value = app.min_words_entry
    event_ctrl_f = MagicMock()
    event_ctrl_f.keysym = "f"
    event_ctrl_f.char = "\x06"
    with patch.object(app, "_focus_entry_field") as mock_focus_field:
        app._focus_search(event_ctrl_f)
        mock_focus_field.assert_called_once_with("search_entry", "search_var")


def test_new_ui_shortcuts_and_consistency(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    # 1. Verify uppercase Ctrl shortcuts and equivalents are bound on root
    bound_events = [args[0][0] for args in root.bind.call_args_list]
    assert "<Control-O>" in bound_events
    assert "<Control-S>" in bound_events
    assert "<Control-I>" in bound_events
    assert "<Control-F>" in bound_events
    assert "<Control-E>" in bound_events
    assert "<Control-G>" in bound_events
    assert "<Control-Q>" in bound_events
    assert "<Control-U>" in bound_events
    assert "<Control-Shift-X>" in bound_events
    assert "<Control-Shift-x>" in bound_events

    # 2. Verify standard bindings on exclude_entry
    exclude_binds = [args[0][0] for args in app.exclude_entry.bind.call_args_list]
    assert "<Up>" in exclude_binds
    assert "<Down>" in exclude_binds
    assert "<Escape>" in exclude_binds

    # 3. Verify standard bindings on min_words_entry and max_words_entry
    min_binds = [args[0][0] for args in app.min_words_entry.bind.call_args_list]
    assert "<Return>" in min_binds
    assert "<Escape>" in min_binds
    assert "<Up>" in min_binds
    assert "<Down>" in min_binds

    max_binds = [args[0][0] for args in app.max_words_entry.bind.call_args_list]
    assert "<Return>" in max_binds
    assert "<Escape>" in max_binds
    assert "<Up>" in max_binds
    assert "<Down>" in max_binds

    # 4. Verify detail_text foreground
    text_mock = mock_gui_deps["tk"].Text
    kwargs_list = [args[1] for args in text_mock.call_args_list]
    assert any(kw.get("foreground") == "#000000" for kw in kwargs_list)
