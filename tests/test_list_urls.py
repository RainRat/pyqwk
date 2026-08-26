import json
import logging
import pytest
from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    show_list_urls,
    render_urls_as_text,
    _render_urls_html,
    _render_urls_markdown,
    _render_urls_csv,
)
from pyqwk.cli import main


@pytest.fixture
def sample_messages_with_urls(tmp_path):
    msg1 = ParsedMessage(
        text="Check out https://example.com/page1 and http://python.org for updates.",
        msgnum=101,
        refnum=None,
        confnum=1,
        header=MessageHeader(
            status=" ",
            msgnum=101,
            msgdate="01-15-23",
            msgtime="10:00",
            msgto="All",
            msgfrom="Alice",
            msgsubject="Cool Links",
            msgpassword="",
            refnum=None,
            numblocks=1,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        ),
        confname="General",
        bbs_name="RetroBBS",
        bbs_id="RETRO",
        source_file="archive1.json",
    )

    msg2 = ParsedMessage(
        text="More info at https://example.com/page1 or http://gnu.org",
        msgnum=102,
        refnum=None,
        confnum=1,
        header=MessageHeader(
            status=" ",
            msgnum=102,
            msgdate="01-16-23",
            msgtime="11:30",
            msgto="Bob",
            msgfrom="Charlie",
            msgsubject="Re: Cool Links",
            msgpassword="",
            refnum=101,
            numblocks=1,
            msgflag=" ",
            confnum=1,
            lognum=0,
            nettag="",
        ),
        confname="General",
        bbs_name="RetroBBS",
        bbs_id="RETRO",
        source_file="archive1.json",
    )

    file_path = tmp_path / "urls_archive.json"
    data = {
        "type": "qwk_archive",
        "bbs_info": {
            "name": "RetroBBS",
            "bbs_id": "RETRO",
            "sysop": "Sysop",
        },
        "conferences": {"1": "General"},
        "messages": [
            {
                "text": msg1.text,
                "header": msg1.header.as_dict,
                "conference": "General",
                "bbs_name": "RetroBBS",
                "bbs_id": "RETRO",
                "source_file": "urls_archive.json",
            },
            {
                "text": msg2.text,
                "header": msg2.header.as_dict,
                "conference": "General",
                "bbs_name": "RetroBBS",
                "bbs_id": "RETRO",
                "source_file": "urls_archive.json",
            },
        ],
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    return str(file_path)


def test_render_urls_as_text():
    url_list = [
        {
            "url": "https://example.com/page1",
            "message_count": 2,
            "authors_count": 2,
            "first_active": "2023-01-15",
            "last_active": "2023-01-16",
            "bbs_name": "RetroBBS",
        }
    ]
    txt_no_color = render_urls_as_text(url_list, use_colors=False)
    assert "Extracted URLs" in txt_no_color
    assert "https://example.com/page1" in txt_no_color
    assert "Total Unique URLs: 1" in txt_no_color

    txt_color = render_urls_as_text(url_list, use_colors=True)
    assert "Extracted URLs" in txt_color


def test_render_urls_html_md_csv():
    url_list = [
        {
            "url": "https://example.com/page1",
            "message_count": 2,
            "authors_count": 2,
            "first_active": "2023-01-15",
            "last_active": "2023-01-16",
            "bbs_name": "RetroBBS",
        }
    ]
    html_out = _render_urls_html(url_list, "Extracted URLs")
    assert "<h1>Extracted URLs</h1>" in html_out
    assert "<a href='https://example.com/page1'>" in html_out

    md_out = _render_urls_markdown(url_list, "Extracted URLs")
    assert "# Extracted URLs" in md_out
    assert "[https://example.com/page1](https://example.com/page1)" in md_out

    csv_out = _render_urls_csv(url_list)
    assert "url,message_count,authors_count" in csv_out
    assert "https://example.com/page1,2,2" in csv_out


def test_show_list_urls_json_export(tmp_path, sample_messages_with_urls):
    out_file = tmp_path / "urls_out.json"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
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
        output_path=str(out_file),
        encoding="utf-8",
    )
    logger = logging.getLogger("test_show_list_urls")
    show_list_urls([sample_messages_with_urls], settings, logger)

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data) == 3
    urls = [d["url"] for d in data]
    assert "https://example.com/page1" in urls
    assert "http://python.org" in urls
    assert "http://gnu.org" in urls

    ex_data = next(d for d in data if d["url"] == "https://example.com/page1")
    assert ex_data["message_count"] == 2
    assert ex_data["authors_count"] == 2


def test_show_list_urls_no_matches(tmp_path, caplog):
    no_urls_path = tmp_path / "no_urls.json"
    data = [
        {
            "text": "Hello world without any web links.",
            "header": {
                "confnum": 1,
                "msgnum": 1,
                "msgdate": "01-01-23",
                "msgtime": "12:00",
                "msgfrom": "Alice",
                "msgto": "Bob",
                "msgsubject": "No Links",
                "status": " ",
            },
        }
    ]
    no_urls_path.write_text(json.dumps(data), encoding="utf-8")

    settings = ProcessingSettings(
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
        encoding="utf-8",
    )
    logger = logging.getLogger("test_no_urls")

    with caplog.at_level(logging.WARNING):
        show_list_urls([str(no_urls_path)], settings, logger)
    assert "No URLs found." in caplog.text


def test_cli_list_urls(mocker, tmp_path, sample_messages_with_urls):
    mocker.patch("sys.argv", ["qwk", sample_messages_with_urls, "--list-urls"])
    mock_exit = mocker.patch("sys.exit")

    main()

    mock_exit.assert_called_once_with(0)
