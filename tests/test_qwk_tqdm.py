import sys
import logging
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import _create_progress_bar

def test_create_progress_bar_logs_missing_tqdm_only_once(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    # Simulate tqdm missing by mocking the import
    monkeypatch.setitem(sys.modules, "tqdm", None)

    # Reset state
    if hasattr(_create_progress_bar, "_logged_missing_tqdm"):
        delattr(_create_progress_bar, "_logged_missing_tqdm")

    with caplog.at_level(logging.INFO):
        # First call should log
        _create_progress_bar(100, quiet=False)
        # Second call should not log
        _create_progress_bar(100, quiet=False)

    # Should appear exactly once
    assert caplog.text.count("Install tqdm") == 1
