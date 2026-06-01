import base64
import binascii
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    _render_single_message_html,
)

def _bytes_to_uue_raw(data: bytes, filename: str) -> str:
    lines = [f"begin 644 {filename}"]
    for i in range(0, len(data), 45):
        chunk = data[i : i + 45]
        lines.append(binascii.b2a_uu(chunk).decode("ascii").strip("\n"))
    lines.append("`")
    lines.append("end")
    return "\n".join(lines)

def test_render_single_message_html_embed_image_png():
    png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    uue_text = _bytes_to_uue_raw(png_data, "test.png")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    expected_b64 = base64.b64encode(png_data).decode("ascii")
    assert f'data:image/png;base64,{expected_b64}' in html_out
    assert 'alt="test.png"' in html_out

def test_render_single_message_html_embed_image_jpg():
    jpg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    uue_text = _bytes_to_uue_raw(jpg_data, "test.jpg")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    expected_b64 = base64.b64encode(jpg_data).decode("ascii")
    # JPG uses the default image/jpeg
    assert f'data:image/jpeg;base64,{expected_b64}' in html_out

def test_render_single_message_html_embed_image_multiple():
    png1 = b"fake-png-1"
    png2 = b"fake-png-2"
    uue_text = _bytes_to_uue_raw(png1, "1.png") + "\n" + _bytes_to_uue_raw(png2, "2.png")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    assert "data:image/png;base64," + base64.b64encode(png1).decode("ascii") in html_out
    assert "data:image/png;base64," + base64.b64encode(png2).decode("ascii") in html_out

def test_render_single_message_html_embed_skip_non_image():
    txt_data = b"Hello world"
    uue_text = _bytes_to_uue_raw(txt_data, "test.txt")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    assert "<img src=" not in html_out

def test_render_single_message_html_embed_with_original_text():
    png_data = b"image-in-original"
    uue_text = _bytes_to_uue_raw(png_data, "original.png")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    # text is clean, original_text has the UUE
    msg = ParsedMessage(text="Clean body", original_text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    assert "data:image/png;base64," + base64.b64encode(png_data).decode("ascii") in html_out

def test_render_single_message_html_embed_empty_text():
    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text="", original_text="", msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)
    assert "<img" not in html_out

def test_render_single_message_html_embed_webp_gif():
    # Testing other extensions in the mapping
    gif_data = b"GIF89a"
    webp_data = b"RIFF....WEBP"
    uue_text = _bytes_to_uue_raw(gif_data, "test.gif") + "\n" + _bytes_to_uue_raw(webp_data, "test.webp")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    assert "data:image/gif;base64," + base64.b64encode(gif_data).decode("ascii") in html_out
    assert "data:image/webp;base64," + base64.b64encode(webp_data).decode("ascii") in html_out
