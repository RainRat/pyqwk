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
        # Depth 0: no indent
        assert "| 1 | 01-01-23 12:00 | A | B | [Root](001.md) |  |" in content
        # Depth 1: └&nbsp;
        assert "| 2 | 01-01-23 12:05 | B | A | └&nbsp;[Reply 1](002.md) |  |" in content
        # Depth 2: &nbsp;&nbsp;└&nbsp;
        assert "| 3 | 01-01-23 12:10 | A | B | &nbsp;&nbsp;└&nbsp;[Reply 2](003.md) |  |" in content
