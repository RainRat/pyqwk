import pytest
from unittest.mock import MagicMock
from pyqwk.cli import _parse_msgnum_ranges
from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    show_list_emails,
    show_list_urls,
)


def test_show_list_urls_whitespace_match_handling(mocker, tmp_path):
    """Verify show_list_urls correctly skips empty or whitespace-only regex matches."""
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(
        text="Check this link https://example.com",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))
    mock_pattern = MagicMock()
    mock_pattern.findall.return_value = ["   ", ""]
    mocker.patch("pyqwk.core.RE_URL_PATTERN", mock_pattern)

    logger = MagicMock()
    output_file = tmp_path / "urls.txt"
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
        output_mode="file",
        output_path=str(output_file),
        encoding="utf-8",
    )

    show_list_urls(["dummy.qwk"], settings, logger)
    logger.warning.assert_called_once_with("No URLs found across messages.")


def test_show_list_emails_whitespace_match_handling(mocker, tmp_path):
    """Verify show_list_emails correctly skips empty or whitespace-only regex matches."""
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(
        text="Email me at user@example.com",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))
    mock_pattern = MagicMock()
    mock_pattern.findall.return_value = ["   ", ""]
    mocker.patch("pyqwk.core.RE_EMAIL_PATTERN", mock_pattern)

    logger = MagicMock()
    output_file = tmp_path / "emails.txt"
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
        output_mode="file",
        output_path=str(output_file),
        encoding="utf-8",
    )

    show_list_emails(["dummy.qwk"], settings, logger)
    logger.warning.assert_called_once_with("No email addresses found across messages.")


def test_parse_msgnum_ranges_invalid_range():
    """Verify _parse_msgnum_ranges raises ValueError when given an unparseable range string."""
    with pytest.raises(ValueError, match="Invalid message number range: 'invalid-range'"):
        _parse_msgnum_ranges("invalid-range")
