import sys
from pathlib import Path
import struct
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import MessageHeader, MessagesDatFormatError

def build_header_bytes(**kwargs) -> bytes:
    """Helper to construct a 128-byte messages.dat header record."""
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
        'numblocks': b"1".ljust(6, b' '),
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

class TestMessageHeader:
    """Unit tests for MessageHeader parsing logic."""

    def test_from_bytes_handles_null_padding(self):
        # Construct a header with null padding instead of space padding
        # msgnum: "123\x00\x00\x00\x00" (7 bytes)
        # msgto: "User\x00..." (25 bytes)
        raw_msgnum = b'123\x00\x00\x00\x00'
        raw_msgto = b'UserName'.ljust(25, b'\x00')
        raw_msgfrom = b'Sender  '.ljust(25, b'\x00')

        record = build_header_bytes(
            msgnum=raw_msgnum,
            msgto=raw_msgto,
            msgfrom=raw_msgfrom,
            refnum=b'456\x00\x00\x00\x00\x00'
        )

        header, _, _ = MessageHeader.from_bytes(record)

        # Should parse number correctly
        assert header.msgnum == 123
        assert header.refnum == 456

        # Should strip nulls from string fields
        assert header.msgto == "UserName"
        assert "\x00" not in header.msgto

        # Should preserve whitespace in msgfrom but remove nulls
        # "Sender  " + nulls -> "Sender  "
        assert header.msgfrom == "Sender  "

    def test_from_bytes_raises_on_invalid_size(self):
        # Record must be exactly 128 bytes
        invalid_record = b'\x00' * 127
        with pytest.raises(MessagesDatFormatError) as exc:
            MessageHeader.from_bytes(invalid_record)
        assert "invalid size" in str(exc.value)

        invalid_record_long = b'\x00' * 129
        with pytest.raises(MessagesDatFormatError) as exc:
            MessageHeader.from_bytes(invalid_record_long)
        assert "invalid size" in str(exc.value)

    def test_refnum_parsing(self):
        # "0" should be None
        record = build_header_bytes(refnum=b"0".ljust(8, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.refnum is None

        # "000" should be None
        record = build_header_bytes(refnum=b"000".ljust(8, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.refnum is None

        # "123" should be 123
        record = build_header_bytes(refnum=b"123".ljust(8, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.refnum == 123

        # "garbage" should be None
        record = build_header_bytes(refnum=b"garbage".ljust(8, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.refnum is None

    def test_numblocks_parsing(self):
        # Valid integer
        record = build_header_bytes(numblocks=b"5".ljust(6, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.numblocks == 5
        assert header._numblocks_raw == "5"

        # Invalid integer -> None
        record = build_header_bytes(numblocks=b"NaN".ljust(6, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.numblocks is None
        assert header._numblocks_raw == "NaN"

    def test_msgnum_parsing_invalid(self):
        # Invalid integer -> None
        record = build_header_bytes(msgnum=b"NaN".ljust(7, b' '))
        header, _, _ = MessageHeader.from_bytes(record)
        assert header.msgnum is None
