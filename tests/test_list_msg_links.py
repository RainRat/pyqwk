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
    show_list_msg_links,
    render_msg_links_as_text,
    _render_msg_links_html,
    _render_msg_links_markdown,
    _render_msg_links_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_msg_link_data(message_factory):
    m1 = message_factory(1, 0, "Subj 1", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Check out msg #101 or message #202 for details."
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Subj 2", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "Regarding msg #101, I agree!"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Subj 3", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "No message links in this post."
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_msg_links_formats():
    msg_link_list = [
        {
            "msg_link": "message #999999999999999999999999999999999999999999",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "msg_link": "msg #101",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Plain text colored & plain
    text_colored = render_msg_links_as_text(msg_link_list, use_colors=True)
    assert "=== Extracted Message Links ===" in text_colored
    assert "Total Message Links: 2" in text_colored

    text_plain = render_msg_links_as_text(msg_link_list, use_colors=False)
    assert "=== Extracted Message Links ===" in text_plain

    # HTML
    html_out = _render_msg_links_html(msg_link_list, "Extracted Message Links")
    assert "<h1>Extracted Message Links</h1>" in html_out
    assert "<td>msg #101</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown
    md_out = _render_msg_links_markdown(msg_link_list, "Extracted Message Links")
    assert "# Extracted Message Links" in md_out
    assert "| msg #101 |" in md_out

    # CSV
    csv_out = _render_msg_links_csv(msg_link_list)
    assert "msg_link,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "msg #101,5,1,,," in csv_out


def test_show_list_msg_links_formats(mock_msg_link_data, tmp_path):
    msgs, board = mock_msg_link_data
    logger = logging.getLogger("test")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        # JSON format
        json_file = tmp_path / "out.json"
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
            separator="\n---\n",
            output_mode="single",
            output_path=str(json_file),
            encoding="cp437",
        )
        show_list_msg_links(["dummy.qwk"], settings, logger)

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["msg_link"] == "msg #101"
        assert data[0]["message_count"] == 2

        # HTML format
        html_file = tmp_path / "out.html"
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
            format="html",
            separator="\n---\n",
            output_mode="single",
            output_path=str(html_file),
            encoding="cp437",
        )
        show_list_msg_links(["dummy.qwk"], settings, logger)
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<h1>Extracted Message Links</h1>" in content

        # Markdown format
        md_file = tmp_path / "out.md"
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
            format="markdown",
            separator="\n---\n",
            output_mode="single",
            output_path=str(md_file),
            encoding="cp437",
        )
        show_list_msg_links(["dummy.qwk"], settings, logger)
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# Extracted Message Links" in content

        # CSV format
        csv_file = tmp_path / "out.csv"
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
            separator="\n---\n",
            output_mode="single",
            output_path=str(csv_file),
            encoding="cp437",
        )
        show_list_msg_links(["dummy.qwk"], settings, logger)
        with open(csv_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "msg_link,message_count" in content


def test_show_list_msg_links_filters_and_branch_edge_cases(mock_msg_link_data, tmp_path):
    msgs, board = mock_msg_link_data
    logger = logging.getLogger("test")

    # Test when no message links are found
    m_no_links = msgs[2]
    with patch("pyqwk.core.load_data", return_value=([m_no_links], board)):
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
            separator="\n---\n",
            output_mode="single",
            output_path=None,
            encoding="cp437",
        )
        with patch.object(logger, "warning") as mock_warn:
            show_list_msg_links(["dummy.qwk"], settings, logger)
            mock_warn.assert_called_once_with("No message links found across messages.")

    # Test error handling when loading archive fails
    with patch("pyqwk.core.load_data", side_effect=ValueError("Corrupt archive")):
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
            separator="\n---\n",
            output_mode="single",
            output_path=None,
            encoding="cp437",
        )
        with patch.object(logger, "error") as mock_err:
            show_list_msg_links(["corrupt.qwk"], settings, logger)
            mock_err.assert_called_once()

    # Test filtering by conference
    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        csv_file = tmp_path / "out.csv"
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
            separator="\n---\n",
            output_mode="single",
            output_path=str(csv_file),
            encoding="cp437",
            conferences=["1"],
        )
        show_list_msg_links(["dummy.qwk"], settings, logger)
        with open(csv_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "msg #101" in content


def test_cli_list_msg_links_integration(tmp_path, mock_msg_link_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_msg_link_data

    test_args = ["qwk.py", str(test_file), "--list-msg-links", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["msg_link"] == "msg #101"
                    assert output[0]["message_count"] == 2

    # Alias test --list-message-links
    test_args_alias = ["qwk.py", str(test_file), "--list-message-links", "--format", "json"]

    with patch("sys.argv", test_args_alias):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
