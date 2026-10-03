import os
import tempfile
import logging
from unittest.mock import MagicMock, patch
import pytest

from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    extract_domains_from_text,
    _order_messages_by_thread,
    show_threads,
    show_list_authors,
    show_list_recipients,
    show_list_subjects,
    show_list_sources,
    show_list_dates,
    show_list_hours,
    show_list_msg_links,
)


def create_msg(msgnum=1, confnum=1, date="01-01-23", time="12:00", msgfrom="Alice", msgto="Bob", subject="Hello", text="Body text", refnum=None):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=date,
        msgtime=time,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=subject,
        msgpassword="",
        refnum=refnum,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=1,
        nettag="",
    )
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header,
        confname=f"Conf_{confnum}",
        bbs_name="TestBBS",
        source_file="test.qwk",
    )


def test_process_merged_files_dry_run_archive_export(tmp_path):
    logger = logging.getLogger("pyqwk.test")
    zip_out = str(tmp_path / "export.zip")
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=zip_out,
        encoding="cp437",
        dry_run=True,
    )

    msg = create_msg()
    with patch("pyqwk.core.load_data", return_value=([msg], {1: "Conf_1"})):
        process_merged_files(["dummy.qwk"], settings, logger)

    assert not os.path.exists(zip_out)


def test_extract_domains_from_text_edge_cases():
    mock_pattern = MagicMock()
    mock_pattern.findall.return_value = ["noatsign"]
    with patch("pyqwk.core.RE_EMAIL_PATTERN", mock_pattern):
        domains = extract_domains_from_text("some text")
        assert domains == []

    text_with_empty_parsed_host = "Visit http://"
    domains_url = extract_domains_from_text(text_with_empty_parsed_host)
    assert domains_url == []


def test_entity_list_reports_intermediate_date_branches(tmp_path):
    logger = logging.getLogger("pyqwk.test")
    out_file = str(tmp_path / "report.txt")

    m1 = create_msg(msgnum=1, date="01-01-20", time="10:00")
    m2 = create_msg(msgnum=2, date="01-03-20", time="10:00")
    m3 = create_msg(msgnum=3, date="01-02-20", time="10:00")
    m4 = create_msg(msgnum=4, date="invalid_date", time="invalid_time")
    m5_filtered_out = create_msg(msgnum=5, msgfrom="FilteredAuthor", date="01-02-20")
    msgs = [m1, m2, m3, m4, m5_filtered_out]

    base_settings = ProcessingSettings(
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
        output_mode="stdout",
        output_path=out_file,
        encoding="cp437",
        exclude_authors=["FilteredAuthor"],
    )

    with patch("pyqwk.core.load_data", return_value=(msgs, {1: "Conf_1"})):
        show_list_authors(["dummy.qwk"], base_settings, logger)
        show_list_recipients(["dummy.qwk"], base_settings, logger)
        show_list_subjects(["dummy.qwk"], base_settings, logger)
        show_list_sources(["dummy.qwk"], base_settings, logger)
        show_list_dates(["dummy.qwk"], base_settings, logger)
        show_list_hours(["dummy.qwk"], base_settings, logger)

    assert os.path.exists(out_file)


def test_show_list_msg_links_filters(tmp_path):
    logger = logging.getLogger("pyqwk.test")
    out_file = str(tmp_path / "msg_links.txt")
    m1 = create_msg(msgnum=1, text="Check msg #2 for details")
    m2 = create_msg(msgnum=2, text="No link here")

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
        output_mode="stdout",
        output_path=out_file,
        encoding="cp437",
    )
    with patch("pyqwk.core.load_data", return_value=([m1, m2], {1: "Conf_1"})):
        show_list_msg_links(["dummy.qwk"], settings, logger)
    assert os.path.exists(out_file)


def test_order_messages_by_thread_cycle_reported():
    m1 = create_msg(msgnum=1, refnum=2)
    m2 = create_msg(msgnum=2, refnum=1)

    ordered = _order_messages_by_thread([m1, m2])
    assert len(ordered) == 2


def test_show_threads_none_thread_id(tmp_path):
    logger = logging.getLogger("pyqwk.test")
    out_file = str(tmp_path / "threads.txt")
    m1 = create_msg(msgnum=1)

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
        output_mode="stdout",
        output_path=out_file,
        encoding="cp437",
    )

    with patch("pyqwk.core.load_data", return_value=([m1], {1: "Conf_1"})), \
         patch("pyqwk.core._order_messages_by_thread", return_value=[m1]):
        show_threads(["dummy.qwk"], settings, logger)

    assert os.path.exists(out_file)


def test_gui_branch_coverage_gaps():
    from pyqwk.gui import QwkGuiApp
    import tkinter as tk

    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display unavailable")

    app = QwkGuiApp(root)
    app.messages = [create_msg(msgnum=1), create_msg(msgnum=2)]

    app.message_list.selection_remove(app.message_list.selection())
    app._restore_status_bar()
    app._update_status_bar()
    app._push_current_to_history()

    if hasattr(app, "back_button"):
        delattr(app, "back_button")
    if hasattr(app, "edit_menu"):
        delattr(app, "edit_menu")
    app._update_history_ui()

    app._clear_filter_field("search_var", "non_existent_entry")

    app.detail_text.tag_add("sel", "1.0", "1.5")
    app.detail_text.delete("1.0", tk.END)
    app.detail_text.insert("1.0", "   ")
    app.detail_text.tag_add("sel", "1.0", "1.3")
    app._search_from_selection()

    hdr_no_msgnum = MessageHeader(
        status=" ",
        msgnum=None,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg_no_msgnum = ParsedMessage(
        text="body",
        msgnum=None,
        refnum=None,
        confnum=1,
        header=hdr_no_msgnum,
    )
    app.messages = [msg_no_msgnum]
    app._render_message(0)

    app._search_timer = None
    app._on_search_changed()

    with patch("tkinter.filedialog.asksaveasfilename", return_value=""):
        app._on_export_attachment("attachment.bin", b"data")

    cb = app._create_pivot_callback("search", "query")
    with patch.object(app, "reload_messages") as mock_reload:
        cb()
        assert app.search_var.get() == "query"
        mock_reload.assert_called_once()

    res = app._get_sort_key_for_item("1", "#0")
    assert res is not None

    root.destroy()
