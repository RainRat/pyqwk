import pytest
import logging
from pyqwk.core import (
    _order_messages_by_thread,
    _get_message_mapping,
    matches_filters,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    _parse_html_messages
)

def test_threading_immediate_cycle_warning(message_factory, caplog):
    msgs = [
        message_factory(1, 2, "A"),
        message_factory(2, 1, "B"),
    ]
    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)
    assert "Circular reference detected" in caplog.text
    assert "skipping parent assignment" in caplog.text

def test_matches_filters_exclude_bbs_no_match():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("Hi", 1, None, 1, header, bbs_name="GoodBBS", bbs_id="GOOD")

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", exclude_bbs_names=["BadBBS"]
    )

    assert matches_filters(msg, settings, set()) is True

def test_get_message_mapping_empty_snippet():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("\n  \n\t\n", 1, None, 1, header)

    mapping = _get_message_mapping(msg, 1)
    assert mapping["snippet"] == ""

def test_get_message_mapping_with_user_name():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "Alice", "Subj", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("Body", 1, None, 1, header)

    mapping = _get_message_mapping(msg, 1, user_name="Bob")
    assert mapping["my_name"] == "Bob"

def test_parse_html_messages_extra_div(tmp_path):
    content = """
    <div></div>
    </div>
    <div class="message">
        <strong>From:</strong> Alice</div>
        <strong>To:</strong> Bob</div>
        <strong>Subject:</strong> Hello</div>
        <strong>Date:</strong> 01-01-24 12:00</div>
        <div class="body">Body</div>
    </div>
    """
    html_file = tmp_path / "extra_div.html"
    html_file.write_text(content)

    msgs = _parse_html_messages(str(html_file))
    assert len(msgs) == 1

def test_parse_html_messages_incomplete_date(tmp_path):
    content = """
    <div class="message">
        <strong>From:</strong> Alice</div>
        <strong>To:</strong> Bob</div>
        <strong>Subject:</strong> Subj</div>
        <strong>Date:</strong> 01-01-24</div>
        <div class="body">Body</div>
    </div>
    <div class="message">
        <strong>From:</strong> Alice</div>
        <strong>To:</strong> Bob</div>
        <strong>Subject:</strong> Subj</div>
        <strong>Date:</strong> </div>
        <div class="body">Body</div>
    </div>
    """
    html_file = tmp_path / "dates.html"
    html_file.write_text(content)

    msgs = _parse_html_messages(str(html_file))
    assert len(msgs) == 2
    assert msgs[0].header.msgdate == "01-01-24"
    assert msgs[0].header.msgtime == "00:00"
    assert msgs[1].header.msgdate == "01-01-70"
    assert msgs[1].header.msgtime == "00:00"
