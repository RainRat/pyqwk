from unittest.mock import MagicMock, patch
import pytest


def test_tooltip_unit_logic():
    from pyqwk.gui import ToolTip

    widget = MagicMock()
    widget.after.return_value = "timer_123"
    widget.winfo_exists.return_value = True
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 200
    widget.winfo_height.return_value = 25

    with patch("pyqwk.gui.tk") as mock_tk:
        tip = ToolTip(widget, "Clear Search", delay_ms=400)
        assert tip.text == "Clear Search"
        assert tip.delay_ms == 400

        # Schedule timer
        tip._on_enter(None)
        widget.after.assert_called_with(400, tip.show_tip)
        assert tip._timer_id == "timer_123"

        # Show tip creates Toplevel and Label
        tip.show_tip()
        assert mock_tk.Toplevel.called
        assert mock_tk.Label.called
        tw_mock = mock_tk.Toplevel.return_value
        tw_mock.wm_overrideredirect.assert_called_with(True)
        tw_mock.wm_geometry.assert_called_with("+110+230")

        # Unschedule and hide tip on click/leave/destroy
        tip._on_leave(None)
        widget.after_cancel.assert_called_with("timer_123")
        tw_mock.destroy.assert_called_once()
        assert tip.tip_window is None


def test_gui_toolbar_tooltips_attached():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.ToolTip") as mock_tooltip,
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.simpledialog"),
    ):
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        from pyqwk.gui import QwkGuiApp

        root = MagicMock()
        QwkGuiApp(root)

        tooltip_texts = [call[0][1] for call in mock_tooltip.call_args_list]

        expected_texts = [
            "Clear Search",
            "Previous Search Match (Shift+F3)",
            "Next Search Match (F3)",
            "Clear Exclusion",
            "Previous BBS ({)",
            "Reset BBS Filter",
            "Next BBS (})",
            "Previous Conference ([)",
            "Reset Conference Filter",
            "Next Conference (])",
            "Reset Visibility Filters",
            "Reset Word Limits",
            "Reset Display Options",
        ]

        for text in expected_texts:
            assert text in tooltip_texts, f"Expected tooltip text '{text}' not found in toolbar buttons"
