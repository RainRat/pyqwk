from unittest.mock import MagicMock, patch
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)

def _make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        merge=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=None,
        encoding="cp437",
        organize=False,
        organize_by_date=False,
        organize_by_bbs=False,
        organize_by_author=False,
        organize_by_to=False,
        organize_by_subject=False,
        extract_attachments=False,
        include_toc=False,
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)

def _make_msg(
    msgnum=1,
    confnum=1,
    msgdate="01-01-23",
    msgtime="12:00",
    msgfrom="Author",
    msgto="Recipient",
    msgsubject="Subject",
    text="Body",
):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=confnum,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text=text, msgnum=msgnum, refnum=None, confnum=confnum, header=header
    )

def test_organize_by_subject(tmp_path):
    output_dir = tmp_path / "output_subject"
    output_dir.mkdir()

    msg1 = _make_msg(msgnum=1, msgsubject="Greetings")
    msg2 = _make_msg(msgnum=2, msgsubject="Re: Greetings")
    msg3 = _make_msg(msgnum=3, msgsubject="Important News")

    settings = _make_settings(output_path=str(output_dir), organize_by_subject=True)
    logger = MagicMock()

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General Chat"})),
        patch("pyqwk.core.parse_messages", return_value=[msg1, msg2, msg3]),
    ):
        process_merged_files(["dummy.qwk"], settings, logger)

    # Both msg1 and msg2 should be in the "greetings" folder because of normalization
    assert (output_dir / "greetings" / "001-00001-greetings.txt").exists()
    assert (output_dir / "greetings" / "001-00002-re_greetings.txt").exists()
    assert (output_dir / "important_news" / "001-00003-important_news.txt").exists()

def test_organize_by_subject_empty(tmp_path):
    output_dir = tmp_path / "output_subject_empty"
    output_dir.mkdir()

    msg = _make_msg(msgnum=1, msgsubject="")
    settings = _make_settings(output_path=str(output_dir), organize_by_subject=True)

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General Chat"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert (output_dir / "no_subject" / "001-00001-message.txt").exists()
