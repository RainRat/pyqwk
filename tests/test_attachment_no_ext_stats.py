import pytest
from pyqwk.core import _compute_stats_from_messages, ParsedMessage, MessageHeader

def test_attachment_no_extension_stats():
    # Message with UUE attachment that has no extension
    body = "Hello\nbegin 644 noextension\n!\nend\n"

    msg = ParsedMessage(
        body,
        1,
        None,
        1,
        MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")
    )

    stats = _compute_stats_from_messages(iter([msg]))

    assert stats["attachments_count"] == 1

    # Check top attachments
    top_atts = {a["name"]: a["count"] for a in stats["top_attachments"]}
    assert "noextension" in top_atts
    assert top_atts["noextension"] == 1

    # Check top attachment types
    top_types = {t["extension"]: t["count"] for t in stats["top_attachment_types"]}
    assert "(no extension)" in top_types
    assert top_types["(no extension)"] == 1
