import pytest
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    _serialize_message_html,
    _serialize_message_markdown,
    _write_html,
    _write_markdown,
    ProcessingSettings,
)


@pytest.fixture
def sample_message():
    header = MessageHeader(
        status=" ",
        msgnum=100,
        msgdate="01-20-24",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Quote Highlighting",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    text = (
        "Hello Alice,\n"
        "> This is a standard quote.\n"
        "| This is an alternative quote style.\n"
        "│ And another one.\n"
        "Normal line here.\n"
        "> Quote with search term: highlight me!"
    )
    return ParsedMessage(
        text=text,
        msgnum=100,
        refnum=None,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="TestBBS",
    )


def test_html_quote_highlighting(sample_message):
    html_output = _serialize_message_html(sample_message, search_term="highlight")

    # Check for CSS class
    assert ".quote { color: #4e9a06; }" in html_output

    # Check for quote spans
    assert '<span class="quote">&gt; This is a standard quote.</span>' in html_output
    assert (
        '<span class="quote">| This is an alternative quote style.</span>'
        in html_output
    )
    assert '<span class="quote">│ And another one.</span>' in html_output

    # Check for highlighting within quote
    assert (
        '<span class="quote">&gt; Quote with search term: <mark>highlight</mark> me!</span>'
        in html_output
    )

    # Normal line should not be wrapped
    assert "Normal line here." in html_output
    assert '<span class="quote">Normal line here.</span>' not in html_output


def test_markdown_quote_standardization(sample_message):
    md_output = _serialize_message_markdown(sample_message, search_term="highlight")

    # Check for blockquote standardization
    # Standard quote already has >
    assert "> This is a standard quote." in md_output
    # Alternatives should have > prepended
    assert "> | This is an alternative quote style." in md_output
    assert "> │ And another one." in md_output

    # Check for highlighting within quote
    assert "> Quote with search term: **highlight** me!" in md_output

    # Normal line should not have >
    assert "\nNormal line here.\n" in md_output
    assert "\n> Normal line here.\n" not in md_output


def test_write_html_with_quotes(sample_message, tmp_path):
    output_file = tmp_path / "test.html"
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
        format="html",
        separator="none",
        output_mode="file",
        output_path=str(output_file),
        encoding="utf-8",
    )

    _write_html([sample_message], str(output_file), settings=settings)

    content = output_file.read_text(encoding="utf-8")
    assert ".quote { color: #4e9a06; }" in content
    assert '<span class="quote">&gt; This is a standard quote.</span>' in content


def test_write_markdown_with_quotes(sample_message, tmp_path):
    output_file = tmp_path / "test.md"
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
        format="markdown",
        separator="none",
        output_mode="file",
        output_path=str(output_file),
        encoding="utf-8",
    )

    _write_markdown([sample_message], str(output_file), settings=settings)

    content = output_file.read_text(encoding="utf-8")
    assert "> | This is an alternative quote style." in content
