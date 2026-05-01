import logging
from unittest.mock import patch
from pyqwk.core import calculate_archive_stats, ProcessingSettings, ParsedMessage, MessageHeader, ConferenceMap

def test_calculate_archive_stats_limit_break():
    logger = logging.getLogger("test")

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
        format='text',
        separator='none',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        limit=1,
        quiet=True
    )

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag=""
    )
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header
    )

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([msg], ConferenceMap())

        paths = ["archive1.qwk", "archive2.qwk"]
        stats = calculate_archive_stats(paths, settings, logger)

        assert stats["matching_messages"] == 1
        assert mock_load.call_count == 1
        mock_load.assert_called_once_with("archive1.qwk", logger, "cp437")
