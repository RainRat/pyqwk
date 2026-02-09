import os
import pytest
from pyqwk.core import ProcessingSettings, process_merged_files, load_data, parse_messages
import logging

def test_merge_archives(tmp_path):
    # Setup paths
    archive1 = "testdata/test1_qwk.zip"
    archive2 = "testdata/test2_qwk.zip"
    output_file = tmp_path / "merged.json"

    logger = logging.getLogger("test")

    # Create settings for merge
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        merge=True,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="auto",
        output_mode="file",
        output_path=str(output_file),
        encoding="cp437"
    )

    # Run merge
    process_merged_files([archive1, archive2], settings, logger)

    # Verify output exists
    assert output_file.exists()

    # Read output and verify message count
    import json
    with open(output_file, "r") as f:
        data = json.load(f)

    # archive1 has 1 message, archive2 has 2 messages
    assert len(data) == 3

    # Verify we have messages from both conferences
    conf_nums = {msg["header"]["confnum"] for msg in data}
    assert 4 in conf_nums  # from archive1
    assert 3 in conf_nums  # from archive2

def test_merge_archives_threading(tmp_path):
    # This is a bit harder to test without specific data,
    # but we can verify that threading doesn't crash
    archive1 = "testdata/test1_qwk.zip"
    archive2 = "testdata/test2_qwk.zip"
    output_file = tmp_path / "merged_threaded.txt"

    logger = logging.getLogger("test")

    settings = ProcessingSettings(
        verbose=True,
        private=True,
        no_header=False,
        truncate_signatures=True,
        cut_quoting=True,
        individual_files=False,
        threaded=True,
        merge=True,
        binaries_removal=True,
        redact_pii=True,
        format="text",
        separator="dashes",
        output_mode="file",
        output_path=str(output_file),
        encoding="cp437"
    )

    process_merged_files([archive1, archive2], settings, logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="cp437")
    assert "Conference: Pnw.Tech" in content
    assert "Conference: Net140.Tech" in content
