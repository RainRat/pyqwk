import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import _is_binary_line

class TestBinaryDetection:
    """Unit tests for the _is_binary_line function."""

    def test_detects_yenc_start(self):
        line = "=ybegin line=128 size=12345 name=test.zip"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False
        )
        assert skip is True
        assert in_yenc is True
        assert in_uue is False

    def test_detects_yenc_body(self):
        line = "random_yenc_data"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=True, in_uue_block=False
        )
        assert skip is True
        assert in_yenc is True
        assert in_uue is False

    def test_detects_yenc_end(self):
        line = "=yend size=12345 crc32=12345678"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=True, in_uue_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is False

    def test_detects_uue_start(self):
        line = "begin 644 test.txt"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_data_strict(self):
        # Strict UUE line starts with 'M' and is 61 chars long (M + 60 chars)
        line = "M" + ("A" * 60)
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_loose_inside_block(self):
        # Loose pattern allows other start chars and lengths
        line = "L" + ("A" * 50)
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_loose_outside_block_with_predecessor(self):
        # If we are NOT in a block, but previous line was UUE, we should enter block/skip
        line = "L" + ("A" * 50)
        previous = "M" + ("A" * 60)
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=previous, in_yenc_block=False, in_uue_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_ignores_uue_loose_outside_block_without_predecessor(self):
        # Loose pattern on its own should not trigger UUE if not already in block or following UUE
        line = "L" + ("A" * 50)
        previous = "Normal line"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=previous, in_yenc_block=False, in_uue_block=False
        )
        assert skip is False
        assert in_yenc is False
        assert in_uue is False

    def test_detects_uue_end(self):
        line = "end"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is False

    def test_exits_uue_on_invalid_line(self):
        line = "Not a uue line"
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True
        )
        assert skip is False
        assert in_yenc is False
        assert in_uue is False

    def test_detects_base64(self):
        line = "VGhpcyBpcyBhIHRlc3QgbWVzc2FnZQ==" # Base64 for "This is a test message"
        # It needs to be at least 60 chars according to RE_BASE64_PATTERN in qwk.py
        line = "A" * 65
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False
        )
        assert skip is True
        # Base64 doesn't set a state in this implementation, it just skips
        assert in_yenc is False
        assert in_uue is False

    def test_base64_preserves_state(self):
        # If we happen to see base64 inside a yenc block (unlikely but possible), state should be preserved
        line = "A" * 65
        skip, in_yenc, in_uue = _is_binary_line(
            line, previous_line=None, in_yenc_block=True, in_uue_block=False
        )
        assert skip is True
        assert in_yenc is True
        assert in_uue is False
