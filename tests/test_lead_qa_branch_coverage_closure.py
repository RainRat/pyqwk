import logging
import sys
from unittest.mock import MagicMock

import pytest

from pyqwk.cli import main
from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    _order_messages_by_thread,
    _pack_directory_to_archive,
    detect_extension,
    process_merged_files,
    show_list_authors,
    show_list_bbs,
    show_list_recipients,
    show_list_subjects,
    show_threads,
)


def create_default_settings(**kwargs):
    defaults = dict(
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
        separator="=",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def test_detect_extension_empty_sample():
    assert detect_extension(b"") == ".txt"


def test_pack_directory_unsupported_extension(tmp_path):
    output_dir = tmp_path / "src"
    output_dir.mkdir()
    (output_dir / "test.txt").write_text("hello")
    archive_path = tmp_path / "out.unsupported"
    logger = logging.getLogger("test")
    _pack_directory_to_archive(str(output_dir), str(archive_path), logger)
    assert not archive_path.exists()


def test_process_messages_dry_run_temp_dir(tmp_path):
    archive = tmp_path / "test.qwk"
    archive.write_bytes(b"dummy archive content")
    output_archive = tmp_path / "out.qwk"
    logger = logging.getLogger("test")

    msg1 = ParsedMessage(
        header=MessageHeader(
            status="",
            msgnum=1,
            msgdate="01-01-24",
            msgtime="12:00",
            msgto="User",
            msgfrom="Sysop",
            msgsubject="Test",
            msgpassword="",
            refnum=0,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=1,
            nettag="",
        ),
        text=["Hello"],
        msgnum=1,
        refnum=0,
        confnum=1,
    )

    settings = create_default_settings(
        dry_run=True,
        format="qwk",
        output_path=str(output_archive),
        output_mode="archive",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("pyqwk.core.parse_messages", lambda data, pb, encoding, headers_only=False: [msg1])
        mp.setattr("pyqwk.core.validate_archive", lambda path: (True, "QWK", []))
        process_merged_files([str(archive)], settings, logger)
        assert not output_archive.exists()


def test_show_list_bbs_edge_branches(tmp_path):
    msg1 = ParsedMessage(
        header=MessageHeader(
            status="",
            msgnum=1,
            msgdate="99-99-99",  # Invalid date string
            msgtime="99:99",
            msgto="User",
            msgfrom="Sysop",
            msgsubject="Test",
            msgpassword="",
            refnum=0,
            numblocks=1,
            msgflag="",
            confnum=0,
            lognum=1,
            nettag="",
        ),
        text=["Hello"],
        msgnum=1,
        refnum=0,
        confnum=0,
    )
    msg1.confnum = None
    msg1.datetime = None

    archive = tmp_path / "test.qwk"
    archive.write_bytes(b"dummy")
    logger = logging.getLogger("test")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("pyqwk.core.parse_messages", lambda data, pb, encoding, headers_only=False: [msg1])
        mp.setattr("pyqwk.core.validate_archive", lambda path: (True, "QWK", []))
        settings = create_default_settings(format="text")
        show_list_bbs([str(archive)], settings, logger)


def test_order_messages_by_thread_repeated_cycle():
    def make_msg(msgnum, refnum, subj="Subj"):
        h = MessageHeader(
            status="",
            msgnum=msgnum,
            msgdate="01-01-24",
            msgtime="12:00",
            msgto="To",
            msgfrom="From",
            msgsubject=subj,
            msgpassword="",
            refnum=refnum,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=1,
            nettag="",
        )
        return ParsedMessage(header=h, text=[], msgnum=msgnum, refnum=refnum, confnum=1)

    m1 = make_msg(1, 4)
    m2 = make_msg(2, 1)
    m3 = make_msg(3, 2)
    m4 = make_msg(4, 3)
    m5 = make_msg(5, 0, "Re: Subj")
    m1.header.msgsubject = "Subj"

    res = _order_messages_by_thread([m1, m2, m3, m4, m5])
    assert len(res) == 5


def test_reports_filter_rejection_and_invalid_date_branches(tmp_path):
    msg_matching = ParsedMessage(
        header=MessageHeader(
            status="",
            msgnum=1,
            msgdate="01-01-24",
            msgtime="12:00",
            msgto="Bob",
            msgfrom="Alice",
            msgsubject="Topic",
            msgpassword="",
            refnum=0,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=1,
            nettag="",
        ),
        text=["Hello"],
        msgnum=1,
        refnum=0,
        confnum=1,
    )
    msg_matching.datetime = None

    msg_filtered = ParsedMessage(
        header=MessageHeader(
            status="",
            msgnum=2,
            msgdate="99-99-99",
            msgtime="99:99",
            msgto="Secret",
            msgfrom="Secret",
            msgsubject="FilterMe",
            msgpassword="",
            refnum=0,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=1,
            nettag="",
        ),
        text=["Filtered"],
        msgnum=2,
        refnum=0,
        confnum=1,
    )
    msg_filtered.datetime = None

    archive = tmp_path / "test.qwk"
    archive.write_bytes(b"dummy")
    logger = logging.getLogger("test")

    settings = create_default_settings(
        search_term="Topic",  # Filters out msg_filtered
        format="text",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("pyqwk.core.parse_messages", lambda data, pb, encoding, headers_only=False: [msg_matching, msg_filtered])
        mp.setattr("pyqwk.core.validate_archive", lambda path: (True, "QWK", []))

        show_threads([str(archive)], settings, logger)
        show_list_authors([str(archive)], settings, logger)
        show_list_recipients([str(archive)], settings, logger)
        show_list_subjects([str(archive)], settings, logger)


def test_cli_short_option_preset_matching(tmp_path, monkeypatch):
    archive = tmp_path / "test.qwk"
    archive.write_bytes(b"dummy archive content")

    # Pass short options (-c, -v) alongside -P to exercise short option matching loops
    monkeypatch.setattr("sys.argv", ["qwk", "-P", "forum", "-c", "-v", "--format=html", str(archive)])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("pyqwk.cli.process_merged_files", lambda paths, settings, logger: None)
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
