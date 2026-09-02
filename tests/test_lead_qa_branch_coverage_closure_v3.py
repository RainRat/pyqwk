import sys
import argparse
from unittest.mock import MagicMock
from pyqwk.core import (
    ProcessingSettings,
    process_merged_files,
    show_list_urls,
    show_list_emails,
    show_list_bbs,
    show_list_authors,
    show_list_recipients,
    show_list_subjects,
    show_threads,
    _order_messages_by_thread,
    ParsedMessage,
    MessageHeader,
)
from pyqwk.cli import main


def make_header(msgnum=1, confnum=1, msgfrom="Alice", msgto="Bob", msgsubject="Test", refnum=0, msgdate="01-01-24", msgtime="12:00"):
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=refnum,
        numblocks=1,
        msgflag="",
        confnum=confnum,
        lognum=0,
        nettag="",
    )


def make_msg(msgnum=1, refnum=0, confnum=1, msgfrom="Alice", msgto="Bob", msgsubject="Test", text="Hello", bbs_name="TestBBS"):
    hdr = make_header(msgnum=msgnum, confnum=confnum, msgfrom=msgfrom, msgto=msgto, msgsubject=msgsubject, refnum=refnum)
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=hdr,
        depth=0,
        thread_id=str(msgnum),
        parent_msgnum=None,
        confname=f"Conf {confnum}",
        bbs_name=bbs_name,
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
        "separator": "auto",
        "output_mode": "stdout",
        "output_path": None,
        "encoding": "cp437",
    }
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def test_process_merged_files_dry_run_archive_packing_skip(tmp_path, monkeypatch):
    packed = []
    monkeypatch.setattr("pyqwk.core._pack_directory_to_archive", lambda d, r, l: packed.append((d, r)))

    qwk_path = tmp_path / "test.qwk"
    qwk_path.write_bytes(b"")

    out_zip = tmp_path / "out.zip"
    settings = make_settings(
        output_path=str(out_zip),
        dry_run=True,
        output_mode="file",
        quiet=True,
    )
    logger = MagicMock()

    monkeypatch.setattr("pyqwk.core.load_data", lambda path, logger, enc: ([], None))

    process_merged_files([str(qwk_path)], settings, logger)
    assert len(packed) == 0


def test_list_urls_and_emails_filter_exclusion_and_empty_matches(monkeypatch):
    msg1 = make_msg(msgnum=1, confnum=1, text="Check http://example.com")
    msg2 = make_msg(msgnum=2, confnum=2, text="Check http://test.com")

    monkeypatch.setattr("pyqwk.core.load_data", lambda path, logger, enc: ([msg1, msg2], None))
    monkeypatch.setattr("pyqwk.core.RE_URL_PATTERN", MagicMock(findall=lambda text: ["   "]))
    monkeypatch.setattr("pyqwk.core.RE_EMAIL_PATTERN", MagicMock(findall=lambda text: ["   "]))

    settings = make_settings(conferences=["1"], quiet=True)
    logger = MagicMock()

    show_list_urls(["dummy.qwk"], settings, logger)
    show_list_emails(["dummy.qwk"], settings, logger)


def test_list_reports_none_datetime_and_filter_exclusion(monkeypatch):
    hdr1 = make_header(msgnum=1, confnum=1, msgfrom="Alice", msgto="Bob", msgsubject="Test", msgdate="invalid", msgtime="invalid")
    msg1 = ParsedMessage(
        text="Hello",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=hdr1,
        bbs_name="BBS1",
    )
    msg1.datetime = None

    msg2 = make_msg(msgnum=2, confnum=2, bbs_name="BBS2")

    monkeypatch.setattr("pyqwk.core.load_data", lambda path, logger, enc: ([msg1, msg2], None))

    settings = make_settings(conferences=["1"], quiet=True)
    logger = MagicMock()

    show_list_bbs(["dummy.qwk"], settings, logger)
    show_list_authors(["dummy.qwk"], settings, logger)
    show_list_recipients(["dummy.qwk"], settings, logger)
    show_list_subjects(["dummy.qwk"], settings, logger)


def test_show_threads_none_thread_id_and_filter_exclusion(monkeypatch):
    msg1 = make_msg(msgnum=1, confnum=1)
    msg1.thread_id = None

    msg2 = make_msg(msgnum=2, confnum=2)

    monkeypatch.setattr("pyqwk.core.load_data", lambda path, logger, enc: ([msg1, msg2], None))

    settings = make_settings(conferences=["1"], quiet=True)
    logger = MagicMock()

    show_threads(["dummy.qwk"], settings, logger)


def test_order_messages_by_thread_cycle_reentry(monkeypatch):
    hdr1 = make_header(msgnum=1, refnum=2, confnum=1)
    hdr2 = make_header(msgnum=2, refnum=1, confnum=1)
    hdr3 = make_header(msgnum=3, refnum=1, confnum=1)

    msg1 = make_msg(msgnum=1, refnum=2, confnum=1)
    msg1.header = hdr1
    msg2 = make_msg(msgnum=2, refnum=1, confnum=1)
    msg2.header = hdr2
    msg3 = make_msg(msgnum=3, refnum=1, confnum=1)
    msg3.header = hdr3

    msgs = [msg1, msg2, msg3]
    ordered = _order_messages_by_thread(msgs)
    assert len(ordered) == 3


def test_cli_explicit_keys_non_dash_option_string(monkeypatch):
    test_args = ["qwk", "dummy.qwk", "--preset", "blog", "--info"]
    monkeypatch.setattr(sys, "argv", test_args)

    info_called = []
    monkeypatch.setattr("pyqwk.cli.show_info", lambda p, s, l: info_called.append(True))

    orig_init = argparse.ArgumentParser.__init__

    def custom_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        dummy_action = argparse.Action(option_strings=["+custom"], dest="custom_option")
        self._actions.append(dummy_action)

    monkeypatch.setattr(argparse.ArgumentParser, "__init__", custom_init)

    try:
        main()
    except SystemExit:
        pass

    assert len(info_called) == 1
