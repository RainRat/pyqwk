import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import _write_html

def test_html_output_decreasing_depth(message_factory):
    """
    Verify that _write_html correctly handles cases where message depth decreases,
    ensuring all nested <div> tags are closed.
    """
    # Create a sequence of messages with varying depths: 0 -> 1 -> 2 -> 0
    msgs = [
        message_factory(1, None, "Root"),
        message_factory(2, 1, "Child 1"),
        message_factory(3, 2, "Grandchild 1"),
        message_factory(4, None, "Root 2"),
    ]

    # Manually set depths as _order_messages_by_thread usually does this
    msgs[0].depth = 0
    msgs[1].depth = 1
    msgs[2].depth = 2
    msgs[3].depth = 0

    with patch("pyqwk.core._write_text_output") as mock_write:
        _write_html(msgs, None)
        content = mock_write.call_args[0][0]

        # Verify that we have the correct number of opening div tags for replies
        assert content.count('<div class="reply">') == 2

        # Verify the structure when depth decreases from 2 to 0.
        # It should close the Grandchild message div, then two reply divs.
        # So we expect </div> repeated three times (with newlines/whitespace)
        # between Grandchild 1's body and Root 2's message.

        # Let's check for the triple </div> closing block.
        assert "</div>\n</div>\n</div>\n<div class=\"message\">" in content

def test_html_output_trailing_closing_tags(message_factory):
    """
    Verify that _write_html closes all remaining nested <div> tags at the end of the file.
    """
    # Sequence ends at depth 1
    msgs = [
        message_factory(1, None, "Root"),
        message_factory(2, 1, "Child 1"),
    ]
    msgs[0].depth = 0
    msgs[1].depth = 1

    with patch("pyqwk.core._write_text_output") as mock_write:
        _write_html(msgs, None)
        content = mock_write.call_args[0][0]

        # It should close the Child 1 message div, then the one reply div, then body/html
        # </div> (Message)
        # </div> (Reply)
        # </body>
        # </html>
        assert "</div>\n</div>\n</body>" in content
