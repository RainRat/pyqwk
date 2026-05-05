import os
import pytest
from pyqwk.core import _write_index, ProcessingSettings, BBSInfo


def _make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="none",
        output_mode="file",
        output_path=None,
        encoding="utf-8",
        include_toc=False,
        extract_attachments=False,
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


@pytest.fixture
def sample_info():
    return [
        {
            "path": "001-00001-welcome.html",
            "subject": "Welcome | To BBS",
            "from": "Sysop [Admin]",
            "to": "User",
            "date": "01-01-23 12:00",
            "conf_num": 1,
            "conf_name": "General",
            "msgnum": 1,
            "attachments": ["logo.png"],
        },
        {
            "path": "002-00002-hello.html",
            "subject": "Hello",
            "from": "User",
            "to": "All",
            "date": "01-02-23 13:00",
            "conf_num": 2,
            "conf_name": "Chat",
            "msgnum": 2,
            "attachments": [],
        },
    ]


def test_write_html_index(tmp_path, sample_info):
    output_dir = str(tmp_path)
    bbs_info = BBSInfo(name="Test BBS")
    settings = _make_settings(format="html")

    _write_index(sample_info, output_dir, settings, bbs_info)

    index_path = os.path.join(output_dir, "index.html")
    assert os.path.exists(index_path)

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "<title>Test BBS Message Archive</title>" in content
        assert "<h1>Test BBS Message Archive</h1>" in content
        assert "<h2>General (Conference 1)</h2>" in content
        assert "<td>Sysop [Admin]</td>" in content
        assert 'href="001-00001-welcome.html"' in content
        assert "Welcome | To BBS" in content
        # Check attachment count display
        assert "<td>1</td>" in content  # For first message
        assert "<td></td>" in content  # For second message (empty)


def test_write_markdown_index(tmp_path, sample_info):
    output_dir = str(tmp_path)
    bbs_info = BBSInfo(name="Test BBS")
    settings = _make_settings(format="markdown")

    _write_index(sample_info, output_dir, settings, bbs_info)

    index_path = os.path.join(output_dir, "README.md")
    assert os.path.exists(index_path)

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Test BBS Message Archive" in content
        assert "## General (Conference 1)" in content
        # Check escaping in Markdown (from esc_md)
        assert "Sysop \\[Admin\\]" in content
        assert "Welcome \\| To BBS" in content
        assert "| 1 | 01-01-23 12:00 |" in content
        assert "[Welcome \\| To BBS](001-00001-welcome.html)" in content
        # Check attachment count
        assert "| 1 |" in content
        assert "|  |" in content


def test_write_index_empty_info(tmp_path):
    output_dir = str(tmp_path)
    settings = _make_settings(format="html")

    _write_index([], output_dir, settings)

    assert not os.path.exists(os.path.join(output_dir, "index.html"))


def test_write_index_no_output_dir(sample_info):
    settings = _make_settings(format="html")
    # Should not raise exception
    _write_index(sample_info, None, settings)


def test_write_index_default_title(tmp_path, sample_info):
    output_dir = str(tmp_path)
    settings = _make_settings(format="html")

    _write_index(sample_info, output_dir, settings, bbs_info=None)

    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "<h1>Message Archive</h1>" in content
