from pyqwk.core import _parse_text_messages

def test_parse_text_messages_preserves_body_with_fake_headers(tmp_path):
    """Verify that text resembling headers within the body is not consumed as a header."""
    content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Real Subject\n"
        "\n"
        "This is the first line of body.\n"
        "BBS: Fake header in body.\n"
        "This is the last line of body."
    )
    txt_file = tmp_path / "bug_repro.txt"
    txt_file.write_text(content)

    messages = _parse_text_messages(str(txt_file))
    assert len(messages) == 1
    # The bug causes 'This is the first line of body.' to be lost.
    assert "This is the first line of body." in messages[0].text
    assert "BBS: Fake header in body." in messages[0].text
