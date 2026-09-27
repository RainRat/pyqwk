import json
import logging
import pytest
from dataclasses import fields
import pyqwk.core as core


def _make_settings(tmp_path=None, **kwargs):
    default_kwargs = {f.name: None for f in fields(core.ProcessingSettings)}
    default_kwargs["format"] = "jsonl"
    default_kwargs["encoding"] = "cp437"
    if tmp_path:
        default_kwargs["output_path"] = str(tmp_path / "output.jsonl")
    default_kwargs.update(kwargs)
    return core.ProcessingSettings(**default_kwargs)


def test_show_stats_jsonl(tmp_path):
    logger = logging.getLogger("test_jsonl")
    out_file = tmp_path / "stats.jsonl"
    settings = _make_settings(output_path=str(out_file))

    core.show_stats(["testdata/test1_qwk.zip"], settings, logger)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8").strip()
    assert content
    lines = content.splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["file"] == "testdata/test1_qwk.zip"
    assert data["total_messages"] == 1


def test_show_info_jsonl(tmp_path):
    logger = logging.getLogger("test_jsonl")
    out_file = tmp_path / "info.jsonl"
    settings = _make_settings(output_path=str(out_file))

    core.show_info(["testdata/test1_qwk.zip"], settings, logger)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8").strip()
    lines = content.splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["file"] == "testdata/test1_qwk.zip"


def test_show_validation_report_jsonl(tmp_path):
    logger = logging.getLogger("test_jsonl")
    out_file = tmp_path / "val.jsonl"
    settings = _make_settings(output_path=str(out_file))

    def dummy_validator(path, logger, encoding):
        return {
            "valid": True,
            "format": "qwk",
            "messages_count": 1,
            "errors": [],
            "warnings": [],
        }

    valid = core.show_validation_report(
        ["testdata/test1_qwk.zip"], settings, logger, validator=dummy_validator
    )
    assert valid is True
    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["valid"] is True


def test_show_threads_jsonl(tmp_path):
    logger = logging.getLogger("test_jsonl")
    out_file = tmp_path / "threads.jsonl"
    settings = _make_settings(output_path=str(out_file))

    core.show_threads(["testdata/test1_qwk.zip"], settings, logger)

    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert "thread_id" in data


def test_list_reports_jsonl(tmp_path):
    logger = logging.getLogger("test_jsonl")
    test_file = "testdata/test1_qwk.zip"

    list_funcs = [
        ("authors", core.show_list_authors),
        ("recipients", core.show_list_recipients),
        ("conferences", core.show_list_conferences),
        ("bbs", core.show_list_bbs),
        ("subjects", core.show_list_subjects),
        ("sources", core.show_list_sources),
        ("dates", core.show_list_dates),
        ("phones", core.show_list_phones),
        ("keywords", core.show_list_keywords),
    ]

    for name, func in list_funcs:
        out_file = tmp_path / f"{name}.jsonl"
        settings = _make_settings(output_path=str(out_file))
        func([test_file], settings, logger)
        assert out_file.exists(), f"Output file missing for {name}"
        content = out_file.read_text(encoding="utf-8").strip()
        assert content, f"Empty content for {name}"
        lines = content.splitlines()
        for line in lines:
            data = json.loads(line)
            assert isinstance(data, dict)


def test_remaining_list_reports_jsonl(tmp_path, monkeypatch):
    logger = logging.getLogger("test_jsonl")

    header = core.MessageHeader.from_dict({
        "status": " ",
        "msgnum": 1,
        "msgdate": "01-01-95",
        "msgtime": "10:00",
        "msgto": "All",
        "msgfrom": "Alice",
        "msgsubject": "Check http://example.com and user@test.com and msg #10",
        "confnum": 1,
        "numblocks": 1,
    })
    msg = core.ParsedMessage(
        text="Visit http://example.com or mail user@test.com or see msg #10",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header,
        source_file="test.qwk",
        bbs_name="TestBBS",
        attachments=["image.png"],
    )

    monkeypatch.setattr(core, "load_data", lambda path, logger, encoding: ([msg], core.ConferenceMap({1: "General"})))

    funcs = [
        ("attachments", core.show_attachments),
        ("urls", core.show_list_urls),
        ("emails", core.show_list_emails),
        ("domains", core.show_list_domains),
        ("msg_links", core.show_list_msg_links),
    ]

    for name, func in funcs:
        out_f = tmp_path / f"{name}.jsonl"
        s = _make_settings(output_path=str(out_f))
        func(["dummy.qwk"], s, logger)
        assert out_f.exists(), f"Output file missing for {name}"
        content = out_f.read_text(encoding="utf-8").strip()
        assert content, f"Empty content for {name}"
        for line in content.splitlines():
            data = json.loads(line)
            assert isinstance(data, dict)
