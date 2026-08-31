import os
import sys
import tkinter as tk
import pytest

from pyqwk.gui import ToolTip, QwkGuiApp


@pytest.fixture
def tk_root():
    """Fixture providing a Tk root window, skipped if headless/no display."""
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except tk.TclError:
        pytest.skip("Tkinter display not available in headless environment")


def test_tooltip_init_and_bindings(tk_root):
    btn = tk.Button(tk_root, text="Test")
    tooltip = ToolTip(btn, "Helpful info", delay_ms=100)

    assert tooltip.widget == btn
    assert tooltip.text == "Helpful info"
    assert tooltip.delay_ms == 100
    assert tooltip.tooltip_window is None


def test_tooltip_show_and_hide(tk_root):
    btn = tk.Button(tk_root, text="Test")
    btn.pack()
    tk_root.update_idletasks()

    tooltip = ToolTip(btn, "Helpful info", delay_ms=50)

    # Directly show tooltip
    tooltip.show()
    assert tooltip.tooltip_window is not None
    assert tooltip.tooltip_window.winfo_exists()

    # Calling show again should be a no-op
    tooltip.show()

    # Hide tooltip
    tooltip.hide()
    assert tooltip.tooltip_window is None


def test_tooltip_schedule_and_events(tk_root):
    btn = tk.Button(tk_root, text="Test")
    btn.pack()
    tk_root.update_idletasks()

    tooltip = ToolTip(btn, "Hover Text", delay_ms=50)

    # Mouse enter triggers schedule
    tooltip._on_enter()
    assert tooltip._timer_id is not None

    # Fast mouse leave cancels timer and hides
    tooltip._on_leave()
    assert tooltip._timer_id is None
    assert tooltip.tooltip_window is None


def test_tooltip_destroy_cleanup(tk_root):
    btn = tk.Button(tk_root, text="Test")
    btn.pack()
    tk_root.update_idletasks()

    tooltip = ToolTip(btn, "Hover Text", delay_ms=50)
    tooltip.show()
    assert tooltip.tooltip_window is not None

    tooltip._on_destroy()
    assert tooltip.tooltip_window is None


def test_gui_app_has_tooltips(tk_root):
    app = QwkGuiApp(tk_root)
    assert hasattr(app, "root")
