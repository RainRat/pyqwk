import pytest
import os
import tempfile
import shutil
import logging
from unittest.mock import MagicMock, patch
from pyqwk.core import load_data

@pytest.fixture
def test_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

def test_markdown_parser_metadata_and_merging_gaps(test_dir):
    content = (
        "Preamble content to skip.\n"
        "---\n"
        "Malformed section without header\n"
        "---\n"
        "## Message 1\n"
        "- **Date:** 01-01-24 12:00\n"
        "- **From:** Alice\n"
        "- **To:** Bob\n"
        "- **Conference:** General (1)\n"
        "- **BBS:** MyBBS\n"
        "- **Source:** source.qwk\n"
        "- **Number:** 123\n"
        "- **Attachments:** [file1.txt](file1.txt)\n"
        "\n"
        "Body 1\n"
        "---\n"
        "No double hash here, will be merged to Message 1.\n"
        "---\n"
        "  ## Message 2 with leading space\n"
        "- **Date:** 02-02-24\n"
        "\n"
        "Body 2\n"
        "---\n"
        "> ## Message 3 (Threaded)\n"
        "> - **Date:** 03-03-24\n"
        ">\n"
        "> Line 1\n"
        "Line 2 (not quoted)\n"
        "---\n"
        "## Message 4 (Subsequent)\n"
        "- **Date:** 04-04-24 15:00\n"
        "\n"
        "Body 4\n"
    )

    path = os.path.join(test_dir, "gaps.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    messages, _ = load_data(path, logging.getLogger())

    assert len(messages) == 4
    assert messages[0].header.msgsubject == "Message 1"
    assert "No double hash here" in messages[0].text
    assert messages[1].header.msgsubject == "Message 2 with leading space"
    assert messages[2].header.msgsubject == "Message 3 (Threaded)"
    assert messages[2].depth == 1
    assert "Line 1" in messages[2].text
    assert "Line 2" in messages[2].text
    assert messages[3].header.msgsubject == "Message 4 (Subsequent)"

def test_markdown_load_data_error_handling_gap(test_dir):
    path = os.path.join(test_dir, "corrupt.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("dummy")
    from unittest.mock import patch
    with patch("pyqwk.core._parse_markdown_messages", side_effect=Exception("Parsing error")):
        with pytest.raises(ValueError, match="Failed to load Markdown archive"):
            load_data(path, logging.getLogger())

def test_markdown_blockquote_empty_line_parsing_gap(test_dir):
    content = "> ## Message\n\n> Content"
    path = os.path.join(test_dir, "bq_empty.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    messages, _ = load_data(path, logging.getLogger())
    assert len(messages) == 1
    assert "Content" in messages[0].text

def test_markdown_invalid_section_after_blockquote_stripping_gap(test_dir):
    content = "> ## \n"
    path = os.path.join(test_dir, "invalid_sec.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    messages, _ = load_data(path, logging.getLogger())
    assert len(messages) == 0

def test_markdown_subject_regex_failure_gap(test_dir):
    # Targeted line 1154: re_subject.search(working_section) fails.
    # The regex is local to _parse_markdown_messages, so we patch re.compile
    # to return a mock object for the subject regex.
    content = "## Message"
    path = os.path.join(test_dir, "mock_fail.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    import re
    original_compile = re.compile

    mock_regex = MagicMock()
    mock_regex.search.return_value = None

    def side_effect(pattern, flags=0):
        if pattern == r'^## (.*)':
            return mock_regex
        return original_compile(pattern, flags)

    from unittest.mock import patch
    with patch("re.compile", side_effect=side_effect):
        messages, _ = load_data(path, logging.getLogger())
        assert len(messages) == 0
