import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from pyqwk.gui import QwkGuiApp, ToolTip


@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.messagebox"),
    ):
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.SOLID = "solid"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        class TclError(Exception):
            pass

        mock_tk.TclError = TclError

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
        }


def test_tooltip_init_and_events():
    widget = MagicMock()
    tooltip = ToolTip(widget, "Clear BBS filter", delay_ms=100)

    assert tooltip.text == "Clear BBS filter"
    assert tooltip.delay_ms == 100
    assert widget.bind.call_count >= 4


def test_tooltip_schedule_and_show():
    widget = MagicMock()
    widget.winfo_exists.return_value = True
    widget.bbox.return_value = (0, 0, 10, 20)
    widget.winfo_height.return_value = 20
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 100

    tooltip = ToolTip(widget, "Test Tooltip", delay_ms=100)

    # Test enter triggers schedule
    widget.after.return_value = "timer_1"
    tooltip._on_enter()
    widget.after.assert_called_with(100, tooltip._show)

    # Test show window creation
    with patch("pyqwk.gui.tk.Toplevel") as mock_toplevel:
        tw_instance = MagicMock()
        mock_toplevel.return_value = tw_instance
        tooltip._show()

        mock_toplevel.assert_called_once_with(widget)
        tw_instance.wm_overrideredirect.assert_called_with(True)
        assert tooltip.tip_window == tw_instance

        # Test leave hides window
        tooltip._on_leave()
        tw_instance.destroy.assert_called_once()
        assert tooltip.tip_window is None


def test_tooltip_show_existing_or_destroyed_widget():
    widget = MagicMock()
    tooltip = ToolTip(widget, "Test Tooltip")

    # If tip_window already exists
    tooltip.tip_window = MagicMock()
    tooltip._show()
    # Widget check shouldn't crash or recreate
    assert tooltip.tip_window is not None

    # If widget no longer exists
    tooltip.tip_window = None
    widget.winfo_exists.return_value = False
    tooltip._show()
    assert tooltip.tip_window is None


def test_gui_toolbar_tooltips_creation(mock_gui_deps):
    root = MagicMock()
    with patch("pyqwk.gui.ToolTip") as mock_tooltip_cls:
        app = QwkGuiApp(root)
        assert mock_tooltip_cls.call_count >= 10
        texts = [call.args[1] for call in mock_tooltip_cls.call_args_list]
        assert "Clear Find field" in texts
        assert "Clear Exclude field" in texts
        assert "Clear BBS filter" in texts
        assert "Clear conference filter" in texts
        assert "Clear visibility filters" in texts
        assert "Clear word limit filters" in texts
        assert "Clear display options" in texts
