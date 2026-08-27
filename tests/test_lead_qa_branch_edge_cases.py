import logging
from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    detect_extension,
    _pack_directory_to_archive,
    _order_messages_by_thread,
    show_list_bbs,
    show_list_authors,
    show_list_recipients,
    show_list_subjects,
)


def test_detect_extension_whitespace_only():
    assert detect_extension(b"   \n\r\t   ") == ".txt"


def test_pack_directory_to_archive_unsupported_extension(tmp_path):
    logger = logging.getLogger("test")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "file.txt").write_text("sample content")

    archive_path = str(tmp_path / "archive.unsupported")
    _pack_directory_to_archive(str(src_dir), archive_path, logger)


def test_order_messages_by_thread_cycle_reentry():
    hdr1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-20",
        msgtime="10:00",
        msgto="All",
        msgfrom="User1",
        msgsubject="Root Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    hdr2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-01-20",
        msgtime="10:05",
        msgto="User1",
        msgfrom="User2",
        msgsubject="Re: Root Subject",
        msgpassword="",
        refnum=1,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    hdr3 = MessageHeader(
        status=" ",
        msgnum=3,
        msgdate="01-01-20",
        msgtime="10:10",
        msgto="User1",
        msgfrom="User3",
        msgsubject="Re: Root Subject",
        msgpassword="",
        refnum=1,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )

    msg1 = ParsedMessage(text="Root", msgnum=1, refnum=None, confnum=1, header=hdr1)
    msg2 = ParsedMessage(text="Reply 1", msgnum=2, refnum=1, confnum=1, header=hdr2)
    msg3 = ParsedMessage(text="Reply 2", msgnum=3, refnum=1, confnum=1, header=hdr3)

    msg1.refnum = 2

    messages = [msg1, msg2, msg3]
    msg1.refnum = 2
    msg2.refnum = 1
    msg3.refnum = 1

    ordered = _order_messages_by_thread(messages)
    assert len(ordered) == 3


def test_show_list_bbs_none_confnum_and_invalid_date(tmp_path, mocker):
    hdr = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="invalid-date",
        msgtime="invalid-time",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=hdr)
    msg.confnum = None

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=str(tmp_path / "out.txt"),
        encoding="utf-8",
    )

    show_list_bbs(["test.qwk"], settings, logger)


def test_show_list_authors_invalid_date(tmp_path, mocker):
    hdr = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="invalid-date",
        msgtime="invalid-time",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=hdr)

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=str(tmp_path / "out.txt"),
        encoding="utf-8",
    )

    show_list_authors(["test.qwk"], settings, logger)


def test_show_list_recipients_invalid_date(tmp_path, mocker):
    hdr = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="invalid-date",
        msgtime="invalid-time",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=hdr)

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=str(tmp_path / "out.txt"),
        encoding="utf-8",
    )

    show_list_recipients(["test.qwk"], settings, logger)


def test_show_list_subjects_invalid_date(tmp_path, mocker):
    hdr = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="invalid-date",
        msgtime="invalid-time",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=hdr)

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=str(tmp_path / "out.txt"),
        encoding="utf-8",
    )

    show_list_subjects(["test.qwk"], settings, logger)
