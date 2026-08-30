from unittest.mock import MagicMock, patch
from pyqwk.gui import ToolTip


def test_tooltip_init_and_events():
    widget = MagicMock()
    tooltip = ToolTip(widget, "Clear search text", delay=50)

    assert tooltip.widget == widget
    assert tooltip.text == "Clear search text"
    assert tooltip.delay == 50
    assert tooltip.tip_window is None
    assert tooltip.timer_id is None

    # Check binds were made on widget
    bind_events = [call_args[0][0] for call_args in widget.bind.call_args_list]
    assert "<Enter>" in bind_events
    assert "<Leave>" in bind_events
    assert "<Button-1>" in bind_events


def test_tooltip_schedule_and_show():
    widget = MagicMock()
    widget.after.return_value = "timer_123"
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 200
    widget.winfo_height.return_value = 30

    tooltip = ToolTip(widget, "Reset filter", delay=10)

    # Hover enter schedules timer
    tooltip._on_enter(None)
    widget.after.assert_called_with(10, tooltip._show)
    assert tooltip.timer_id == "timer_123"

    # Mock tk.Toplevel and ttk.Label creation
    with patch("pyqwk.gui.tk.Toplevel") as mock_toplevel, patch("pyqwk.gui.ttk.Label") as mock_label:
        tw_instance = MagicMock()
        mock_toplevel.return_value = tw_instance

        tooltip._show()

        mock_toplevel.assert_called_once_with(widget)
        tw_instance.wm_overrideredirect.assert_called_once_with(True)
        tw_instance.wm_geometry.assert_called_once_with("+110+235")
        mock_label.assert_called_once()
        assert tooltip.tip_window == tw_instance

        # Second call to _show when tip_window exists is no-op
        tooltip._show()
        assert mock_toplevel.call_count == 1

        # Hover leave destroys tooltip window and cancels timer
        tooltip._on_leave(None)
        widget.after_cancel.assert_called_with("timer_123")
        tw_instance.destroy.assert_called_once()
        assert tooltip.tip_window is None
        assert tooltip.timer_id is None


def test_tooltip_empty_text():
    widget = MagicMock()
    tooltip = ToolTip(widget, "", delay=10)

    with patch("pyqwk.gui.tk.Toplevel") as mock_toplevel:
        tooltip._show()
        mock_toplevel.assert_not_called()
        assert tooltip.tip_window is None


def test_tooltip_exception_handling():
    widget = MagicMock()
    widget.winfo_rootx.side_effect = Exception("Widget destroyed")

    tooltip = ToolTip(widget, "Tooltip text", delay=10)
    with patch("pyqwk.gui.tk.Toplevel") as mock_toplevel:
        tooltip._show()
        mock_toplevel.assert_not_called()

    # Exception during destroy should be swallowed gracefully
    bad_tw = MagicMock()
    bad_tw.destroy.side_effect = Exception("TclError")
    tooltip.tip_window = bad_tw
    tooltip._hide()
    assert tooltip.tip_window is None
