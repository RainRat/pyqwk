import logging
from pyqwk.core import (
    _parse_html_messages,
    matches_filters,
    _get_message_mapping,
    _order_messages_by_thread,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)

def _make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)

def test_parse_html_messages_empty_stack_on_div_close(tmp_path):
    # Covers line 1445: if stack: (False branch) in pyqwk/core.py
    # We need a message block AFTER a loose </div> to actually enter the while loop
    html_content = """
    </div>
    <div class="message">
        <div class="header"><strong>Number:</strong> 1</div>
        <pre class="body">Body</pre>
    </div>
    """
    html_file = tmp_path / "empty_stack.html"
    html_file.write_text(html_content, encoding="utf-8")

    messages = _parse_html_messages(str(html_file))
    assert len(messages) == 1
    assert messages[0].depth == 0

def test_parse_html_messages_date_variations(tmp_path):
    # Covers lines 1496 and 1498 (skipped branches in _parse_html_messages)

    # 1. date_str is empty (leads to dt_parts = [])
    html_content_1 = """
    <div class="message">
        <div class="header"><strong>Number:</strong> 1</div>
        <div class="header"><strong>Date:</strong></div>
        <pre class="body">Body</pre>
    </div>
    """
    f1 = tmp_path / "date_empty.html"
    f1.write_text(html_content_1, encoding="utf-8")
    msgs1 = _parse_html_messages(str(f1))
    assert msgs1[0].header.msgdate == "01-01-70"
    assert msgs1[0].header.msgtime == "00:00"

    # 2. date_str has only one part
    html_content_2 = """
    <div class="message">
        <div class="header"><strong>Number:</strong> 2</div>
        <div class="header"><strong>Date:</strong> 05-05-24</div>
        <pre class="body">Body</pre>
    </div>
    """
    f2 = tmp_path / "date_one_part.html"
    f2.write_text(html_content_2, encoding="utf-8")
    msgs2 = _parse_html_messages(str(f2))
    assert msgs2[0].header.msgdate == "05-05-24"
    assert msgs2[0].header.msgtime == "00:00"

def test_matches_filters_exclude_bbs_no_match():
    # Covers line 2628 (False branch)
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("Body", 1, None, 1, header, bbs_name="OtherBBS", bbs_id="OTHER")

    settings = _make_settings(
        exclude_bbs_names=["TargetBBS"],
        private=False
    )
    # Should not match exclusion, so matches_filters should be True
    assert matches_filters(msg, settings, set()) is True

def test_get_message_mapping_whitespace_body():
    # Covers line 2802 (loop finishes without finding non-empty line)
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("  \n  \t  ", 1, None, 1, header)

    mapping = _get_message_mapping(msg, 1)
    assert mapping["snippet"] == ""

def test_get_message_mapping_user_name_override():
    # Covers line 2812 (if not my_name_val is False)
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage("Body", 1, None, 1, header)

    mapping = _get_message_mapping(msg, 1, user_name="OverrideName")
    assert mapping["my_name"] == "OverrideName"

def test_order_messages_by_thread_circular_already_reported(caplog):
    # Covers line 6039 (child_idx in cycle_reported is True branch)

    def make_msg(num, ref, subj="Cycle"):
        h = MessageHeader(" ", num, "01-01-23", "10:00", "All", "From", subj, "", ref, 1, " ", 1, 1, "")
        return ParsedMessage(str(num), num, ref, 1, h)

    # Root 1 -> 2, 1 -> 3
    # 2 -> 4
    # 3 -> 4
    # 4 -> 1 (Cycle)

    make_msg(1, None)
    mA = make_msg(2, 1)
    mB = make_msg(3, 1)
    mC1 = make_msg(4, 2)
    mC2 = make_msg(4, 3)
    mR_with_ref = make_msg(1, 4)

    msgs = [mR_with_ref, mA, mB, mC1, mC2]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        _order_messages_by_thread(msgs)
    assert any("Conversation loop detected" in r.message for r in caplog.records)

def test_order_messages_by_thread_visited_but_not_path():
    # Covers line 6049: if child_idx in visited: (True branch)
    def make_msg(num, ref):
        h = MessageHeader(" ", num, "01-01-23", "10:00", "All", "From", "Subj", "", ref, 1, " ", 1, 1, "")
        return ParsedMessage(str(num), num, ref, 1, h)

    # Root 1 -> 3
    # Root 2 -> 3
    messages = [
        make_msg(1, None),
        make_msg(2, None),
        make_msg(3, 1),
        make_msg(3, 2), # Duplicate msgnum 3 but different parents
    ]

    _order_messages_by_thread(messages)
