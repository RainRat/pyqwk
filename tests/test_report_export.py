import logging
import pytest
from pyqwk.core import show_stats, show_info, ProcessingSettings

@pytest.fixture
def mock_logger():
    import unittest.mock
    return unittest.mock.MagicMock(spec=logging.Logger)

@pytest.fixture
def base_settings():
    return ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        quiet=True,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=None,
        encoding="cp437",
    )

def test_stats_export_html(tmp_path, base_settings, mock_logger):
    input_path = "testdata/test1_qwk.zip"
    output_file = tmp_path / "stats.html"

    settings = base_settings
    settings.format = "html"
    settings.output_path = str(output_file)

    show_stats([input_path], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Archive Statistics" in content
    assert "Top Authors" in content
    assert "Warren Zatwarni" in content

def test_stats_export_markdown(tmp_path, base_settings, mock_logger):
    input_path = "testdata/test1_qwk.zip"
    output_file = tmp_path / "stats.md"

    settings = base_settings
    settings.format = "markdown"
    settings.output_path = str(output_file)

    show_stats([input_path], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "# Archive Statistics" in content
    assert "### Archive Summary" in content
    assert "Warren Zatwarni" in content

def test_stats_export_csv(tmp_path, base_settings, mock_logger):
    input_path = "testdata/test1_qwk.zip"
    output_file = tmp_path / "stats.csv"

    settings = base_settings
    settings.format = "csv"
    settings.output_path = str(output_file)

    show_stats([input_path], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "file,total_messages,matching_messages" in content
    assert "testdata/test1_qwk.zip" in content
    assert "Warren Zatwarni" in content


def test_stats_export_csv_edge_cases():
    from pyqwk.core import _render_stats_csv

    # Test handling of None/missing fields without raising exceptions
    sparse_stats = [
        {
            "file": "sparse.qwk",
            "reply_rate": None,
            "avg_message_length": None,
            "avg_word_count": None,
            "conversation": {"avg_thread_length": None},
            "authors": [None, "invalid_author", {"name": "Test", "count": 1}],
            "dates": None,
        }
    ]
    csv_text = _render_stats_csv(sparse_stats)
    assert "file,total_messages,matching_messages" in csv_text
    assert "sparse.qwk" in csv_text
    assert "Test (1)" in csv_text

def test_info_export_html(tmp_path, base_settings, mock_logger):
    input_path = "testdata/test1_qwk.zip"
    output_file = tmp_path / "info.html"

    settings = base_settings
    settings.format = "html"
    settings.output_path = str(output_file)

    show_info([input_path], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Archive Information" in content
    assert "BBS Name:" in content
    assert "Benden Weyr" in content

def test_info_export_markdown(tmp_path, base_settings, mock_logger):
    input_path = "testdata/test1_qwk.zip"
    output_file = tmp_path / "info.md"

    settings = base_settings
    settings.format = "markdown"
    settings.output_path = str(output_file)

    show_info([input_path], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "# Archive Information" in content
    assert "## File: testdata/test1_qwk.zip" in content
    assert "**BBS Name:** Benden Weyr" in content
