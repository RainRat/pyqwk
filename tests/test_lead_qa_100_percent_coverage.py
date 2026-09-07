from unittest.mock import MagicMock
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    show_list_phones,
)
from pyqwk.gui import ToolTip


def test_show_list_phones_whitespace_match_handling(mocker, tmp_path):
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(
        text="Call me at 555-123-4567",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))
    mock_pattern = MagicMock()
    mock_pattern.findall.return_value = ["   ", ""]
    mocker.patch("pyqwk.core.RE_PHONE_PATTERN", mock_pattern)

    logger = MagicMock()
    output_file = tmp_path / "phones.txt"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=str(output_file),
        encoding="utf-8",
    )

    show_list_phones(["dummy.qwk"], settings, logger)
    logger.warning.assert_called_once_with("No phone numbers found across messages.")


def test_tooltip_unschedule_exception():
    widget = MagicMock()
    widget.after_cancel.side_effect = Exception("Cancel failed")
    tooltip = ToolTip(widget, "Test Tip")
    tooltip._timer_id = "timer123"
    tooltip._unschedule()
    assert tooltip._timer_id is None


def test_tooltip_show_rootx_exception():
    widget = MagicMock()
    widget.winfo_rootx.side_effect = Exception("Rootx error")
    tooltip = ToolTip(widget, "Test Tip")
    tooltip.show()
    assert tooltip.tooltip_window is None


def test_tooltip_show_attributes_exception(mocker):
    widget = MagicMock()
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 100
    widget.winfo_height.return_value = 20

    mock_toplevel = MagicMock()
    mock_toplevel.attributes.side_effect = Exception("Attributes error")
    mocker.patch("pyqwk.gui.tk.Toplevel", return_value=mock_toplevel)
    mocker.patch("pyqwk.gui.tk.Label")

    tooltip = ToolTip(widget, "Test Tip")
    tooltip.show()
    assert tooltip.tooltip_window is mock_toplevel


def test_tooltip_hide_destroy_exception():
    mock_tw = MagicMock()
    mock_tw.destroy.side_effect = Exception("Destroy error")
    tooltip = ToolTip(MagicMock(), "Test Tip")
    tooltip.tooltip_window = mock_tw
    tooltip.hide()
    assert tooltip.tooltip_window is None
