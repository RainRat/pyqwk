import os
from unittest.mock import patch
from pyqwk.core import _write_markdown, MessageHeader, ProcessedMessage, _write_index, ProcessingSettings


def test_write_markdown_output():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="User",
        msgfrom="Sysop",
        msgsubject="Welcome",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    message = ProcessedMessage(
        text="Hello World",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        depth=0,
        thread_id="1",
        parent_msgnum=None,
    )

    with patch("pyqwk.core._write_text_output") as mock_write:
        _write_markdown([message], None)

        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]

        assert "# QWK Messages" in content
        assert "## Welcome" in content
        assert "- **From:** Sysop" in content
        assert "Hello World" in content
        assert "---" in content


def test_write_markdown_threaded():
    header1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-90",
        msgtime="12:00",
        msgto="All",
        msgfrom="Sysop",
        msgsubject="Topic",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    header2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-01-90",
        msgtime="12:05",
        msgto="Sysop",
        msgfrom="User",
        msgsubject="Re: Topic",
        msgpassword="",
        refnum=1,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=2,
        nettag="",
    )

    msg1 = ProcessedMessage(
        text="Parent message",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header1,
        depth=0,
        thread_id="1",
        parent_msgnum=None,
    )
    msg2 = ProcessedMessage(
        text="Child message",
        msgnum=2,
        refnum=1,
        confnum=1,
        header=header2,
        depth=1,
        thread_id="1",
        parent_msgnum=1,
    )

    with patch("pyqwk.core._write_text_output") as mock_write:
        _write_markdown([msg1, msg2], None)

        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]

        assert "> ## Re: Topic" in content
        assert "> - **From:** User" in content
        assert "> Child message" in content
        assert "> ---" in content

        assert "\n## Topic" in content


def _make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="markdown",
        separator="none",
        output_mode="file",
        output_path=None,
        encoding="utf-8",
        include_toc=False,
        extract_attachments=False,
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def test_write_markdown_index_threaded_indentation(tmp_path):
    output_dir = str(tmp_path)
    settings = _make_settings(format="markdown", threaded=True)

    sample_info = [
        {
            "path": "001.md",
            "subject": "Root",
            "from": "A",
            "to": "B",
            "date": "01-01-23 12:00",
            "conf_num": 1,
            "conf_name": "General",
            "msgnum": 1,
            "attachments": [],
            "depth": 0,
        },
        {
            "path": "002.md",
            "subject": "Reply 1",
            "from": "B",
            "to": "A",
            "date": "01-01-23 12:05",
            "conf_num": 1,
            "conf_name": "General",
            "msgnum": 2,
            "attachments": [],
            "depth": 1,
        },
        {
            "path": "003.md",
            "subject": "Reply 2",
            "from": "A",
            "to": "B",
            "date": "01-01-23 12:10",
            "conf_num": 1,
            "conf_name": "General",
            "msgnum": 3,
            "attachments": [],
            "depth": 2,
        },
    ]

    _write_index(sample_info, output_dir, settings)

    index_path = os.path.join(output_dir, "README.md")
    assert os.path.exists(index_path)

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "| 1 | 01-01-23 12:00 | A | B | [Root](001.md) |  |" in content
        assert "| 2 | 01-01-23 12:05 | B | A | └&nbsp;[Reply 1](002.md) |  |" in content
        assert "| 3 | 01-01-23 12:10 | A | B | &nbsp;&nbsp;└&nbsp;[Reply 2](003.md) |  |" in content
