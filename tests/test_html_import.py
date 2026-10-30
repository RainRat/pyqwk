import base64
import binascii
import os
import logging
import unittest.mock
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    ProcessingSettings,
    load_data,
    expand_paths,
    _render_single_message_html,
    _parse_html_messages,
)


def test_html_import_roundtrip(tmp_path):
    """Test that messages exported to HTML can be imported back correctly."""
    output_html = tmp_path / "test.html"

    # Setup test messages
    h1 = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="05-20-23",
        msgtime="14:30",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Hello HTML",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg1 = ParsedMessage(
        text="This is a test message body.",
        msgnum=101,
        refnum=None,
        confnum=1,
        header=h1,
        confname="General",
        bbs_name="TestBBS",
        source_file="original.qwk",
    )

    h2 = MessageHeader(
        status=" ",
        msgnum=102,
        msgdate="05-20-23",
        msgtime="14:35",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Re: Hello HTML",
        msgpassword="",
        refnum=101,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=2,
        nettag="",
    )
    # Child message for threading
    msg2 = ParsedMessage(
        text="This is a reply.",
        msgnum=102,
        refnum=101,
        confnum=1,
        header=h2,
        confname="General",
        bbs_name="TestBBS",
        source_file="original.qwk",
        depth=1,
    )

    messages = [msg1, msg2]

    # 1. Export to HTML
    settings_export = ProcessingSettings(
        verbose=True,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        merge=True,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="none",
        output_mode="file",
        output_path=str(output_html),
        encoding="utf-8",
        include_toc=True,
        quiet=True,
    )

    mock_logger = unittest.mock.MagicMock()

    # We need to mock load_data to return our test messages during process_merged_files
    with unittest.mock.patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (messages, {1: "General"})
        process_merged_files(["fake.qwk"], settings_export, mock_logger)

    assert os.path.exists(output_html)

    # 2. Import back from HTML
    logger = logging.getLogger("test")
    imported_messages, board_dict = load_data(str(output_html), logger)

    assert len(imported_messages) == 2

    # Check Message 1
    im1 = imported_messages[0]
    assert im1.msgnum == 101
    assert im1.header.msgfrom == "Bob"
    assert im1.header.msgto == "Alice"
    assert im1.header.msgsubject == "Hello HTML"
    assert im1.confnum == 1
    assert im1.confname == "General"
    assert im1.bbs_name == "TestBBS"
    assert "test message body" in im1.text
    assert im1.depth == 0

    # Check Message 2
    im2 = imported_messages[1]
    assert im2.msgnum == 102
    assert im2.header.msgfrom == "Alice"
    assert im2.header.msgto == "Bob"
    assert im2.header.msgsubject == "Re: Hello HTML"
    assert im2.depth == 1
    assert "reply" in im2.text


def test_html_individual_files_import(tmp_path):
    """Test importing from a directory of individual HTML message files."""
    output_dir = tmp_path / "individual"
    output_dir.mkdir()

    h1 = MessageHeader(
        status=" ",
        msgnum=50,
        msgdate="01-01-23",
        msgtime="10:00",
        msgto="All",
        msgfrom="Sysop",
        msgsubject="Welcome",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=0,
        lognum=1,
        nettag="",
    )
    msg1 = ParsedMessage(
        text="Welcome to the BBS",
        msgnum=50,
        refnum=None,
        confnum=0,
        header=h1,
        confname="Public",
        bbs_name="MyBBS",
    )

    settings_export = ProcessingSettings(
        verbose=True,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        merge=False,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="none",
        output_mode="file",
        output_path=str(output_dir),
        encoding="utf-8",
        quiet=True,
    )

    mock_logger = unittest.mock.MagicMock()

    with unittest.mock.patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([msg1], {0: "Public"})
        process_merged_files(["fake.qwk"], settings_export, mock_logger)

    # Find the generated HTML file (ignoring index.html)
    html_files = [
        f for f in os.listdir(output_dir) if f.endswith(".html") and f != "index.html"
    ]
    assert len(html_files) == 1
    msg_file_path = output_dir / html_files[0]

    # Import it back
    imported, _ = load_data(str(msg_file_path), mock_logger)
    assert len(imported) == 1
    assert imported[0].msgnum == 50
    assert imported[0].header.msgsubject == "Welcome"
    assert imported[0].bbs_name == "MyBBS"
    assert "Welcome to the BBS" in imported[0].text


def test_expand_paths_html():
    """Verify that expand_paths finds .html and .htm files."""
    with unittest.mock.patch("os.path.isdir", return_value=True):
        with unittest.mock.patch("os.walk") as mock_walk:
            mock_walk.return_value = [
                ("/fake", ("subdir",), ("msg1.html", "msg2.htm", "other.exe")),
            ]
            found = expand_paths(["/fake"])
            assert "/fake/msg1.html" in found
            assert "/fake/msg2.htm" in found
            assert "/fake/other.exe" not in found


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
    gif_data = b"GIF89a"
    webp_data = b"RIFF....WEBP"
    uue_text = _bytes_to_uue_raw(gif_data, "test.gif") + "\n" + _bytes_to_uue_raw(webp_data, "test.webp")

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage(text=uue_text, msgnum=1, refnum=None, confnum=1, header=h)

    parts = _render_single_message_html(msg, embed_attachments=True)
    html_out = "".join(parts)

    assert "data:image/gif;base64," + base64.b64encode(gif_data).decode("ascii") in html_out
    assert "data:image/webp;base64," + base64.b64encode(webp_data).decode("ascii") in html_out


def test_parse_html_extra_closing_div(tmp_path):
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
    assert len(msgs) == 3
    assert msgs[0].depth == 1
    assert msgs[1].depth == 0
    assert msgs[2].depth == 0


def test_parse_html_empty_date_parts(tmp_path):
    content = '<div class="message"><strong>Date:</strong>   </div>'
    f = tmp_path / "empty_date.html"
    f.write_text(content, encoding="utf-8")

    msgs = _parse_html_messages(str(f))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"
    assert msgs[0].header.msgtime == "00:00"


def test_parse_html_comprehensive_headers(tmp_path):
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
