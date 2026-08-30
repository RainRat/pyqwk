from unittest.mock import MagicMock, patch
import pyqwk.core as core


def test_show_list_urls_and_emails_empty_matches_coverage(capsys):
    msg = MagicMock()
    msg.text = "sample message text"
    msg.header.msgdate = "01-01-24"
    msg.header.msgtime = "12:00"
    msg.header.msgfrom = "Tester"
    msg.bbs_name = "TestBBS"
    msg.bbs_id = "TEST"

    fake_url_pattern = MagicMock()
    fake_url_pattern.findall.return_value = ["   ", "http://example.com"]

    fake_email_pattern = MagicMock()
    fake_email_pattern.findall.return_value = ["   ", "user@example.com"]

    logger = MagicMock()
    settings = MagicMock()
    settings.my_name = None
    settings.conferences = None
    settings.exclude_conferences = None
    settings.output_path = None
    settings.output_mode = "text"
    settings.no_header = False

    with patch("pyqwk.core.load_data", return_value=([msg], {})):
        with patch("pyqwk.core.matches_filters", return_value=True):
            with patch("pyqwk.core.RE_URL_PATTERN", fake_url_pattern):
                core.show_list_urls(["dummy.qwk"], settings, logger)
            with patch("pyqwk.core.RE_EMAIL_PATTERN", fake_email_pattern):
                core.show_list_emails(["dummy.qwk"], settings, logger)

    captured = capsys.readouterr()
    assert "http://example.com" in captured.out
    assert "user@example.com" in captured.out
