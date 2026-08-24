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
    show_list_subjects,
    render_subjects_as_text,
    _render_subjects_html,
    _render_subjects_markdown,
    _render_subjects_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_subject_data(message_factory):
    m1 = message_factory(1, 0, "Hello World", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Hello World", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Another Topic", confnum=2)
    m3.header.msgfrom = "Alice"
    m3.header.msgto = "Bob"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_subjects_formats():
    subject_list = [
        {
            "subject": "Extremely Long Subject Title That Will Be Truncated",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "subject": "Short Topic",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_subjects_as_text(subject_list, use_colors=False)
    assert "Message Subjects" in text_out
    assert "Extremely Long Subject Title T..." in text_out
    assert "Short Topic" in text_out
    assert "Total Subjects: 2" in text_out

    # Text format with colors
    text_color_out = render_subjects_as_text(subject_list, use_colors=True)
    assert "Message Subjects" in text_color_out
    assert "Total Subjects: 2" in text_color_out

    # HTML format
    html_out = _render_subjects_html(subject_list, "Test Subjects")
    assert "<h1>Test Subjects</h1>" in html_out
    assert "<td>Short Topic</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_subjects_markdown(subject_list, "Test Subjects")
    assert "# Test Subjects" in md_out
    assert "| Subject | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| Short Topic | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_subjects_csv(subject_list)
    assert "subject,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "Short Topic,5,1,,," in csv_out


def test_show_list_subjects_stdout(mock_subject_data):
    msgs, board = mock_subject_data

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

    logger = logging.getLogger("test_list_subjects")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_subjects(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            subjects_out = json.loads(output_content)

            assert len(subjects_out) == 2
            # Sorted by count descending: "Hello World" (2 msgs, 2 authors), "Another Topic" (1 msg, 1 author)
            assert subjects_out[0]["subject"] == "Hello World"
            assert subjects_out[0]["message_count"] == 2
            assert subjects_out[0]["authors_count"] == 2
            assert subjects_out[0]["first_active"] == "2024-01-01"
            assert subjects_out[0]["last_active"] == "2024-01-02"
            assert subjects_out[0]["bbs_name"] == "Vintage BBS"

            assert subjects_out[1]["subject"] == "Another Topic"
            assert subjects_out[1]["message_count"] == 1
            assert subjects_out[1]["authors_count"] == 1


def test_show_list_subjects_empty():
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
    logger = logging.getLogger("test_subjects_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_subjects(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No message subjects found.")


def test_cli_list_subjects_integration(tmp_path, mock_subject_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_subject_data

    test_args = ["qwk.py", str(test_file), "--list-subjects", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["subject"] == "Hello World"
                    assert output[0]["message_count"] == 2


def test_show_list_subjects_all_formats(mock_subject_data):
    msgs, board = mock_subject_data
    logger = logging.getLogger("test_subjects_all_formats")

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
                show_list_subjects(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "Hello World" in out
