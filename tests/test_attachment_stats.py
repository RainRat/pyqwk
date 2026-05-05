from pyqwk.core import (
    _compute_stats_from_messages,
    ParsedMessage,
    MessageHeader,
    render_stats_as_text,
    _render_stats_html,
    _render_stats_markdown,
)


def test_attachment_stats_calculation():
    # Message with 2 UUE attachments
    body1 = "Hello\nbegin 644 file1.txt\n!\nend\nbegin 644 file2.jpg\n!\nend\n"
    # Message with 1 UUE attachment (repeat of file1.txt)
    body2 = "Another\nbegin 644 file1.txt\n!\nend\n"
    # Message with no attachments
    body3 = "Plain text"

    msg1 = ParsedMessage(
        body1,
        1,
        None,
        1,
        MessageHeader(
            " ",
            1,
            "01-01-24",
            "12:00",
            "To",
            "From",
            "Subj",
            "",
            None,
            1,
            " ",
            1,
            0,
            "",
        ),
    )
    msg2 = ParsedMessage(
        body2,
        2,
        None,
        1,
        MessageHeader(
            " ",
            2,
            "01-01-24",
            "12:05",
            "To",
            "From",
            "Subj",
            "",
            None,
            1,
            " ",
            1,
            0,
            "",
        ),
    )
    msg3 = ParsedMessage(
        body3,
        3,
        None,
        1,
        MessageHeader(
            " ",
            3,
            "01-01-24",
            "12:10",
            "To",
            "From",
            "Subj",
            "",
            None,
            1,
            " ",
            1,
            0,
            "",
        ),
    )

    stats = _compute_stats_from_messages(iter([msg1, msg2, msg3]))

    assert stats["attachments_count"] == 3

    # Check top attachments
    top_atts = {a["name"]: a["count"] for a in stats["top_attachments"]}
    assert top_atts["file1.txt"] == 2
    assert top_atts["file2.jpg"] == 1

    # Check top attachment types
    top_types = {t["extension"]: t["count"] for t in stats["top_attachment_types"]}
    assert top_types[".txt"] == 2
    assert top_types[".jpg"] == 1


def test_attachment_stats_rendering():
    stats = {
        "file": "Test Archive",
        "total_messages": 10,
        "matching_messages": 10,
        "attachments_count": 5,
        "dates": {"earliest": "2024-01-01T12:00:00", "latest": "2024-01-01T13:00:00"},
        "private_count": 0,
        "reply_count": 0,
        "reply_rate": 0.0,
        "avg_message_length": 100.0,
        "year_distribution": {},
        "month_distribution": {},
        "authors": [],
        "recipients": [],
        "conferences": [],
        "subjects": [],
        "keywords": [],
        "day_of_week": {},
        "hour_of_day": {},
        "top_attachments": [
            {"name": "image.png", "count": 3},
            {"name": "doc.pdf", "count": 2},
        ],
        "top_attachment_types": [
            {"extension": ".png", "count": 3},
            {"extension": ".pdf", "count": 2},
        ],
    }

    # Text rendering
    text_report = render_stats_as_text(stats)
    assert "Top Attachments:" in text_report
    assert "image.png" in text_report
    assert "Top Attachment Types:" in text_report
    assert ".png" in text_report

    # HTML rendering
    html_report = "".join(_render_stats_html(stats))
    assert "<h3>Top Attachments</h3>" in html_report
    assert "image.png" in html_report

    # Markdown rendering
    md_report = "".join(_render_stats_markdown(stats))
    assert "#### Top Attachments" in md_report
    assert "image.png" in md_report
