import json
import logging
import os
import sys
from unittest.mock import patch

import pytest
from pyqwk.cli import main
from pyqwk.core import (
    ConferenceMap,
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    show_conferences,
)


def _create_sample_messages():
    hdr1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Hello General",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg1 = ParsedMessage(
        text="Hello world in General",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=hdr1,
        confname="General Chat",
        bbs_name="Test BBS",
    )

    hdr2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-02-24",
        msgtime="13:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Programming Topic",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=2,
        lognum=0,
        nettag="",
    )
    msg2 = ParsedMessage(
        text="Coding discussion",
        msgnum=2,
        refnum=None,
        confnum=2,
        header=hdr2,
        confname="Programming",
        bbs_name="Test BBS",
    )

    hdr3 = MessageHeader(
        status=" ",
        msgnum=3,
        msgdate="01-03-24",
        msgtime="14:00",
        msgto="All",
        msgfrom="Sysop",
        msgsubject="General Chat 2",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg3 = ParsedMessage(
        text="More in General",
        msgnum=3,
        refnum=None,
        confnum=1,
        header=hdr3,
        confname="General Chat",
        bbs_name="Test BBS",
    )

    board_dict = ConferenceMap({1: "General Chat", 2: "Programming"})
    return [msg1, msg2, msg3], board_dict


def test_show_conferences_text_format(tmp_path, mocker, capsys):
    msgs, board_dict = _create_sample_messages()
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board_dict))

    logger = logging.getLogger("test_conferences")
    settings = ProcessingSettings(
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
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8",
    )

    show_conferences(["fake.qwk"], settings, logger)
    captured = capsys.readouterr().out

    assert "Conferences List:" in captured
    assert "General Chat" in captured
    assert "Programming" in captured
    assert "2" in captured  # 2 messages in Conf 1


def test_show_conferences_json_format(tmp_path, mocker):
    msgs, board_dict = _create_sample_messages()
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board_dict))

    out_file = str(tmp_path / "confs.json")
    logger = logging.getLogger("test_conferences")
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="auto",
        output_mode="file",
        output_path=out_file,
        encoding="utf-8",
    )

    show_conferences(["fake.qwk"], settings, logger)

    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 2
    assert data[0]["number"] == 1
    assert data[0]["name"] == "General Chat"
    assert data[0]["message_count"] == 2
    assert data[1]["number"] == 2
    assert data[1]["name"] == "Programming"
    assert data[1]["message_count"] == 1


def test_show_conferences_html_and_markdown_format(tmp_path, mocker):
    msgs, board_dict = _create_sample_messages()
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board_dict))

    logger = logging.getLogger("test_conferences")

    # HTML
    html_file = str(tmp_path / "confs.html")
    settings_html = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="auto",
        output_mode="file",
        output_path=html_file,
        encoding="utf-8",
    )
    show_conferences(["fake.qwk"], settings_html, logger)
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "<h1>Conferences List</h1>" in html_content
    assert "General Chat" in html_content

    # Markdown
    md_file = str(tmp_path / "confs.md")
    settings_md = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="markdown",
        separator="auto",
        output_mode="file",
        output_path=md_file,
        encoding="utf-8",
    )
    show_conferences(["fake.qwk"], settings_md, logger)
    with open(md_file, "r", encoding="utf-8") as f:
        md_content = f.read()
    assert "# Conferences List" in md_content
    assert "| Conf # | Conference Name | Messages | BBS |" in md_content


def test_show_conferences_csv_format(tmp_path, mocker):
    msgs, board_dict = _create_sample_messages()
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board_dict))

    csv_file = str(tmp_path / "confs.csv")
    logger = logging.getLogger("test_conferences")
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="csv",
        separator="auto",
        output_mode="file",
        output_path=csv_file,
        encoding="utf-8",
    )
    show_conferences(["fake.qwk"], settings, logger)
    with open(csv_file, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert '"number","name","message_count","bbs_name"' in csv_content
    assert '"1","General Chat","2"' in csv_content


def test_show_conferences_cli(tmp_path, mocker, capsys):
    msgs, board_dict = _create_sample_messages()
    mocker.patch("pyqwk.cli.expand_paths", return_value=["test.qwk"])
    mocker.patch("pyqwk.core.load_data", return_value=(msgs, board_dict))

    test_args = ["qwk", "test.qwk", "--list-conferences"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    captured = capsys.readouterr().out
    assert "Conferences List:" in captured
    assert "General Chat" in captured
