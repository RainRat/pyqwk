import pytest
from pyqwk.core import _linkify_text, _apply_highlighting, _parse_html_messages
from unittest.mock import patch

def test_linkify_text_html_markdown_formats():
    text = "Visit https://example.com or email me@example.com"

    html_out = _linkify_text(text, "html")
    assert '<a href="https://example.com">https://example.com</a>' in html_out
    assert '<a href="mailto:me@example.com">me@example.com</a>' in html_out

    md_out = _linkify_text(text, "markdown")
    assert "[https://example.com](https://example.com)" in md_out
    assert "[me@example.com](mailto:me@example.com)" in md_out

def test_linkify_text_ansi_colors_phone():
    text = "Call 555-1234"
    # Testing phone ANSI highlighting (etype == "phone")
    ansi_out = _linkify_text(text, "ansi", use_colors=True)
    assert "\x1b[90m555-1234\x1b[0m" in ansi_out

    # Testing phone without colors
    plain_out = _linkify_text(text, "ansi", use_colors=False)
    assert "555-1234" in plain_out
    assert "\x1b" not in plain_out

def test_linkify_text_msg_link_variants():
    # msg_link without a valid message number (e.g. malformed or empty capture)
    # We can mock _discover_entities to return a msg_link with an value that RE_MSG_LINK_PATTERN won't match
    with patch("pyqwk.core._discover_entities") as mock_discover:
        mock_discover.return_value = [(0, 4, "msg_link", "none")]
        out = _linkify_text("none", "html")
        assert out == "none"

def test_linkify_text_unknown_entity_type():
    # This tests the bug fix: if etype is unknown, it should still append the text.
    with patch("pyqwk.core._discover_entities") as mock_discover:
        mock_discover.return_value = [(0, 7, "unknown", "content")]
        out = _linkify_text("content", "html")
        # Before fix, this would likely return empty string or skip the part
        assert "content" in out

def test_apply_highlighting_gaps():
    # term is None
    assert _apply_highlighting("text", None) == "text"

    # invalid regex
    assert _apply_highlighting("text", "[", is_regex=True) == "text"

    # Mid-text match
    # _apply_highlighting(text, term, is_regex=False, start_tag="", end_tag="", escape_func=None)
    out = _apply_highlighting("Hello World", "World", start_tag="<", end_tag=">")
    assert out == "Hello <World>"

def test_parse_html_messages_stray_div_close(tmp_path):
    # Covers tag_name == "/div" and not stack
    html_content = """
    <div class="message">
        <div class="header"><strong>Number:</strong> 1</div>
        <pre class="body">Body</pre>
    </div>
    </div>
    """
    html_file = tmp_path / "stray_div.html"
    html_file.write_text(html_content, encoding="utf-8")

    # This shouldn't crash and should handle the stray tag gracefully
    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 1
