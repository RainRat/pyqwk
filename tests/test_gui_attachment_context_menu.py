from unittest.mock import MagicMock, patch
import pytest

from pyqwk.gui import QwkGuiApp


def test_add_attachment_context_commands_single():
    app = MagicMock(spec=QwkGuiApp)
    menu = MagicMock()
    msg = MagicMock()
    msg.attachments = ["sample_image.png"]

    QwkGuiApp._add_attachment_context_commands(app, menu, msg)

    menu.add_separator.assert_called_once()
    menu.add_command.assert_called_once()
    assert "Save Attachment: sample_image.png" in menu.add_command.call_args.kwargs["label"]


def test_add_attachment_context_commands_multiple():
    app = MagicMock(spec=QwkGuiApp)
    menu = MagicMock()
    msg = MagicMock()
    msg.attachments = ["archive.zip", "document.pdf"]

    QwkGuiApp._add_attachment_context_commands(app, menu, msg)

    menu.add_separator.assert_called_once()
    menu.add_cascade.assert_called_once()
    assert "Save Attachment (2 files)" in menu.add_cascade.call_args.kwargs["label"]


def test_add_attachment_context_commands_empty():
    app = MagicMock(spec=QwkGuiApp)
    menu = MagicMock()
    msg = MagicMock()
    msg.attachments = []

    QwkGuiApp._add_attachment_context_commands(app, menu, msg)

    menu.add_separator.assert_not_called()
    menu.add_command.assert_not_called()
    menu.add_cascade.assert_not_called()


def test_add_attachment_context_commands_none():
    app = MagicMock(spec=QwkGuiApp)
    menu = MagicMock()
    msg = MagicMock()
    msg.attachments = None

    QwkGuiApp._add_attachment_context_commands(app, menu, msg)

    menu.add_separator.assert_not_called()
    menu.add_command.assert_not_called()
    menu.add_cascade.assert_not_called()
