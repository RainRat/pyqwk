import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock
import pyqwk.cli as cli
from pyqwk.cli import main

@pytest.fixture
def testdata_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata"

def test_cli_aliases(monkeypatch, testdata_dir):
    """Verify that the new short flags -B, -X, and -O are correctly parsed."""
    input_file = testdata_dir / "messages.dat"

    # Use the new short flags
    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-B", "MyBBS", "-X", "spam", "-O", "author"]
    )

    mock_process = MagicMock()

    # We need to mock process_merged_files because main() calls it for single input
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    assert settings.bbs_names == ["MyBBS"]
    assert settings.exclude_search == "spam"
    assert settings.sort == "author"

def test_bbs_multi_alias(monkeypatch, testdata_dir):
    """Verify that -B can be used multiple times just like --bbs."""
    input_file = testdata_dir / "messages.dat"

    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-B", "BBS1", "-B", "BBS2"]
    )

    mock_process = MagicMock()

    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]
    assert settings.bbs_names == ["BBS1", "BBS2"]

if __name__ == "__main__":
    pytest.main([__file__])
