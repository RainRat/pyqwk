import time

from pyqwk.core import RE_PHONE_PATTERN
from pyqwk.gui import QwkGuiApp, _normalize_display_text


def test_normalize_display_text_removes_carriage_returns():
    assert _normalize_display_text("one\r\ntwo\rthree\nfour") == "one\ntwo\nthree\nfour"
    assert "\r" not in _normalize_display_text("a\r\nb\rc")


def test_normalize_display_text_leaves_plain_text_unchanged():
    assert _normalize_display_text("plain text\n") == "plain text\n"


def test_source_metadata_hidden_for_single_archive():
    app = QwkGuiApp.__new__(QwkGuiApp)
    app.current_paths = ["archive.qwk"]
    assert app._show_source_metadata() is False


def test_source_metadata_shown_for_multiple_archives():
    app = QwkGuiApp.__new__(QwkGuiApp)
    app.current_paths = ["one.qwk", "two.qwk"]
    assert app._show_source_metadata() is True


def test_source_metadata_hidden_when_no_archive_is_loaded():
    app = QwkGuiApp.__new__(QwkGuiApp)
    assert app._show_source_metadata() is False


def test_phone_matcher_stays_fast_on_long_mixed_runs():
    """Regression: the old lookahead backtracked quadratically on this shape."""
    text = "a1-" * 16000  # 48 KB, ~17 s with the previous expression
    started = time.perf_counter()
    assert RE_PHONE_PATTERN.findall(text) == []
    assert time.perf_counter() - started < 1.0
