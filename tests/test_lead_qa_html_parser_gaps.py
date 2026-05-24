from pyqwk.core import _parse_html_messages

def test_parse_html_extra_closing_div(tmp_path):
    """Test HTML parsing with an extra closing div and nested replies to close gaps."""
    content = """
    </div>
    <div class="reply">
        <div class="message">Msg 1</div>
    </div>
    <div class="message">Msg 2</div>
    <div class="other">
        <div class="message">Msg 3</div>
    </div>
    """
    f = tmp_path / "gaps.html"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_html_messages(str(f))
    # Msg 1 should be at depth 1 (inside reply div)
    # Msg 2 should be at depth 0 (after reply div was closed)
    # Msg 3 should be at depth 0 (inside other div, not reply)
    assert len(msgs) == 3
    assert msgs[0].depth == 1
    assert msgs[1].depth == 0
    assert msgs[2].depth == 0

def test_parse_html_empty_date_parts(tmp_path):
    """Test HTML parsing with an empty date string to exercise parts-splitting branch coverage."""
    # Permissive HTML regex captures the empty date string between tags.
    content = '<div class="message"><strong>Date:</strong>   </div>'
    f = tmp_path / "empty_date.html"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 1
    # parts will be [] so msg_date and msg_time should remain default
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

def test_parse_html_comprehensive_headers(tmp_path):
    """Test HTML parsing with all headers present to increase coverage."""
    content = """
    <div class="message">
        <div class="header">
            <strong>From:</strong> User A</div>
            <strong>To:</strong> User B</div>
            <strong>Subject:</strong> Topic</div>
            <strong>Conference:</strong> Support (10)</div>
            <strong>BBS:</strong> EliteBBS</div>
            <strong>Number:</strong> 456</div>
            <strong>Date:</strong> 2024-06-01 10:00</div>
            <strong>Attachments:</strong> image.png, document.pdf</div>
            <strong>Source:</strong> archive.qwk</div>
        </div>
        <pre class="body">Hello world</pre>
    </div>
    <div class="message">
        <div class="header">
            <strong>Attachments:</strong> </div>
        </div>
        <pre class="body">Empty attachment list</pre>
    </div>
    """
    f = tmp_path / "comprehensive.html"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 2
    assert msgs[0].header.msgfrom == "User A"
    assert msgs[0].header.msgto == "User B"
    assert msgs[0].header.msgsubject == "Topic"
    assert msgs[0].confname == "Support"
    assert msgs[0].confnum == 10
    assert msgs[0].bbs_name == "EliteBBS"
    assert msgs[0].msgnum == 456
    assert msgs[0].header.msgdate == "2024-06-01"
    assert msgs[0].header.msgtime == "10:00"
    assert msgs[0].attachments == ["image.png", "document.pdf"]
    assert msgs[0].source_file == "archive.qwk"

    assert msgs[1].attachments is None
