import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters, _get_message_mapping, process_merged_files
import logging

def test_question_filter():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, " ")

    msg_with_q = ParsedMessage("Is this a question?", 1, None, 1, header)
    msg_without_q = ParsedMessage("This is a statement.", 1, None, 1, header)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        has_questions=True
    )

    assert matches_filters(msg_with_q, settings, set()) is True
    assert matches_filters(msg_without_q, settings, set()) is False

def test_quote_filter():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, " ")

    msg_with_quote = ParsedMessage("> Quoted text\nReply text", 1, None, 1, header)
    msg_without_quote = ParsedMessage("Regular text", 1, None, 1, header)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        has_quotes=True
    )

    assert matches_filters(msg_with_quote, settings, set()) is True
    assert matches_filters(msg_without_quote, settings, set()) is False

def test_word_count_filter():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, " ")

    msg_small = ParsedMessage("One two", 1, None, 1, header) # 2 words
    msg_large = ParsedMessage("One two three four five", 1, None, 1, header) # 5 words

    settings_min = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        min_words=3
    )

    assert matches_filters(msg_small, settings_min, set()) is False
    assert matches_filters(msg_large, settings_min, set()) is True

    settings_max = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        max_words=3
    )

    assert matches_filters(msg_small, settings_max, set()) is True
    assert matches_filters(msg_large, settings_max, set()) is False

def test_replies_filter():
    header_orig = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Original", "", None, 1, " ", 1, 0, " ")
    header_reply = MessageHeader(" ", 2, "01-01-24", "12:01", "From", "To", "Re: Original", "", 1, 1, " ", 1, 0, " ")

    msg_orig = ParsedMessage("Original", 1, None, 1, header_orig)
    msg_reply = ParsedMessage("Reply", 2, 1, 1, header_reply)

    settings_only = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        replies_filter="only"
    )

    assert matches_filters(msg_orig, settings_only, set()) is False
    assert matches_filters(msg_reply, settings_only, set()) is True

    settings_exclude = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        replies_filter="exclude"
    )

    assert matches_filters(msg_orig, settings_exclude, set()) is True
    assert matches_filters(msg_reply, settings_exclude, set()) is False

def test_analytics_mapping():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, " ")
    # 9 words, 2 sentences
    text = "This is a sentence. And this is another one?"
    msg = ParsedMessage(text, 1, None, 1, header)

    mapping = _get_message_mapping(msg, 1)

    assert mapping["word_count"] == 9
    assert mapping["sentence_count"] == 2
    assert mapping["reading_time"] == "1 min read"
    assert mapping["is_question"] == "true"

def test_reading_time_long():
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, " ")
    # 400 words should be ~2 min
    text = "word " * 400
    msg = ParsedMessage(text, 1, None, 1, header)

    mapping = _get_message_mapping(msg, 1)
    assert mapping["word_count"] == 400
    assert mapping["reading_time"] == "2 min read"

def test_sorting_by_words(tmp_path, capsys):
    # Using process_merged_files to test sorting
    import os
    import json

    msg1 = {
        "header": {"status": " ", "msgnum": 1, "msgdate": "01-01-24", "msgtime": "12:00", "msgto": "All", "msgfrom": "A", "msgsubject": "Long", "msgpassword": "", "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "},
        "text": "one two three four five" # 5 words
    }
    msg2 = {
        "header": {"status": " ", "msgnum": 2, "msgdate": "01-01-24", "msgtime": "12:01", "msgto": "All", "msgfrom": "B", "msgsubject": "Short", "msgpassword": "", "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "},
        "text": "one" # 1 word
    }

    json_path = tmp_path / "test.json"
    with open(json_path, "w") as f:
        json.dump([msg1, msg2], f)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None, encoding="cp437",
        sort="words", quiet=True
    )

    logger = logging.getLogger("test")
    process_merged_files([str(json_path)], settings, logger)

    captured = capsys.readouterr()
    # Short should come first (1 word)
    lines = captured.out.strip().split("\n")
    assert lines[0].strip() == "one"
    assert lines[1].strip() == "one two three four five"

    # Reverse sort
    settings.reverse = True
    process_merged_files([str(json_path)], settings, logger)
    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert lines[0].strip() == "one two three four five"
    assert lines[1].strip() == "one"
