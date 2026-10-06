import json
import logging
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    render_days_as_text,
    _render_days_html,
    _render_days_markdown,
    _render_days_csv,
    show_list_days,
)
from pyqwk.cli import main


@pytest.fixture
def base_settings():
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
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )


def create_sample_message(
    msgnum=1,
    confnum=101,
    author="Alice",
    to="Bob",
    subject="Hello World",
    msgdate="10-12-23",  # Oct 12, 2023 is Thursday
    msgtime="12:00",
    bbs_name="Test BBS",
    source_file="archive1.qwk",
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
        text="Sample message text.",
        msgnum=msgnum,
        refnum=None,
        confnum=confnum,
        header=header,
        bbs_name=bbs_name,
        source_file=source_file,
    )


def test_render_days_functions():
    days = [
        {
            "day": "Thursday",
            "message_count": 10,
            "authors_count": 3,
            "conferences_count": 2,
            "first_active": "2023-10-12 08:05",
            "last_active": "2023-10-12 08:50",
            "bbs_name": "Digital Horizon BBS",
        },
        {
            "day": "Friday",
            "message_count": 5,
            "authors_count": 1,
            "conferences_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    text_colored = render_days_as_text(days, use_colors=True)
    assert "Day of Week Activity Summary" in text_colored
    assert "Thursday" in text_colored
    assert "Total Days: 2" in text_colored

    text_plain = render_days_as_text(days, use_colors=False)
    assert "=== Day of Week Activity Summary ===" in text_plain

    html_out = _render_days_html(days, "Day of Week Activity Summary")
    assert "<h1>Day of Week Activity Summary</h1>" in html_out
    assert "<td>Thursday</td>" in html_out

    md_out = _render_days_markdown(days, "Day of Week Activity Summary")
    assert "# Day of Week Activity Summary" in md_out
    assert "| Thursday | 10 | 3 | 2 |" in md_out

    csv_out = _render_days_csv(days)
    assert "day,message_count,authors_count,conferences_count" in csv_out
    assert "Thursday,10,3,2" in csv_out


def test_show_list_days_formats(tmp_path, monkeypatch, base_settings):
    logger = logging.getLogger("test_days")

    m1 = create_sample_message(msgnum=1, author="Alice", msgdate="10-12-23")  # Thursday
    m2 = create_sample_message(msgnum=2, author="Bob", msgdate="10-13-23")    # Friday

    def mock_load_data(input_path, logger, encoding="cp437"):
        from pyqwk.core import ConferenceMap, BBSInfo
        b_dict = ConferenceMap({101: "General"})
        b_dict.bbs_info = BBSInfo(name="Test BBS")
        return [m1, m2], b_dict

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)

    # 1. Text format to file
    out_txt = tmp_path / "days.txt"
    base_settings.output_path = str(out_txt)
    base_settings.format = "text"
    show_list_days(["dummy.qwk"], base_settings, logger)
    assert out_txt.exists()
    content = out_txt.read_text(encoding="utf-8")
    assert "Thursday" in content
    assert "Friday" in content

    # 2. JSON format
    out_json = tmp_path / "days.json"
    base_settings.output_path = str(out_json)
    base_settings.format = "json"
    show_list_days(["dummy.qwk"], base_settings, logger)
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["day"] in ("Thursday", "Friday")

    # 3. JSONL format
    out_jsonl = tmp_path / "days.jsonl"
    base_settings.output_path = str(out_jsonl)
    base_settings.format = "jsonl"
    show_list_days(["dummy.qwk"], base_settings, logger)
    lines = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2

    # 4. HTML format
    out_html = tmp_path / "days.html"
    base_settings.output_path = str(out_html)
    base_settings.format = "html"
    show_list_days(["dummy.qwk"], base_settings, logger)
    assert "<h1>Day of Week Activity Summary</h1>" in out_html.read_text(encoding="utf-8")

    # 5. Markdown format
    out_md = tmp_path / "days.md"
    base_settings.output_path = str(out_md)
    base_settings.format = "markdown"
    show_list_days(["dummy.qwk"], base_settings, logger)
    assert "# Day of Week Activity Summary" in out_md.read_text(encoding="utf-8")

    # 6. CSV format
    out_csv = tmp_path / "days.csv"
    base_settings.output_path = str(out_csv)
    base_settings.format = "csv"
    show_list_days(["dummy.qwk"], base_settings, logger)
    assert "day,message_count" in out_csv.read_text(encoding="utf-8")


def test_show_list_days_empty(monkeypatch, base_settings, caplog):
    logger = logging.getLogger("test_days_empty")

    def mock_load_data(input_path, logger, encoding="cp437"):
        from pyqwk.core import ConferenceMap
        return [], ConferenceMap()

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)

    with caplog.at_level(logging.WARNING):
        show_list_days(["dummy.qwk"], base_settings, logger)
    assert "No message days found." in caplog.text


def test_cli_list_days_flags(monkeypatch, tmp_path):
    out_json = tmp_path / "days_cli.json"
    test_args = [
        "qwk",
        "dummy.qwk",
        "--list-days",
        "-o",
        str(out_json),
        "--format",
        "json",
    ]

    m = create_sample_message(msgnum=1, msgdate="10-12-23")

    def mock_load_data(input_path, logger, encoding="cp437"):
        from pyqwk.core import ConferenceMap, BBSInfo
        b_dict = ConferenceMap({101: "General"})
        b_dict.bbs_info = BBSInfo(name="Test BBS")
        return [m], b_dict

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)
    monkeypatch.setattr("sys.argv", test_args)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data[0]["day"] == "Thursday"
