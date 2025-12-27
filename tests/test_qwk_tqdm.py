import sys
import logging
import pytest
from pathlib import Path
from contextlib import nullcontext
import importlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import _create_progress_bar

@pytest.fixture
def clean_tqdm():
    """Ensure tqdm is clean in sys.modules before and after test."""
    original = sys.modules.get("tqdm")
    yield
    if original is None:
        sys.modules.pop("tqdm", None)
    else:
        sys.modules["tqdm"] = original

def test_create_progress_bar_logs_missing_tqdm_only_once(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, clean_tqdm) -> None:
    # Simulate tqdm missing by mocking the import
    if 'tqdm' in sys.modules:
        del sys.modules['tqdm']

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

def test_progress_bar_quiet_mode() -> None:
    """Verify that quiet mode returns a null context."""
    bar = _create_progress_bar(total=100, quiet=True)
    assert isinstance(bar, nullcontext)

@pytest.fixture
def ensure_tqdm():
    """Ensure tqdm is available for the test."""
    if 'tqdm' in sys.modules and sys.modules['tqdm'] is None:
        del sys.modules['tqdm']

    # Try importing it to verify availability
    try:
        import tqdm
    except ImportError:
        pytest.skip("tqdm not installed")

    yield

    # No teardown needed usually, unless we want to be super clean

def test_progress_bar_active(ensure_tqdm) -> None:
    """Verify that a real progress bar is returned when not quiet and tqdm is installed."""
    # This assumes tqdm is installed in the test environment (which we did)
    # We must ensure tqdm is actually importable here
    try:
        import tqdm
    except ImportError:
        pytest.skip("tqdm not installed")

    bar = _create_progress_bar(total=100, quiet=False)
    assert not isinstance(bar, nullcontext)
    # Check for tqdm interface
    assert hasattr(bar, "update")
    assert hasattr(bar, "close")
