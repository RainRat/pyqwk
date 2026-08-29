import logging
from types import SimpleNamespace
from pyqwk.core import (
    show_list_urls,
    show_list_emails,
    show_list_authors,
    show_list_recipients,
    show_list_subjects,
    show_threads,
    _order_messages_by_thread,
    process_merged_files,
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
)

test_logger = logging.getLogger("test_lead_qa")


def make_header(msgfrom="Alice", msgto="Bob", msgdate="01-01-24", msgtime="12:00", msgsubject="Test"):
    return MessageHeader(
        status=" ",
        msgnum=1,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )


def make_message(text="Hello", msgnum=1, refnum=0, confnum=1, msgfrom="Alice", msgto="Bob", msgdate="01-01-24", msgtime="12:00", msgsubject="Test", confname="General"):
    header = make_header(msgfrom=msgfrom, msgto=msgto, msgdate=msgdate, msgtime=msgtime, msgsubject=msgsubject)
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header,
        confname=confname,
    )


def test_show_list_urls_filter_exclusion_and_empty_url(mocker, tmp_path):
    mock_settings = SimpleNamespace(
        search=None,
        exclude="Exclude",
        conf=None,
        author=None,
        mine=False,
        my_name=None,
        min_words=None,
        max_words=None,
        start_date=None,
        end_date=None,
        on_this_day=None,
        msgnum=None,
        refnum=None,
        thread_id=None,
        min_depth=None,
        max_depth=None,
        limit=None,
        output_format="text",
        dry_run=False,
        to_user=None,
        output=None,
        pattern=None,
    )

    msg1 = make_message(text="Check http://example.com and   ", msgnum=1, msgsubject="Test")
    msg2 = make_message(text="Excluded http://secret.com", msgnum=2, msgsubject="Test Exclude")

    mocker.patch("pyqwk.core.parse_messages", return_value=[msg1, msg2])
    test_file = tmp_path / "test.qwk"
    test_file.write_bytes(b"dummy")

    show_list_urls([str(test_file)], mock_settings, test_logger)


def test_show_list_emails_filter_exclusion_and_empty_email(mocker, tmp_path):
    mock_settings = SimpleNamespace(
        search=None,
        exclude="Exclude",
        conf=None,
        author=None,
        mine=False,
        my_name=None,
        min_words=None,
        max_words=None,
        start_date=None,
        end_date=None,
        on_this_day=None,
        msgnum=None,
        refnum=None,
        thread_id=None,
        min_depth=None,
        max_depth=None,
        limit=None,
        output_format="text",
        dry_run=False,
        to_user=None,
        output=None,
        pattern=None,
    )

    msg1 = make_message(text="Mail alice@example.com", msgnum=1, msgsubject="Test")
    msg2 = make_message(text="Mail secret@example.com", msgnum=2, msgsubject="Test Exclude")

    mocker.patch("pyqwk.core.parse_messages", return_value=[msg1, msg2])
    test_file = tmp_path / "test.qwk"
    test_file.write_bytes(b"dummy")

    show_list_emails([str(test_file)], mock_settings, test_logger)


def test_show_list_authors_recipients_subjects_no_date_and_filtered(mocker, tmp_path):
    mock_settings = SimpleNamespace(
        search=None,
        exclude="Exclude",
        conf=None,
        author=None,
        mine=False,
        my_name=None,
        min_words=None,
        max_words=None,
        start_date=None,
        end_date=None,
        on_this_day=None,
        msgnum=None,
        refnum=None,
        thread_id=None,
        min_depth=None,
        max_depth=None,
        limit=None,
        output_format="text",
        dry_run=False,
        to_user=None,
        output=None,
        pattern=None,
    )

    msg1 = make_message(text="Sample text", msgnum=1, msgdate="INVALID", msgtime="INVALID", msgsubject="Hello")
    msg2 = make_message(text="Excluded", msgnum=2, msgsubject="Exclude me")

    mocker.patch("pyqwk.core.parse_messages", return_value=[msg1, msg2])
    test_file = tmp_path / "test.qwk"
    test_file.write_bytes(b"dummy")

    show_list_authors([str(test_file)], mock_settings, test_logger)
    show_list_recipients([str(test_file)], mock_settings, test_logger)
    show_list_subjects([str(test_file)], mock_settings, test_logger)


def test_show_threads_filters_and_none_thread_id(mocker, tmp_path):
    mock_settings = SimpleNamespace(
        search=None,
        exclude="Exclude",
        conf=None,
        author=None,
        mine=False,
        my_name=None,
        min_words=None,
        max_words=None,
        start_date=None,
        end_date=None,
        on_this_day=None,
        msgnum=None,
        refnum=None,
        thread_id=None,
        min_depth=None,
        max_depth=None,
        limit=None,
        output_format="text",
        dry_run=False,
        to_user=None,
        output=None,
        pattern=None,
        sort=None,
        reverse=False,
    )

    msg1 = make_message(text="Hello", msgnum=100, refnum=0, msgsubject="Thread test")
    msg1.thread_id = None  # Force thread_id to None

    msg2 = make_message(text="Hello Exclude", msgnum=101, refnum=100, msgsubject="Exclude test")

    mocker.patch("pyqwk.core.parse_messages", return_value=[msg1, msg2])
    test_file = tmp_path / "test.qwk"
    test_file.write_bytes(b"dummy")

    show_threads([str(test_file)], mock_settings, test_logger)


def test_order_messages_by_thread_cycle_already_reported(caplog):
    msg1 = make_message(msgnum=1, refnum=2, msgsubject="Loop 1")
    msg2 = make_message(msgnum=2, refnum=1, msgsubject="Loop 2")
    msg3 = make_message(msgnum=3, refnum=2, msgsubject="Loop 3")

    with caplog.at_level(logging.WARNING):
        ordered = _order_messages_by_thread([msg1, msg2, msg3])

    assert len(ordered) == 3


def test_process_merged_files_dry_run_packing_bypass(mocker, tmp_path):
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
        format="qwk",
        separator="",
        output_mode="qwk",
        output_path=str(tmp_path / "out.qwk"),
        encoding="cp437",
        dry_run=True,
        quiet=True,
    )

    msg = make_message(text="Hello", msgnum=1, msgsubject="Test")

    mocker.patch("pyqwk.core.parse_messages", return_value=[msg])
    mock_pack = mocker.patch("pyqwk.core._pack_directory_to_archive")
    test_file = tmp_path / "test.qwk"
    test_file.write_bytes(b"dummy")

    process_merged_files([str(test_file)], settings, test_logger)
    assert not mock_pack.called
