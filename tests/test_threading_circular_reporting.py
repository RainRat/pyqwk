from pyqwk.core import _parse_html_messages, _order_messages_by_thread, ProcessedMessage, MessageHeader
import logging

def test_parse_html_messages_depth_and_date_gaps(tmp_path):
    # Covers 1446-1447 (reply class), 1453 (depth decrease)
    html_content = """
    <div class="reply">
        <div class="message">
            <div class="header">
                <strong>Number:</strong> 1
                <strong>Date:</strong> 2024-05-05 12:00
            </div>
            <pre class="body">Body</pre>
        </div>
    </div>
    """
    f = tmp_path / "test_depth.html"
    f.write_text(html_content, encoding="utf-8")
    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].depth == 1

def test_parse_html_messages_date_gaps(tmp_path):
    """Test HTML date parsing with missing or incomplete date strings (Covers 1649-1652)."""
    # Note: _parse_html_messages uses a permissive regex for dates, allowing us to test
    # the parts-splitting logic for malformed inputs.
    html_content = """
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 1
            <strong>Date:</strong> 2024-05-05
        </div>
        <pre class="body">Body</pre>
    </div>
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 2
            <strong>Date:</strong>
        </div>
        <pre class="body">Body</pre>
    </div>
    """
    f = tmp_path / "test_html_date.html"
    f.write_text(html_content, encoding="utf-8")
    msgs = _parse_html_messages(str(f))
    assert msgs[0].header.msgdate == "2024-05-05"
    assert msgs[0].header.msgtime == "00:00"
    assert msgs[1].header.msgdate == "01-01-70"
    assert msgs[1].header.msgtime == "00:00"

def test_order_messages_by_thread_circular_reporting(caplog):
    def make_msg(num, ref, subj="Subj"):
        h = MessageHeader(" ", num, "01-01-24", "12:00", "To", "From", subj, "", ref, 1, " ", 1, 1, "")
        return ProcessedMessage("Body", num, ref, 1, h)

    msgs = [
        make_msg(1, 2),
        make_msg(2, 1),
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)

    assert "Conversation loop detected" in caplog.text
