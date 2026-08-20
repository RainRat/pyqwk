import logging
from unittest.mock import MagicMock
import pytest
from pyqwk.core import (
    ProcessingSettings,
    render_attachments_as_text,
    render_conferences_as_text,
    show_attachments,
    show_list_conferences,
    show_list_authors,
)


def make_settings(**kwargs):
    defaults = {
        "verbose": False,
        "private": False,
        "no_header": False,
        "truncate_signatures": False,
        "cut_quoting": False,
        "individual_files": False,
        "threaded": False,
        "binaries_removal": False,
        "redact_pii": False,
        "format": "text",
        "separator": "========================================",
        "output_mode": "stdout",
        "output_path": None,
        "encoding": "cp437",
    }
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def test_render_attachments_as_text_truncation():
    item = {
        "filename": "A" * 35,
        "msgnum": 100,
        "author": "B" * 25,
        "conference": "C" * 25,
        "bbs_name": "D" * 20,
        "source_file": "E" * 20,
    }
    output = render_attachments_as_text([item], use_colors=False)
    assert "A" * 27 + "..." in output
    assert "B" * 17 + "..." in output
    assert "C" * 17 + "..." in output
    assert "D" * 12 + "..." in output
    assert "E" * 12 + "..." in output


def test_render_conferences_as_text_truncation():
    conf = {
        "number": 1,
        "name": "X" * 35,
        "message_count": 5,
        "bbs_name": "Y" * 28,
    }
    output = render_conferences_as_text([conf], use_colors=False)
    assert "X" * 27 + "..." in output
    assert "Y" * 20 + "..." in output


def test_show_attachments_stdout_tty(mocker):
    mocker.patch("sys.stdout.isatty", return_value=True)
    mock_render = mocker.patch("pyqwk.core.render_attachments_as_text", return_value="attachments_text")
    mocker.patch("pyqwk.core._write_text_output")

    mocker.patch("pyqwk.core.load_data", return_value=([], {}))
    logger = logging.getLogger("test")

    settings = make_settings(format="text", output_path=None)
    show_attachments(["dummy.qwk"], settings, logger)

    assert mock_render.called
    _, kwargs = mock_render.call_args
    assert kwargs.get("use_colors") is True


def test_show_list_conferences_stdout_tty_and_formats(mocker):
    mocker.patch("sys.stdout.isatty", return_value=True)
    mocker.patch("pyqwk.core.load_data", return_value=([], {1: "General"}))
    mock_write = mocker.patch("pyqwk.core._write_text_output")
    mock_render_text = mocker.patch("pyqwk.core.render_conferences_as_text", return_value="conf_text")
    logger = logging.getLogger("test")

    # Test text format with stdout tty
    settings_text = make_settings(format="text", output_path=None)
    show_list_conferences(["dummy.qwk"], settings_text, logger)
    assert mock_render_text.called
    assert mock_render_text.call_args[1].get("use_colors") is True

    # Test html format
    settings_html = make_settings(format="html", output_path=None)
    show_list_conferences(["dummy.qwk"], settings_html, logger)
    assert mock_write.called

    # Test markdown format
    settings_md = make_settings(format="markdown", output_path=None)
    show_list_conferences(["dummy.qwk"], settings_md, logger)
    assert mock_write.called

    # Test csv format
    settings_csv = make_settings(format="csv", output_path=None)
    show_list_conferences(["dummy.qwk"], settings_csv, logger)
    assert mock_write.called


def test_show_list_authors_stdout_tty_and_formats(mocker):
    mocker.patch("sys.stdout.isatty", return_value=True)
    msg = MagicMock()
    msg.header.msgfrom = "Alice"
    msg.header.msgdate = "01-01-23"
    msg.header.msgtime = "12:00"
    msg.datetime = None
    msg.confnum = 1
    msg.confname = "General"
    msg.bbs_name = "TestBBS"
    msg.bbs_id = "TEST"
    msg.source_file = "dummy.qwk"

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))
    mocker.patch("pyqwk.core.matches_filters", return_value=True)
    mock_render_authors = mocker.patch("pyqwk.core.render_authors_as_text", return_value="authors_text")
    mock_write = mocker.patch("pyqwk.core._write_text_output")
    logger = logging.getLogger("test")

    # Test text format with stdout tty
    settings = make_settings(format="text", output_path=None)
    show_list_authors(["dummy.qwk"], settings, logger)
    assert mock_render_authors.called
    assert mock_render_authors.call_args[1].get("use_colors") is True

    # Test html format
    settings_html = make_settings(format="html", output_path=None)
    show_list_authors(["dummy.qwk"], settings_html, logger)
    assert mock_write.called

    # Test markdown format
    settings_md = make_settings(format="markdown", output_path=None)
    show_list_authors(["dummy.qwk"], settings_md, logger)
    assert mock_write.called

    # Test csv format
    settings_csv = make_settings(format="csv", output_path=None)
    show_list_authors(["dummy.qwk"], settings_csv, logger)
    assert mock_write.called
