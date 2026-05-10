import pytest
import tkinter as tk
from unittest.mock import MagicMock, patch
from pyqwk.core import _highlight_entities, RE_MSG_LINK_PATTERN

def test_msg_link_pattern():
    """Verify that the message link pattern matches various formats."""
    matches = RE_MSG_LINK_PATTERN.findall("Check msg #123 and message 456 also msg789")
    assert matches == ["123", "456", "789"]

def test_highlight_entities_ansi():
    """Verify that _highlight_entities applies the correct ANSI codes."""
    text = "Visit http://example.com or email test@example.com or see msg #123"

    # No colors
    assert _highlight_entities(text, use_colors=False) == text

    # With colors
    highlighted = _highlight_entities(text, use_colors=True)

    # URL: Underline (4) and Dim (90)
    assert "\x1b[4;90mhttp://example.com\x1b[0m" in highlighted
    # Email: Underline (4) and Dim (90)
    assert "\x1b[4;90mtest@example.com\x1b[0m" in highlighted
    # Message link: Cyan (36)
    assert "\x1b[36mmsg #123\x1b[0m" in highlighted

def test_gui_entity_discovery():
    """Verify that the GUI discovery loop identifies msg_link entities."""
    mock_root = MagicMock()
    with (
        patch("pyqwk.gui.tk.BooleanVar"),
        patch("pyqwk.gui.tk.StringVar"),
        patch("pyqwk.gui.tk.IntVar"),
        patch("pyqwk.gui.tk") as patched_tk,
        patch("pyqwk.gui.ttk"),
        patch("pyqwk.gui.font"),
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.simpledialog"),
    ):
        from pyqwk.gui import QwkGuiApp

        # Setup the Text mock
        mock_detail_text = MagicMock()
        patched_tk.Text.return_value = mock_detail_text

        # Create instance
        app = QwkGuiApp(mock_root)
        app.detail_text = mock_detail_text

        # Mock a message
    mock_msg = MagicMock()
    mock_msg.text = "Please refer to msg #500 for details."
    app.search_var.get.return_value = "" # Avoid tk.IntVar in _render_message
    mock_msg.header.confnum = 1
    mock_msg.header.msgsubject = "Test"
    mock_msg.header.msgfrom = "Admin"
    mock_msg.header.msgto = "User"
    mock_msg.header.msgdate = "01-01-23"
    mock_msg.header.msgtime = "12:00"
    mock_msg.header.msgnum = 100
    mock_msg.header.is_private = False
    mock_msg.attachments = []
    mock_msg.bbs_name = "TestBBS"
    mock_msg.source_file = "test.qwk"
    mock_msg.refnum = None

    app.messages = [mock_msg]

    # Trigger render
    app._render_message(0)

    # Check if insert was called with the 'msg_link' tag pattern
    # The tag is generated as (etype, id, start) + line_tags
    found_msg_link = False
    for call in app.detail_text.insert.call_args_list:
        args, kwargs = call
        if len(args) >= 3:
            tags = args[2]
            if isinstance(tags, tuple) and any(t.startswith("msg_link_") for t in tags):
                if args[1] == "msg #500":
                    found_msg_link = True
                    break

    assert found_msg_link, "GUI should have identified 'msg #500' as a link"
