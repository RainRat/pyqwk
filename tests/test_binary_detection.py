import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import _is_binary_line

class TestBinaryDetection:
    """Unit tests for the _is_binary_line function."""

    def test_detects_yenc_start(self):
        line = "=ybegin line=128 size=12345 name=test.zip"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is True
        assert in_uue is False

    def test_detects_multi_line_base64_block(self):
        # Test that multiple lines of base64 are skipped, including a short trailing one
        line1 = "A" * 65 # Strict
        line2 = "B" * 65 # Strict
        line3 = "C" * 20 # Loose
        line4 = "Normal Text"

        # Line 1: Strict -> Enter block
        skip1, in_yenc1, in_uue1, in_b64_1 = _is_binary_line(
            line1, None, False, False, False
        )
        assert skip1 is True
        assert in_b64_1 is True

        # Line 2: Strict while in block -> Stay in block
        skip2, in_yenc2, in_uue2, in_b64_2 = _is_binary_line(
            line2, line1, in_yenc1, in_uue1, in_b64_1
        )
        assert skip2 is True
        assert in_b64_2 is True

        # Line 3: Loose while in block -> Stay in block/Skip
        skip3, in_yenc3, in_uue3, in_b64_3 = _is_binary_line(
            line3, line2, in_yenc2, in_uue2, in_b64_2
        )
        assert skip3 is True
        assert in_b64_3 is True

        # Line 4: Normal text -> Exit block/Keep
        skip4, in_yenc4, in_uue4, in_b64_4 = _is_binary_line(
            line4, line3, in_yenc3, in_uue3, in_b64_3
        )
        assert skip4 is False
        assert in_b64_4 is False

    def test_uue_backtick_inside_block(self):
        # Backtick is a valid UUE terminator and should exit the block
        line = "`"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True, in_base64_block=False
        )
        assert skip is True
        assert in_uue is False

    def test_uue_exits_on_non_uue_data(self):
        # Improved logic should exit UUE block if line is not UUE data or terminator
        line = "This is not UUE data"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True, in_base64_block=False
        )
        assert skip is False
        assert in_uue is False

    def test_detects_yenc_body(self):
        line = "random_yenc_data"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=True, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is True
        assert in_uue is False

    def test_detects_yenc_end(self):
        line = "=yend size=12345 crc32=12345678"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=True, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is False

    def test_detects_uue_start(self):
        line = "begin 644 test.txt"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_start_multiple_spaces(self):
        line = "begin  644  test.txt"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_data_strict(self):
        # Strict UUE line starts with 'M' and is 61 chars long (M + 60 chars)
        line = "M" + ("A" * 60)
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_loose_inside_block(self):
        # Loose pattern allows other start chars and lengths
        line = "L" + ("A" * 50)
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_detects_uue_loose_outside_block_with_predecessor(self):
        # If we are NOT in a block, but previous line was UUE, we should enter block/skip
        line = "L" + ("A" * 50)
        previous = "M" + ("A" * 60)
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=previous, in_yenc_block=False, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is True

    def test_ignores_uue_loose_outside_block_without_predecessor(self):
        # Loose pattern on its own should not trigger UUE if not already in block or following UUE
        line = "L" + ("A" * 50)
        previous = "Normal line"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=previous, in_yenc_block=False, in_uue_block=False, in_base64_block=False
        )
        assert skip is False
        assert in_yenc is False
        assert in_uue is False

    def test_detects_uue_end(self):
        line = "end"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is False
        assert in_uue is False

    def test_exits_uue_on_invalid_line(self):
        line = "Not a uue line"
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=True, in_base64_block=False
        )
        # We should exit UUE block if it's garbage
        assert skip is False
        assert in_yenc is False
        assert in_uue is False

    def test_detects_base64(self):
        line = "VGhpcyBpcyBhIHRlc3QgbWVzc2FnZQ==" # Base64 for "This is a test message"
        # It needs to be at least 60 chars according to RE_BASE64_PATTERN in qwk.py
        line = "A" * 65
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=False, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_b64 is True
        assert in_yenc is False
        assert in_uue is False

    def test_base64_preserves_state(self):
        # If we happen to see base64 inside a yenc block (unlikely but possible), state should be preserved
        line = "A" * 65
        skip, in_yenc, in_uue, in_b64 = _is_binary_line(
            line, previous_line=None, in_yenc_block=True, in_uue_block=False, in_base64_block=False
        )
        assert skip is True
        assert in_yenc is True
        assert in_uue is False
