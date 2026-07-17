import pytest
import sys
from unittest.mock import patch
from pyqwk.core import ProcessingSettings, matches_filters, ParsedMessage, MessageHeader
from pyqwk.cli import main


def message_with_ref(refnum, msgnum=1):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=refnum,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text="Body", msgnum=msgnum, refnum=refnum, confnum=1, header=header
    )


def test_refnum_filtering_matches():
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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        refnum_filters={42, 100, 101, 102},
    )

    allowed_confs = {1}

    assert matches_filters(message_with_ref(42), settings, allowed_confs) is True
    assert matches_filters(message_with_ref(101), settings, allowed_confs) is True
    assert matches_filters(message_with_ref(15), settings, allowed_confs) is False
    assert matches_filters(message_with_ref(None), settings, allowed_confs) is False


def test_refnum_filtering_none_by_default():
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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        refnum_filters=None,
    )

    allowed_confs = {1}
    assert matches_filters(message_with_ref(42), settings, allowed_confs) is True
    assert matches_filters(message_with_ref(None), settings, allowed_confs) is True


def test_cli_refnum_argument_parsing():
    # Test that CLI parses -R, --reply-to, --refnum correctly and populates settings
    from pyqwk.cli import _parse_msgnum_ranges
    assert _parse_msgnum_ranges("42,100-102") == {42, 100, 101, 102}

    # Test integration using mock args
    test_args = ["qwk.py", "dummy_archive.qwk", "-R", "42-45", "--dry-run"]
    with patch("sys.argv", test_args), patch("pyqwk.cli.expand_paths", return_value=["dummy_archive.qwk"]), patch("pyqwk.cli.process_merged_files") as mock_process:
        main()
        # Verify that process_merged_files was called and passed ProcessingSettings with refnum_filters={42, 43, 44, 45}
        mock_process.assert_called_once()
        settings = mock_process.call_args[0][1]
        assert settings.refnum_filters == {42, 43, 44, 45}
        assert settings.dry_run is True
