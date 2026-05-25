import pytest
from pyqwk.core import _parse_html_messages

def test_parse_html_messages_div_boundary(tmp_path):
    """Verify that _parse_html_messages doesn't incorrectly pick up tags like <divisible>."""
    html_content = """
    <divisible class="reply">
        <div class="message">
            <div class="header">
                <strong>From:</strong> User1<br>
                <strong>Date:</strong> 01-01-24 10:00<br>
                <strong>Number:</strong> 1<br>
            </div>
            <pre class="body">Message 1</pre>
        </div>
    </divisible>
    """
    html_path = tmp_path / "boundary.html"
    html_path.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_path))
    assert len(messages) == 1
    # Depth should be 0 because <divisible class="reply"> should NOT be counted as a nested reply div.
    # Currently it will likely be 1.
    assert messages[0].depth == 0

def test_parse_html_messages_slash_div_boundary(tmp_path):
    """Verify that _parse_html_messages doesn't incorrectly pick up tags like </divisible>."""
    html_content = """
    <div class="reply">
        <div class="message">
            <div class="header">
                <strong>From:</strong> User1<br>
                <strong>Date:</strong> 01-01-24 10:00<br>
                <strong>Number:</strong> 1<br>
            </div>
            <pre class="body">Message 1</pre>
        </div>
    </divisible>
    <div class="message">
        <div class="header">
            <strong>From:</strong> User2<br>
            <strong>Date:</strong> 01-01-24 11:00<br>
            <strong>Number:</strong> 2<br>
        </div>
        <pre class="body">Message 2</pre>
    </div>
    """
    html_path = tmp_path / "slash_boundary.html"
    html_path.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_path))
    assert len(messages) == 2
    assert messages[0].depth == 1
    # If </divisible> is incorrectly seen as </div>, it might decrement the depth.
    # Actually, in the current implementation:
    # </divisible> matches: G1=/div, G2=isible
    # it pops from stack.
    # So Message 2 depth would be 0 (incorrectly decremented) instead of 1.
    assert messages[1].depth == 1
