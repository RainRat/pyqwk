from pyqwk.core import _render_single_message_html, ParsedMessage, MessageHeader, _bytes_to_uue
import base64

def test_render_single_message_html_embed_images():
    header = MessageHeader(
        status="", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Recipient", msgfrom="Sender", msgsubject="Test Subject",
        msgpassword="", refnum=0, numblocks=1, msgflag="", confnum=1,
        lognum=1, nettag=""
    )

    # Needs to be at least 45 bytes to have a full UUE line if possible,
    # but more importantly, it needs to be valid UUE.
    png_data = b"fake-png-content-that-is-long-enough-for-uue"
    jpg_data = b"fake-jpg-content-that-is-long-enough-for-uue"
    gif_data = b"fake-gif-content-that-is-long-enough-for-uue"
    webp_data = b"fake-webp-content-that-is-long-enough-for-uue"

    uue_png = _bytes_to_uue(png_data, "image.png")
    uue_jpg = _bytes_to_uue(jpg_data, "image.jpg")
    uue_gif = _bytes_to_uue(gif_data, "image.gif")
    uue_webp = _bytes_to_uue(webp_data, "image.webp")

    text = f"Check these images:\n\n{uue_png}\n\n{uue_jpg}\n\n{uue_gif}\n\n{uue_webp}"

    msg = ParsedMessage(
        text=text,
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header,
        attachments=["image.png", "image.jpg", "image.gif", "image.webp"]
    )

    html_output = "\n".join(_render_single_message_html(msg, embed_attachments=True))

    assert 'src="data:image/png;base64,' in html_output
    assert base64.b64encode(png_data).decode("ascii") in html_output

    assert 'src="data:image/jpeg;base64,' in html_output
    assert base64.b64encode(jpg_data).decode("ascii") in html_output

    assert 'src="data:image/gif;base64,' in html_output
    assert base64.b64encode(gif_data).decode("ascii") in html_output

    assert 'src="data:image/webp;base64,' in html_output
    assert base64.b64encode(webp_data).decode("ascii") in html_output

def test_render_single_message_html_embed_original_text_priority():
    header = MessageHeader(
        status="", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Recipient", msgfrom="Sender", msgsubject="Test Subject",
        msgpassword="", refnum=0, numblocks=1, msgflag="", confnum=1,
        lognum=1, nettag=""
    )

    png_data = b"original-png-content-that-is-long-enough-for-uue"
    uue_png = _bytes_to_uue(png_data, "original.png")

    msg = ParsedMessage(
        text="Cleaned text",
        original_text=f"Original text with\n{uue_png}",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header,
        attachments=["original.png"]
    )

    html_output = "\n".join(_render_single_message_html(msg, embed_attachments=True))

    assert 'src="data:image/png;base64,' in html_output
    assert base64.b64encode(png_data).decode("ascii") in html_output
