import pytest
import logging
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    _parse_html_messages,
    load_data,
    _render_stats_html,
    _render_stats_markdown,
    _compute_stats_from_messages,
    _order_messages_by_thread,
    ParsedMessage,
    MessageHeader,
)


def test_parse_html_messages_complex_nesting(tmp_path):
    html_content = """
    <div class="reply">
        <div class="message" id="msg-0">
            <div class="header">
                <div><strong>Number:</strong> 1</div>
                <div><strong>Date:</strong> 01-01-23 10:00</div>
                <div><strong>From:</strong> Alice</div>
                <div><strong>To:</strong> Bob</div>
                <div><strong>Subject:</strong> Test</div>
                <div><strong>Conference:</strong> General (1)</div>
                <div><strong>Attachments:</strong> file1.txt, file2.txt</div>
            </div>
            <pre class="body">Hello world</pre>
            <div class="reply">
                <div class="message" id="msg-1">
                    <div class="header">
                        <div><strong>Number:</strong> 2</div>
                    </div>
                    <pre class="body">Nested reply</pre>
                </div>
            </div>
            <div class="message" id="msg-2">
                <div class="header">
                    <div><strong>Number:</strong> 3</div>
                </div>
                <pre class="body">Back to depth 1</pre>
            </div>
        </div>
    </div>
    """
    html_file = tmp_path / "test.html"
    html_file.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_file))

    assert len(messages) == 3
    assert messages[0].depth == 1
    assert messages[1].depth == 2
    assert messages[2].depth == 1


def test_parse_html_messages_edge_cases(tmp_path):
    html_content = """
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 1</div>
            <strong>Date:</strong></div>
        <pre class="body">Body 1</pre>
    </div>
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 2</div>
            <strong>Date:</strong> 05-20-23</div>
        <pre class="body">Body 2</pre>
    </div>
    """
    html_file = tmp_path / "edge.html"
    # Using open with utf-8 as the code does
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 2


def test_parse_html_messages_coverage_boost(tmp_path):
    html_content = """
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 1 </div>
            <strong>Date:</strong> </div>
        <pre class="body">Body</pre>
    </div>
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 2 </div>
            <strong>Date:</strong> 05-20-23 </div>
        <pre class="body">Body</pre>
    </div>
    <div class="message">
        <div class="header">
            <strong>Number:</strong> 3 </div>
            <strong>Date:</strong> 05-20-23 10:00 </div>
    </div>
    """
    html_file = tmp_path / "boost.html"
    html_file.write_text(html_content, encoding="utf-8")
    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 3
    assert messages[0].header.msgdate == "01-01-70"
    assert messages[1].header.msgdate == "05-20-23"
    assert messages[1].header.msgtime == "00:00"
    assert messages[2].text == ""


def test_load_data_html_error(tmp_path):
    html_file = tmp_path / "bad.html"
    html_file.write_text("just some text", encoding="utf-8")

    logger = logging.getLogger("test")
    with patch("pyqwk.core._parse_html_messages", side_effect=Exception("BOOM")):
        with pytest.raises(ValueError, match="Failed to load HTML archive: BOOM"):
            load_data(str(html_file), logger)


def test_render_stats_empty_fields():
    stats = _compute_stats_from_messages([])

    html_parts = _render_stats_html(stats)
    html_str = "".join(html_parts)
    assert "Date Range:" not in html_str

    md_parts = _render_stats_markdown(stats)
    md_str = "".join(md_parts)
    assert "Date Range:" not in md_str


def test_order_messages_by_thread_circular_reference_complex():
    def make_msg(num, ref):
        h = MessageHeader(
            status=" ",
            msgnum=num,
            msgdate="01-01-23",
            msgtime="10:00",
            msgto="All",
            msgfrom="User",
            msgsubject="Cycle",
            msgpassword="",
            refnum=ref,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=num,
            nettag="",
        )
        return ParsedMessage(text=str(num), msgnum=num, refnum=ref, confnum=1, header=h)

    messages = [make_msg(1, 3), make_msg(2, 1), make_msg(3, 2), make_msg(4, 1)]

    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        _order_messages_by_thread(messages)

    assert any(
        "Conversation loop detected" in call[0][0]
        for call in mock_logger.warning.call_args_list
    )


def test_parse_html_messages_stack_empty_div(tmp_path):
    html_content = """
    </div>
    <div class="message" id="msg-0">
        <div class="header"><strong>Number:</strong> 1 </div>
    </div>
    """
    html_file = tmp_path / "stack_empty.html"
    html_file.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 1
    assert messages[0].depth == 0
