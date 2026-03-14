import pytest
import sys
from pyqwk.cli import main

def test_stats_multiple_files_no_output(monkeypatch, capsys):
    """Test that --stats works with multiple files without requiring -o."""
    # testdata/test1_qwk.zip and testdata/test2_qwk.zip exist
    test1 = "testdata/test1_qwk.zip"
    test2 = "testdata/test2_qwk.zip"

    # Simulate: qwk.py testdata/test1_qwk.zip testdata/test2_qwk.zip --stats
    monkeypatch.setattr(sys, "argv", ["qwk.py", test1, test2, "--stats", "--quiet"])

    # Should not raise SystemExit(2) from argparse.error
    try:
        main()
    except SystemExit as e:
        if e.code != 0:
            pytest.fail(f"main() exited with code {e.code}")

    captured = capsys.readouterr()
    assert "Statistics for: testdata/test1_qwk.zip" in captured.out
    assert "Statistics for: testdata/test2_qwk.zip" in captured.out
    assert "Messages: 1 matching / 1 total" in captured.out
    assert "Messages: 2 matching / 2 total" in captured.out

def test_info_multiple_files_no_output(monkeypatch, capsys):
    """Test that --info already works with multiple files without requiring -o (baseline)."""
    test1 = "testdata/test1_qwk.zip"
    test2 = "testdata/test2_qwk.zip"

    monkeypatch.setattr(sys, "argv", ["qwk.py", test1, test2, "--info", "--quiet"])

    try:
        main()
    except SystemExit as e:
        if e.code != 0:
            pytest.fail(f"main() exited with code {e.code}")

    captured = capsys.readouterr()
    assert "File: testdata/test1_qwk.zip" in captured.out
    assert "File: testdata/test2_qwk.zip" in captured.out
