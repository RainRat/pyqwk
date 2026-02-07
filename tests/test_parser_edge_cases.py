
import sys
import struct
import pytest
from pathlib import Path

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import parse_messages, MessagesDatFormatError

def build_header_bytes(**kwargs) -> bytes:
    defaults = {
        'status': b' ',
        'msgnum': b"1".ljust(7, b' '),
        'msgdate': b"01-01-90",
        'msgtime': b"12:00",
        'msgto': b"To".ljust(25, b' '),
        'msgfrom': b"From".ljust(25, b' '),
        'msgsubject': b"Subj".ljust(25, b' '),
        'msgpassword': b"".ljust(12, b' '),
        'refnum': b"0".ljust(8, b' '),
        'numblocks': b"2".ljust(6, b' '), # 1 header + 1 body
        'msgflag': b' ',
        'confnum': 1,
        'lognum': 1,
        'nettag': b' ',
    }
    defaults.update(kwargs)
    return struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        defaults['status'],
        defaults['msgnum'],
        defaults['msgdate'],
        defaults['msgtime'],
        defaults['msgto'],
        defaults['msgfrom'],
        defaults['msgsubject'],
        defaults['msgpassword'],
        defaults['refnum'],
        defaults['numblocks'],
        defaults['msgflag'],
        defaults['confnum'],
        defaults['lognum'],
        defaults['nettag'],
    )

class TestParserEdgeCases:
    """Tests for additional parser edge cases."""

    def test_parse_messages_with_numblocks_one(self):
        """
        Verify that numblocks=1 yields a message with an empty body.
        """
        qwk_header = b'Produced ' + b'\x00' * (128 - 9)
        # numblocks=1 means only the header block exists
        header = build_header_bytes(numblocks=b"1".ljust(6, b' '))

        data = bytearray(qwk_header + header)
        messages = list(parse_messages(data, progress_bar=None))

        assert len(messages) == 1
        assert messages[0].text == ""

    def test_parse_messages_skips_invalid_numblocks(self, caplog):
        """
        Verify that numblocks < 1 causes the message to be skipped.
        """
        qwk_header = b'Produced ' + b'\x00' * (128 - 9)

        # Message 1: numblocks=0 (invalid)
        header1 = build_header_bytes(msgnum=b"1".ljust(7, b' '), numblocks=b"0".ljust(6, b' '))

        # Message 2: Valid
        header2 = build_header_bytes(msgnum=b"2".ljust(7, b' '), numblocks=b"2".ljust(6, b' '))
        body2 = b"Body 2".ljust(128, b' ')

        data = bytearray(qwk_header + header1 + header2 + body2)
        messages = list(parse_messages(data, progress_bar=None))

        assert len(messages) == 1
        assert messages[0].msgnum == 2
        assert "Invalid block count '0'" in caplog.text

    def test_parse_messages_raises_on_truncation(self):
        """
        Verify that a truncated file raises MessagesDatFormatError.
        """
        qwk_header = b'Produced ' + b'\x00' * (128 - 9)

        # Header claims 3 blocks (1 header + 2 body)
        header = build_header_bytes(numblocks=b"3".ljust(6, b' '))
        # But we only provide 1 body block
        body1 = b"Body 1".ljust(128, b' ')

        data = bytearray(qwk_header + header + body1)

        with pytest.raises(MessagesDatFormatError) as exc:
            list(parse_messages(data, progress_bar=None))

        assert "is truncated" in str(exc.value)

    def test_parse_messages_with_zero_length_data(self):
        """
        Verify that zero-length data raises MessagesDatFormatError.
        """
        data = bytearray(b'')

        with pytest.raises(MessagesDatFormatError) as exc:
            list(parse_messages(data, progress_bar=None))

        assert "Input too short" in str(exc.value)

    def test_parse_messages_with_insufficient_data_for_header(self):
        """
        Verify that data shorter than BLOCK_SIZE raises MessagesDatFormatError.
        """
        data = bytearray(b'Produced ') # 9 bytes

        with pytest.raises(MessagesDatFormatError) as exc:
            list(parse_messages(data, progress_bar=None))

        assert "Input too short" in str(exc.value)
