from pyqwk.core import _parse_html_messages

def test_parse_html_whitespace_date(tmp_path):
    content = '<div class="message"><strong>Date:</strong>   </div>'
    f = tmp_path / "whitespace_date.html"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"

def test_parse_html_single_part_date(tmp_path):
    content = '<div class="message"><strong>Date:</strong> 2024-05-20 </div>'
    f = tmp_path / "single_date.html"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "2024-05-20"
    assert msgs[0].header.msgtime == "00:00"
