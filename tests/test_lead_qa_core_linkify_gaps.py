from pyqwk.core import _linkify_text, _apply_highlighting

def test_linkify_url_html():
    text = "Check out https://google.com"
    result = _linkify_text(text, output_format="html")
    assert '<a href="https://google.com">https://google.com</a>' in result

def test_linkify_url_markdown():
    text = "Check out https://google.com"
    result = _linkify_text(text, output_format="markdown")
    assert "[https://google.com](https://google.com)" in result

def test_linkify_email_html():
    text = "Contact me@example.com"
    result = _linkify_text(text, output_format="html")
    assert '<a href="mailto:me@example.com">me@example.com</a>' in result

def test_linkify_email_markdown():
    text = "Contact me@example.com"
    result = _linkify_text(text, output_format="markdown")
    assert "[me@example.com](mailto:me@example.com)" in result

def test_linkify_phone_ansi_colors():
    text = "Call 555-1234"
    result = _linkify_text(text, output_format="ansi", use_colors=True)
    assert "\x1b[90m555-1234\x1b[0m" in result

def test_linkify_msg_link_no_num(mocker):
    mock_match = mocker.MagicMock()
    mock_match.start.return_value = 0
    mock_match.end.return_value = 4
    mock_match.group.return_value = "msg#"

    mock_pattern = mocker.MagicMock()
    mock_pattern.finditer.return_value = [mock_match]
    mock_pattern.search.return_value = None

    mocker.patch("pyqwk.core.RE_MSG_LINK_PATTERN", mock_pattern)

    result = _linkify_text("msg#", output_format="text")
    assert result == "msg#"

def test_apply_highlighting_no_term():
    assert _apply_highlighting("Hello", None) == "Hello"
    assert _apply_highlighting("Hello", "", escape_func=lambda x: x.upper()) == "HELLO"

def test_apply_highlighting_invalid_regex():
    assert _apply_highlighting("Hello", "[", is_regex=True) == "Hello"
    assert _apply_highlighting("Hello", "[", is_regex=True, escape_func=lambda x: x.upper()) == "HELLO"

def test_apply_highlighting_non_match_escape():
    result = _apply_highlighting("Hello world", "world", escape_func=lambda x: x.replace(" ", "_"))
    assert result == "Hello_world"

def test_parse_html_stray_closing_div(tmp_path):
    from pyqwk.core import _parse_html_messages
    content = '</div><div class="message"><strong>From:</strong> A<br><strong>To:</strong> B<br><strong>Subject:</strong> S<br><strong>Date:</strong> 01-01-24 12:00<br>Body</div>'
    html_path = tmp_path / "stray.html"
    html_path.write_text(content, encoding="utf-8")
    msgs = _parse_html_messages(str(html_path))
    assert len(msgs) == 1

def test_linkify_unknown_etype(mocker):
    mocker.patch("pyqwk.core._discover_entities", return_value=[(0, 5, "unknown", "Hello")])
    result = _linkify_text("Hello", output_format="text")
    assert result == "Hello"
