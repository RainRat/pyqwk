import logging
from unittest.mock import patch

import pyqwk.core
from pyqwk.core import (
    ConferenceMap,
    MessageHeader,
    ProcessedMessage,
    ProcessingSettings,
    show_list_emails,
    show_list_urls,
)


def test_show_list_urls_and_emails_whitespace_matches_coverage():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject="Subj",
        msgpassword="",
        refnum=0,
        numblocks=None,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ProcessedMessage(
        text="http://example.org test@example.com",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header,
    )
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
    logger = logging.getLogger("test_whitespace_matches")

    class MockPattern:
        def findall(self, text):
            return ["   "]

    with patch("pyqwk.core.load_data", return_value=([msg], ConferenceMap())):
        with patch.object(pyqwk.core, "RE_URL_PATTERN", MockPattern()):
            with patch("logging.Logger.warning") as mock_warn:
                show_list_urls(["dummy.qwk"], settings, logger)
                mock_warn.assert_called_with("No URLs found across messages.")

    with patch("pyqwk.core.load_data", return_value=([msg], ConferenceMap())):
        with patch.object(pyqwk.core, "RE_EMAIL_PATTERN", MockPattern()):
            with patch("logging.Logger.warning") as mock_warn:
                show_list_emails(["dummy.qwk"], settings, logger)
                mock_warn.assert_called_with("No email addresses found across messages.")
