import pytest
import io
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    BBSInfo,
    _write_html,
    _write_markdown,
    _write_text,
)


@pytest.fixture
def mock_messages():
    h1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Subject 1",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    h2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-02-23",
        msgtime="13:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Subject 2",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=2,
        lognum=1,
        nettag="",
    )

    m1 = ParsedMessage(
        text="Message 1 content",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=h1,
        confname="General",
    )
    m2 = ParsedMessage(
        text="Message 2 content",
        msgnum=2,
        refnum=None,
        confnum=2,
        header=h2,
        confname="Games",
    )
    return [m1, m2]


@pytest.fixture
def bbs_info():
    return BBSInfo(
        name="Test BBS",
        sysop="Sysop Name",
        location="Somewhere",
        packet_at="2023-10-27",
    )


def test_toc_html(mock_messages, bbs_info, monkeypatch):
    io.StringIO()
    # We need to mock _write_text_output to capture the result
    captured_content = []

    def mock_write_output(content, path, encoding="utf-8"):
        captured_content.append(content)

    monkeypatch.setattr("pyqwk.core._write_text_output", mock_write_output)

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
        strip_ansi=False,
        format="html",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8",
        quiet=True,
        include_toc=True,
    )

    _write_html(mock_messages, None, "utf-8", settings, bbs_info)

    html_out = captured_content[0]
    assert '<h1 id="top">Test BBS Archive</h1>' in html_out
    assert '<li><a href="#conf-1">General (Conf 1)</a></li>' in html_out
    assert '<li><a href="#conf-2">Games (Conf 2)</a></li>' in html_out
    assert '<h2 id="conf-1">General</h2>' in html_out
    assert '<h2 id="conf-2">Games</h2>' in html_out
    assert 'id="msg-0"' in html_out
    assert 'id="msg-1"' in html_out


def test_toc_markdown(mock_messages, bbs_info, monkeypatch):
    captured_content = []

    def mock_write_output(content, path, encoding="utf-8"):
        captured_content.append(content)

    monkeypatch.setattr("pyqwk.core._write_text_output", mock_write_output)

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
        strip_ansi=False,
        format="markdown",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8",
        quiet=True,
        include_toc=True,
    )

    _write_markdown(mock_messages, None, "utf-8", settings, bbs_info)

    md_out = captured_content[0]
    assert "# Test BBS Archive" in md_out
    assert "## Table of Contents" in md_out
    assert "- [General](#conf-1)" in md_out
    assert "- [Games](#conf-2)" in md_out
    assert '## General <a name="conf-1"></a>' in md_out
    assert '## Games <a name="conf-2"></a>' in md_out


def test_toc_text(mock_messages, bbs_info, monkeypatch):
    captured_content = []

    def mock_write_output(content, path, encoding="utf-8"):
        captured_content.append(content)

    monkeypatch.setattr("pyqwk.core._write_text_output", mock_write_output)

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
        strip_ansi=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8",
        quiet=True,
        include_toc=True,
    )

    _write_text(mock_messages, None, "utf-8", settings, bbs_info)

    text_out = captured_content[0]
    assert "Test BBS Archive" in text_out
    assert "Conferences:" in text_out
    assert "  1: General (1 messages)" in text_out
    assert "  2: Games (1 messages)" in text_out
