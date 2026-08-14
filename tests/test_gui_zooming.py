import pytest
from unittest.mock import MagicMock, patch

# Define dummy Entry classes for isinstance checks
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

def test_gui_text_zooming(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    # 1. Initial State
    assert app.font_size_offset == 0

    # 2. Zoom In
    app.adjust_zoom(1)
    assert app.font_size_offset == 1

    # Verify font config call for body
    body_config = app.detail_text.tag_configure.call_args_list
    # Find tag configuration for "body"
    body_calls = [c for c in body_config if c[0][0] == "body"]
    assert len(body_calls) > 0
    last_body_font = body_calls[-1][1]["font"]
    assert last_body_font == ("TkFixedFont", 11)

    # 3. Zoom Out
    app.adjust_zoom(-2)
    assert app.font_size_offset == -1

    body_calls = [c for c in app.detail_text.tag_configure.call_args_list if c[0][0] == "body"]
    last_body_font = body_calls[-1][1]["font"]
    assert last_body_font == ("TkFixedFont", 9)

    # 4. Zoom clamping - Min
    app.adjust_zoom(-10)
    assert app.font_size_offset == -4
    body_calls = [c for c in app.detail_text.tag_configure.call_args_list if c[0][0] == "body"]
    last_body_font = body_calls[-1][1]["font"]
    assert last_body_font == ("TkFixedFont", 6)

    # 5. Zoom clamping - Max
    app.adjust_zoom(20)
    assert app.font_size_offset == 10
    body_calls = [c for c in app.detail_text.tag_configure.call_args_list if c[0][0] == "body"]
    last_body_font = body_calls[-1][1]["font"]
    assert last_body_font == ("TkFixedFont", 20)

    # 6. Reset Zoom
    app.reset_zoom()
    assert app.font_size_offset == 0
    body_calls = [c for c in app.detail_text.tag_configure.call_args_list if c[0][0] == "body"]
    last_body_font = body_calls[-1][1]["font"]
    assert last_body_font == ("TkFixedFont", 10)


def test_zoom_bindings_and_menu(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    app = QwkGuiApp(root)

    # Verify keyboard shortcut bindings
    bound_events = [args[0][0] for args in root.bind.call_args_list]
    assert "<Control-plus>" in bound_events
    assert "<Control-equal>" in bound_events
    assert "<Control-KP_Add>" in bound_events
    assert "<Control-minus>" in bound_events
    assert "<Control-KP_Subtract>" in bound_events
    assert "<Control-0>" in bound_events
    assert "<Control-KP_0>" in bound_events
