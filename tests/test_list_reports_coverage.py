import os
import sys
import datetime
from unittest.mock import MagicMock

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    show_attachments,
    show_list_conferences,
    show_list_authors,
)


def make_header(msgnum, msgfrom, msgto, msgsubject, confnum, msgdate="01-15-2023", msgtime="10:00"):
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
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


def test_show_attachments_html_and_text_stdout(monkeypatch, tmp_path):
    hdr = make_header(1, "Alice", "All", "Check this file", 1)
    msg_text = "begin 644 test.png\n#0$5!\n`\nend\n"
    msg = ParsedMessage(
        text=msg_text,
        msgnum=1,
        refnum=None,
        confnum=1,
        header=hdr,
        confname="General",
        bbs_name="TestBBS",
        source_file="archive.qwk",
    )

    board_dict = {1: "General"}
    monkeypatch.setattr("pyqwk.core.load_data", lambda paths, settings, logger: ([msg], board_dict))

    logger = MagicMock()

    out_html = str(tmp_path / "attachments.html")
    settings_html = make_settings(format="html", output_path=out_html)
    show_attachments(["archive.qwk"], settings_html, logger)

    assert os.path.exists(out_html)
    with open(out_html, "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "<title>Archive Attachments</title>" in html_content
    assert "test.png" in html_content

    settings_text = make_settings(format="text", output_path=None)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    show_attachments(["archive.qwk"], settings_text, logger)


def test_show_list_conferences_all_formats(monkeypatch, tmp_path):
    hdr = make_header(1, "Alice", "All", "Subject 1", 10)
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=10,
        header=hdr,
        confname="Tech",
        bbs_name="TestBBS",
        source_file="archive.qwk",
    )

    board_dict = {10: "Tech"}
    monkeypatch.setattr("pyqwk.core.load_data", lambda paths, settings, logger: ([msg], board_dict))

    logger = MagicMock()

    out_html = str(tmp_path / "confs.html")
    settings_html = make_settings(format="html", output_path=out_html)
    show_list_conferences(["archive.qwk"], settings_html, logger)
    assert os.path.exists(out_html)
    with open(out_html, "r", encoding="utf-8") as f:
        assert "<title>Conference Areas</title>" in f.read()

    out_md = str(tmp_path / "confs.md")
    settings_md = make_settings(format="markdown", output_path=out_md)
    show_list_conferences(["archive.qwk"], settings_md, logger)
    assert os.path.exists(out_md)
    with open(out_md, "r", encoding="utf-8") as f:
        assert "# Conference Areas" in f.read()

    out_csv = str(tmp_path / "confs.csv")
    settings_csv = make_settings(format="csv", output_path=out_csv)
    show_list_conferences(["archive.qwk"], settings_csv, logger)
    assert os.path.exists(out_csv)
    with open(out_csv, "r", encoding="utf-8") as f:
        assert "number,name,message_count,bbs_name" in f.read()

    settings_text = make_settings(format="text", output_path=None)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    show_list_conferences(["archive.qwk"], settings_text, logger)


def test_show_list_authors_all_formats(monkeypatch, tmp_path):
    hdr = make_header(1, "Alice", "All", "Subject 1", 10, msgdate="01-15-2023", msgtime="10:00")
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=10,
        header=hdr,
        confname="Tech",
        bbs_name="TestBBS",
        source_file="archive.qwk",
    )
    msg.datetime = datetime.datetime(2023, 1, 15, 10, 0)

    board_dict = {10: "Tech"}
    monkeypatch.setattr("pyqwk.core.load_data", lambda paths, settings, logger: ([msg], board_dict))

    logger = MagicMock()

    out_html = str(tmp_path / "authors.html")
    settings_html = make_settings(format="html", output_path=out_html)
    show_list_authors(["archive.qwk"], settings_html, logger)
    assert os.path.exists(out_html)
    with open(out_html, "r", encoding="utf-8") as f:
        assert "<title>Message Authors</title>" in f.read()

    out_md = str(tmp_path / "authors.md")
    settings_md = make_settings(format="markdown", output_path=out_md)
    show_list_authors(["archive.qwk"], settings_md, logger)
    assert os.path.exists(out_md)
    with open(out_md, "r", encoding="utf-8") as f:
        assert "# Message Authors" in f.read()

    out_csv = str(tmp_path / "authors.csv")
    settings_csv = make_settings(format="csv", output_path=out_csv)
    show_list_authors(["archive.qwk"], settings_csv, logger)
    assert os.path.exists(out_csv)
    with open(out_csv, "r", encoding="utf-8") as f:
        assert "author,message_count,first_active,last_active,bbs_name" in f.read()

    settings_text = make_settings(format="text", output_path=None)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    show_list_authors(["archive.qwk"], settings_text, logger)
