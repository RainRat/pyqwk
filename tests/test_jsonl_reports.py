import json
import logging
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    show_info,
    show_stats,
    show_validation_report,
    show_threads,
    show_attachments,
    show_list_conferences,
    show_list_authors,
    show_list_recipients,
    show_list_bbs,
    show_list_subjects,
    show_list_urls,
    show_list_emails,
    show_list_domains,
    show_list_phones,
    show_list_keywords,
    show_list_msg_links,
    show_list_sources,
    show_list_dates,
    show_list_hours,
    show_list_years,
)
from pyqwk.cli import main


@pytest.fixture
def jsonl_settings(tmp_path):
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="jsonl",
        separator="auto",
        output_mode="file",
        output_path=str(tmp_path / "report.jsonl"),
        encoding="cp437",
    )


def create_sample_message(
    msgnum=1,
    confnum=101,
    author="Alice",
    to="Bob",
    subject="Hello World",
    msgdate="10-12-23",
    msgtime="12:00",
    bbs_name="Test BBS",
    source_file="archive1.qwk",
    text="Check out https://example.com and email user@domain.com or call 555-123-4567 regarding msg #1. beginner coding",
):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=to,
        msgfrom=author,
        msgsubject=subject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=1,
        nettag="",
    )
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=None,
        confnum=confnum,
        header=header,
        bbs_name=bbs_name,
        source_file=source_file,
    )


def test_show_info_jsonl(tmp_path, jsonl_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    msg = create_sample_message()
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {101: "General"}))

    show_info([str(tmp_path / "archive1.qwk")], jsonl_settings, logger)

    with open(jsonl_settings.output_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["file"] == str(tmp_path / "archive1.qwk")
    assert data["total_messages"] == 1


def test_show_stats_jsonl(tmp_path, jsonl_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    msg = create_sample_message()
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {101: "General"}))

    show_stats([str(tmp_path / "archive1.qwk")], jsonl_settings, logger)

    with open(jsonl_settings.output_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["total_messages"] == 1


def test_show_validation_report_jsonl(tmp_path, jsonl_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    val_res = {
        "valid": True,
        "format": "qwk",
        "messages_count": 5,
        "errors": [],
        "warnings": [],
    }
    mocker.patch("pyqwk.core.validate_archive", return_value=val_res)

    show_validation_report([str(tmp_path / "archive1.qwk")], jsonl_settings, logger)

    with open(jsonl_settings.output_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["valid"] is True
    assert data["format"] == "qwk"


def test_show_threads_jsonl(tmp_path, jsonl_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    msg = create_sample_message()
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {101: "General"}))

    show_threads([str(tmp_path / "archive1.qwk")], jsonl_settings, logger)

    with open(jsonl_settings.output_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["root_subject"] == "Hello World"


def test_show_attachments_jsonl(tmp_path, jsonl_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    msg = create_sample_message(text="Here is a file\nbegin 644 test.zip\nM123456\n`\nend\n")
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {101: "General"}))

    show_attachments([str(tmp_path / "archive1.qwk")], jsonl_settings, logger)

    with open(jsonl_settings.output_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["filename"] == "test.zip"


def test_show_list_reports_jsonl(tmp_path, jsonl_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    msg = create_sample_message()
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {101: "General"}))

    reports = [
        ("conferences", show_list_conferences),
        ("authors", show_list_authors),
        ("recipients", show_list_recipients),
        ("bbs", show_list_bbs),
        ("subjects", show_list_subjects),
        ("urls", show_list_urls),
        ("emails", show_list_emails),
        ("domains", show_list_domains),
        ("phones", show_list_phones),
        ("keywords", show_list_keywords),
        ("msg_links", show_list_msg_links),
        ("sources", show_list_sources),
        ("dates", show_list_dates),
        ("hours", show_list_hours),
        ("years", show_list_years),
    ]

    for name, func in reports:
        out_file = str(tmp_path / f"{name}.jsonl")
        jsonl_settings.output_path = out_file
        func([str(tmp_path / "archive1.qwk")], jsonl_settings, logger)

        with open(out_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) >= 1, f"Report {name} produced no lines"
        for line in lines:
            data = json.loads(line)
            assert isinstance(data, dict), f"Report {name} line is not a dict"


def test_cli_jsonl_flag(tmp_path, mocker):
    qwk_file = tmp_path / "test.qwk"
    qwk_file.write_bytes(b"\x00" * 128)

    mock_show = mocker.patch("pyqwk.cli.show_list_authors")

    mocker.patch("sys.argv", ["qwk", str(qwk_file), "--list-authors", "-J"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert mock_show.called
    settings = mock_show.call_args[0][1]
    assert settings.format == "jsonl"
