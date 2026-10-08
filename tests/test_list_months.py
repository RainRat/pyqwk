import json
import logging
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    render_months_as_text,
    _render_months_html,
    _render_months_markdown,
    _render_months_csv,
    show_list_months,
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
    msgdate="10-12-23",
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


def test_render_months_as_text():
    month_list = [
        {
            "month": "1995-01",
            "message_count": 10,
            "authors_count": 3,
            "conferences_count": 2,
            "first_active": "1995-01-01 10:00",
            "last_active": "1995-01-31 18:00",
            "bbs_name": "Long BBS Name That Exceeds Width",
        },
        {
            "month": "2023-05",
            "message_count": 5,
            "authors_count": 2,
            "conferences_count": 1,
            "first_active": "2023-05-10 12:00",
            "last_active": "2023-05-10 12:00",
            "bbs_name": "Short BBS",
        },
    ]

    text_colored = render_months_as_text(month_list, use_colors=True)
    text_plain = render_months_as_text(month_list, use_colors=False)

    assert "Monthly Activity Summary" in text_colored
    assert "1995-01" in text_colored
    assert "2023-05" in text_colored
    assert "Total Months: 2" in text_colored

    assert "Monthly Activity Summary" in text_plain
    assert "1995-01" in text_plain
    assert "2023-05" in text_plain
    assert "Total Months: 2" in text_plain


def test_render_months_helpers():
    month_list = [
        {
            "month": "2023-05",
            "message_count": 5,
            "authors_count": 2,
            "conferences_count": 1,
            "first_active": "2023-05-10 12:00",
            "last_active": "2023-05-10 12:00",
            "bbs_name": "Test BBS",
        }
    ]

    html_out = _render_months_html(month_list, "Monthly Activity Summary")
    assert "<h1>Monthly Activity Summary</h1>" in html_out
    assert "<td>2023-05</td>" in html_out
    assert "<td>5</td>" in html_out

    md_out = _render_months_markdown(month_list, "Monthly Activity Summary")
    assert "# Monthly Activity Summary" in md_out
    assert "| 2023-05 | 5 | 2 | 1 | 2023-05-10 12:00 | 2023-05-10 12:00 | Test BBS |" in md_out

    csv_out = _render_months_csv(month_list)
    assert "month,message_count,authors_count,conferences_count,first_active,last_active,bbs_name" in csv_out
    assert "2023-05,5,2,1,2023-05-10 12:00,2023-05-10 12:00,Test BBS" in csv_out


def test_show_list_months_formats(mocker, tmp_path, base_settings):
    msg1 = create_sample_message(msgnum=1, msgdate="01-15-95", msgtime="10:00", author="Alice")
    msg2 = create_sample_message(msgnum=2, msgdate="01-20-95", msgtime="14:00", author="Bob")
    msg3 = create_sample_message(msgnum=3, msgdate="10-12-23", msgtime="12:00", author="Charlie")

    mocker.patch("pyqwk.core.load_data", return_value=([msg1, msg2, msg3], {101: "General"}))

    logger = logging.getLogger("test")

    # 1. Text format
    base_settings.format = "text"
    show_list_months(["dummy.qwk"], base_settings, logger)

    # 2. JSON format to file
    out_json = tmp_path / "months.json"
    base_settings.format = "json"
    base_settings.output_path = str(out_json)
    show_list_months(["dummy.qwk"], base_settings, logger)

    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["month"] == "1995-01"
    assert data[0]["message_count"] == 2
    assert data[1]["month"] == "2023-10"
    assert data[1]["message_count"] == 1

    # 3. JSONL format to file
    out_jsonl = tmp_path / "months.jsonl"
    base_settings.format = "jsonl"
    base_settings.output_path = str(out_jsonl)
    show_list_months(["dummy.qwk"], base_settings, logger)

    assert out_jsonl.exists()
    lines = out_jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed_line1 = json.loads(lines[0])
    assert parsed_line1["month"] == "1995-01"

    # 4. HTML format to file
    out_html = tmp_path / "months.html"
    base_settings.format = "html"
    base_settings.output_path = str(out_html)
    show_list_months(["dummy.qwk"], base_settings, logger)

    assert out_html.exists()
    assert "<td>1995-01</td>" in out_html.read_text(encoding="utf-8")

    # 5. Markdown format to file
    out_md = tmp_path / "months.md"
    base_settings.format = "markdown"
    base_settings.output_path = str(out_md)
    show_list_months(["dummy.qwk"], base_settings, logger)

    assert out_md.exists()
    assert "| 1995-01 | 2 |" in out_md.read_text(encoding="utf-8")

    # 6. CSV format to file
    out_csv = tmp_path / "months.csv"
    base_settings.format = "csv"
    base_settings.output_path = str(out_csv)
    show_list_months(["dummy.qwk"], base_settings, logger)

    assert out_csv.exists()
    assert "1995-01,2" in out_csv.read_text(encoding="utf-8")


def test_show_list_months_filtering_and_edge_cases(mocker, base_settings):
    msg1 = create_sample_message(msgnum=1, msgdate="01-15-95", author="Alice")
    msg_unknown_date = create_sample_message(msgnum=2, msgdate="invalid-date", author="Bob", bbs_name="")

    mocker.patch("pyqwk.core.load_data", return_value=([msg1, msg_unknown_date], {101: "General"}))

    logger = logging.getLogger("test")

    base_settings.format = "json"
    base_settings.output_path = None
    base_settings.authors = ["Alice"]

    # Test filtering by author Alice
    mocker.patch("builtins.print")
    show_list_months(["dummy.qwk"], base_settings, logger)

    # Empty archive
    mocker.patch("pyqwk.core.load_data", return_value=([], {}))
    warning_mock = mocker.patch.object(logger, "warning")
    show_list_months(["empty.qwk"], base_settings, logger)
    warning_mock.assert_called_with("No message months found.")

    # Archive load exception handling
    mocker.patch("pyqwk.core.load_data", side_effect=Exception("Corrupt archive"))
    error_mock = mocker.patch.object(logger, "error")
    show_list_months(["corrupt.qwk"], base_settings, logger)
    error_mock.assert_called()


def test_cli_list_months_flags(mocker, tmp_path):
    mocker.patch("sys.argv", ["qwk", "test.qwk", "--list-months"])
    mock_show = mocker.patch("pyqwk.cli.show_list_months")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert mock_show.called

    mocker.patch("sys.argv", ["qwk", "test.qwk", "--list-monthly"])
    mock_show_monthly = mocker.patch("pyqwk.cli.show_list_months")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert mock_show_monthly.called
