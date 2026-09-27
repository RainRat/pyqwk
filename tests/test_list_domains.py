import pytest
import json
import io
import logging
import datetime
from unittest.mock import patch

from pyqwk.core import (
    ConferenceMap,
    BBSInfo,
    ProcessingSettings,
    extract_domains_from_text,
    render_domains_as_text,
    _render_domains_html,
    _render_domains_markdown,
    _render_domains_csv,
    show_list_domains,
)
from pyqwk.cli import main


def test_extract_domains_from_text():
    assert extract_domains_from_text("") == []
    assert extract_domains_from_text(None) == []

    text = (
        "Email alice@example.com or support@bbs.org. "
        "Visit https://www.google.com/search?q=test and http://files.bbs.net:8080/dir. "
        "Check ftp://ftp.debian.org/debian."
    )
    domains = extract_domains_from_text(text)
    assert "example.com" in domains
    assert "bbs.org" in domains
    assert "www.google.com" in domains
    assert "files.bbs.net" in domains
    assert "ftp.debian.org" in domains


@pytest.fixture
def mock_domain_data(message_factory):
    m1 = message_factory(1, 0, "Subj 1", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Contact me at alice@example.com or visit https://www.example.com/page"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Subj 2", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "Check http://bbs.org and email support@bbs.org"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Subj 3", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "No domain references here."
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_domains_formats():
    domain_list = [
        {
            "domain": "extremely-long-domain-name-for-testing-format.com",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "domain": "bbs.org",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_domains_as_text(domain_list, use_colors=False)
    assert "Extracted Domains" in text_out
    assert "extremely-long-domain-nam..." in text_out
    assert "bbs.org" in text_out
    assert "Total Domains: 2" in text_out

    # Text format with colors
    text_color_out = render_domains_as_text(domain_list, use_colors=True)
    assert "Extracted Domains" in text_color_out
    assert "Total Domains: 2" in text_color_out

    # HTML format
    html_out = _render_domains_html(domain_list, "Test Domains")
    assert "<h1>Test Domains</h1>" in html_out
    assert "<td>bbs.org</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_domains_markdown(domain_list, "Test Domains")
    assert "# Test Domains" in md_out
    assert "| Domain | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| bbs.org | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_domains_csv(domain_list)
    assert "domain,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "bbs.org,5,1,,," in csv_out


def test_show_list_domains_stdout(mock_domain_data):
    msgs, board = mock_domain_data

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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    logger = logging.getLogger("test_list_domains")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_domains(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            domains_out = json.loads(output_content)

            assert len(domains_out) >= 3
            domains_map = {d["domain"]: d for d in domains_out}
            assert "example.com" in domains_map
            assert "www.example.com" in domains_map
            assert "bbs.org" in domains_map

            assert domains_map["example.com"]["message_count"] == 1
            assert domains_map["example.com"]["bbs_name"] == "Vintage BBS"


def test_show_list_domains_empty():
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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_domains_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_domains(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No domain names found across messages.")


def test_cli_list_domains_integration(tmp_path, mock_domain_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_domain_data

    test_args = ["qwk.py", str(test_file), "--list-domains", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) >= 3


def test_show_list_domains_all_formats(mock_domain_data):
    msgs, board = mock_domain_data
    logger = logging.getLogger("test_domains_all_formats")

    for fmt in ["html", "markdown", "csv", "text"]:
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
            format=fmt,
            separator="none",
            output_mode="stdout",
            output_path=None,
            encoding="cp437",
            quiet=True,
        )

        with patch("pyqwk.core.load_data", return_value=(msgs, board)):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_domains(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "example.com" in out


def test_show_list_domains_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "Write to user@example.org or visit http://example.org"
    board_map = ConferenceMap()

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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_domains_bytes")

    short_bytes = b"short"
    long_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "short.qwk":
            return short_bytes, board_map
        if path == "long.qwk":
            return long_bytes, board_map
        return [m], board_map

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_domains(
                    ["short.qwk", "long.qwk", "valid.json"], settings, logger
                )
                mock_write.assert_called_once()


def test_show_list_domains_edge_cases(message_factory):
    m1 = message_factory(1, 0, "Subj 1")
    m1.header.msgdate = "INVALID-DATE"
    m1.header.msgtime = "INVALID-TIME"
    m1.datetime = None
    m1.text = "Write to user@example.org and http://example.org"
    m1.bbs_name = None
    m1.bbs_id = None

    board = ConferenceMap()

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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_domains_edge_cases")

    with patch("pyqwk.core.load_data", return_value=([m1], board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            with patch("pyqwk.core._parse_qwk_date", return_value=None):
                show_list_domains(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = json.loads(mock_write.call_args[0][0])
                assert len(out) == 1
                assert out[0]["domain"] == "example.org"
                assert out[0]["message_count"] == 2
                assert out[0]["first_active"] is None
                assert out[0]["last_active"] is None
                assert out[0]["bbs_name"] == "Unknown"


def test_extract_domains_from_text_schemeless_url_prepending():
    res = extract_domains_from_text("Visit www.domain.com/path for info")
    assert "www.domain.com" in res


def test_extract_domains_from_text_urlparse_exception_returns_empty():
    with patch("urllib.parse.urlparse", side_effect=Exception("parse error")):
        res_err = extract_domains_from_text("Visit http://example.com/path")
        assert res_err == []


def test_show_list_domains_filters_whitespace_domains(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "Valid domain example.com"
    board = ConferenceMap()

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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_domains_whitespace")

    with patch("pyqwk.core.extract_domains_from_text", return_value=["   ", "example.com"]):
        with patch("pyqwk.core.load_data", return_value=([m], board)):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_domains(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = json.loads(mock_write.call_args[0][0])
                assert len(out) == 1
                assert out[0]["domain"] == "example.com"
