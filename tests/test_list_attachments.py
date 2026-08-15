import json
import os
import sys
import pytest
from unittest.mock import MagicMock

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    render_attachments_as_text,
    _render_attachments_html,
    _render_attachments_markdown,
    _render_attachments_csv,
    show_attachments,
)
from pyqwk.cli import main


def make_header(msgnum, msgfrom, msgto, msgsubject, confnum):
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-15-2023",
        msgtime="10:00",
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=confnum,
        lognum=1,
        nettag="",
    )


@pytest.fixture
def sample_messages_with_attachments():
    hdr1 = make_header(1, "Alice", "All", "Check this file", 1)
    msg1_text = (
        "Here is the image file:\n"
        "begin 644 test.png\n"
        "#0$5!\n"
        "`\n"
        "end\n"
    )
    msg1 = ParsedMessage(text=msg1_text, msgnum=1, refnum=None, confnum=1, header=hdr1, confname="General", bbs_name="TestBBS", source_file="archive1.qwk")

    hdr2 = make_header(2, "Charlie", "Bob", "Archive attached", 2)
    msg2_text = (
        "Here is a zip archive:\n"
        "begin 644 data.zip\n"
        "#0$5!\n"
        "`\n"
        "end\n"
    )
    msg2 = ParsedMessage(text=msg2_text, msgnum=2, refnum=None, confnum=2, header=hdr2, confname="Downloads", bbs_name="TestBBS", source_file="archive1.qwk")

    hdr3 = make_header(3, "Dave", "All", "No attachments here", 1)
    msg3 = ParsedMessage(text="Just plain text", msgnum=3, refnum=None, confnum=1, header=hdr3, confname="General", bbs_name="TestBBS", source_file="archive1.qwk")

    return [msg1, msg2, msg3]


def test_render_attachments_as_text():
    records = [
        {
            "filename": "test.png",
            "msgnum": 1,
            "author": "Alice",
            "conference": "General",
            "bbs_name": "TestBBS",
            "source_file": "archive1.qwk",
        }
    ]
    text = render_attachments_as_text(records, use_colors=False)
    assert "Archive Attachments:" in text
    assert "test.png" in text
    assert "Alice" in text
    assert "General" in text

    empty_text = render_attachments_as_text([], use_colors=False)
    assert "No attachments found" in empty_text


def test_render_attachments_html():
    records = [
        {
            "filename": "data.zip",
            "msgnum": 2,
            "author": "Charlie",
            "conference": "Downloads",
            "bbs_name": "TestBBS",
            "source_file": "archive1.qwk",
        }
    ]
    html_out = _render_attachments_html(records, "Archive Attachments")
    assert "<title>Archive Attachments</title>" in html_out
    assert "data.zip" in html_out
    assert "Charlie" in html_out
    assert "Downloads" in html_out


def test_render_attachments_markdown():
    records = [
        {
            "filename": "data.zip",
            "msgnum": 2,
            "author": "Charlie",
            "conference": "Downloads",
            "bbs_name": "TestBBS",
            "source_file": "archive1.qwk",
        }
    ]
    md_out = _render_attachments_markdown(records, "Archive Attachments")
    assert "# Archive Attachments" in md_out
    assert "| data.zip | 2 | Charlie | Downloads | TestBBS | archive1.qwk |" in md_out


def test_render_attachments_csv():
    records = [
        {
            "filename": "data.zip",
            "msgnum": 2,
            "author": "Charlie",
            "conference": "Downloads",
            "bbs_name": "TestBBS",
            "source_file": "archive1.qwk",
        }
    ]
    csv_out = _render_attachments_csv(records)
    assert '"filename","msgnum","author","conference","bbs_name","source_file"' in csv_out
    assert '"data.zip","2","Charlie","Downloads","TestBBS","archive1.qwk"' in csv_out


def make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=None,
        encoding="utf-8",
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def test_show_attachments_formats(mocker, tmp_path, sample_messages_with_attachments):
    board_dict = {1: "General", 2: "Downloads"}
    mocker.patch("pyqwk.core.load_data", return_value=(sample_messages_with_attachments, board_dict))

    logger = MagicMock()

    # Test JSON output
    out_json = str(tmp_path / "attachments.json")
    settings_json = make_settings(format="json", output_path=out_json)
    show_attachments(["dummy.qwk"], settings_json, logger)

    assert os.path.exists(out_json)
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2
    filenames = [item["filename"] for item in data]
    assert "data.zip" in filenames
    assert "test.png" in filenames

    # Test Markdown output
    out_md = str(tmp_path / "attachments.md")
    settings_md = make_settings(format="markdown", output_path=out_md)
    show_attachments(["dummy.qwk"], settings_md, logger)

    assert os.path.exists(out_md)
    with open(out_md, "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "# Archive Attachments" in md_text
    assert "test.png" in md_text
    assert "data.zip" in md_text


def test_show_attachments_filters(mocker, tmp_path, sample_messages_with_attachments):
    board_dict = {1: "General", 2: "Downloads"}
    mocker.patch("pyqwk.core.load_data", return_value=(sample_messages_with_attachments, board_dict))

    logger = MagicMock()

    # Filter by conference "General"
    out_csv = str(tmp_path / "filtered.csv")
    settings = make_settings(
        format="csv",
        conferences=["General"],
        output_path=out_csv,
    )
    show_attachments(["dummy.qwk"], settings, logger)

    with open(out_csv, "r", encoding="utf-8") as f:
        csv_text = f.read()

    assert "test.png" in csv_text
    assert "data.zip" not in csv_text


def test_cli_list_attachments(mocker, tmp_path, sample_messages_with_attachments):
    board_dict = {1: "General", 2: "Downloads"}
    mocker.patch("pyqwk.core.load_data", return_value=(sample_messages_with_attachments, board_dict))
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.path.isfile", return_value=True)

    dummy_qwk = str(tmp_path / "test.qwk")
    with open(dummy_qwk, "wb") as f:
        f.write(b"A" * 512)

    out_file = str(tmp_path / "out_attachments.json")

    test_args = ["qwk", dummy_qwk, "--list-attachments", "--format", "json", "-o", out_file]
    mocker.patch.object(sys, "argv", test_args)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2
