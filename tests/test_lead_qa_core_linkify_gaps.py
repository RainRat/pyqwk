from unittest.mock import patch
from pyqwk.core import _linkify_text, _parse_html_messages

def test_linkify_text_unknown_entity_type():
    # This test demonstrates the bug where unknown entity types cause text deletion.
    # We mock _discover_entities to return an unknown type.
    with patch("pyqwk.core._discover_entities") as mock_discover:
        # "world" is at 6:11 in "Hello world!"
        mock_discover.return_value = [(6, 11, "unknown", "world")]
        text = "Hello world!"
        # Ensure that unknown entity types do NOT cause text deletion.
        result = _linkify_text(text, "text")
        assert result == "Hello world!"

def test_linkify_text_html_formats():
    text = "Check http://example.com and www.example.com and test@example.com and msg #123"
    result = _linkify_text(text, "html", conf_num=1)
    assert '<a href="http://example.com">http://example.com</a>' in result
    assert '<a href="http://www.example.com">www.example.com</a>' in result
    assert '<a href="mailto:test@example.com">test@example.com</a>' in result
    assert '<a href="#msg-1-123">msg #123</a>' in result

def test_linkify_text_markdown_formats():
    text = "Check http://example.com and www.example.com and test@example.com and msg #123"
    result = _linkify_text(text, "markdown", conf_num=1)
    assert '[http://example.com](http://example.com)' in result
    assert '[www.example.com](http://www.example.com)' in result
    assert '[test@example.com](mailto:test@example.com)' in result
    assert '[msg #123](#msg-1-123)' in result

def test_linkify_text_ansi_colors():
    text = "Check http://example.com test@example.com 123-456-7890 msg #123"
    result = _linkify_text(text, "ansi", use_colors=True)
    assert "\x1b[4;90mhttp://example.com\x1b[0m" in result
    assert "\x1b[4;90mtest@example.com\x1b[0m" in result
    assert "\x1b[90m123-456-7890\x1b[0m" in result
    assert "\x1b[36mmsg #123\x1b[0m" in result

def test_linkify_text_msg_link_no_match():
    # Force msg_link etype but with value that fails RE_MSG_LINK_PATTERN
    with patch("pyqwk.core._discover_entities") as mock_discover:
        mock_discover.return_value = [(0, 3, "msg_link", "abc")]
        result = _linkify_text("abc", "text")
        assert result == "abc"

def test_linkify_text_overlaps():
    # _discover_entities handles overlaps, but we can test _linkify_text's handling of the results
    # "www.example.com" could be seen as "www.example.com" (url) and "example" (search)
    text = "Visit www.example.com"
    result = _linkify_text(text, "text", search_term="example")
    # Due to sorting and filtering in _discover_entities, it should prefer the longer URL
    assert result == "Visit www.example.com"

def test_parse_html_messages_stray_div_close(tmp_path):
    # Covers line 1451-1453: if stack is empty
    content = '</div><div class="message"><pre class="body">text</pre></div>'
    f = tmp_path / "stray.html"
    f.write_text(content, encoding="utf-8")
    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].text == "text"

def test_parse_html_messages_incomplete_date(tmp_path):
    # Covers line 1649, 1651 where parts are missing
    content = '<div class="message"><strong>Date:</strong> 2024-01-01 </div>'
    f = tmp_path / "date.html"
    f.write_text(content, encoding="utf-8")
    msgs = _parse_html_messages(str(f))
    assert msgs[0].header.msgdate == "2024-01-01"
    assert msgs[0].header.msgtime == "00:00"

    content2 = '<div class="message"><strong>Date:</strong> </div>'
    f2 = tmp_path / "date2.html"
    f2.write_text(content2, encoding="utf-8")
    msgs2 = _parse_html_messages(str(f2))
    assert msgs2[0].header.msgdate == "01-01-70"
    assert msgs2[0].header.msgtime == "00:00"
