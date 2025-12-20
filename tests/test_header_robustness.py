import sys
from pathlib import Path
import struct
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import MessageHeader

def test_header_from_bytes_handles_null_padding():
    # Construct a header with null padding instead of space padding
    # msgnum: "123\x00\x00\x00\x00" (7 bytes)
    # msgto: "User\x00..." (25 bytes)

    raw_msgnum = b'123\x00\x00\x00\x00'
    raw_msgto = b'UserName'.ljust(25, b'\x00')
    raw_msgfrom = b'Sender  '.ljust(25, b'\x00') # Check that it preserves spaces but removes nulls

    # We use a helper to pack default values
    def build_header(**kwargs):
        defaults = {
            'status': b' ',
            'msgnum': b"1".ljust(7, b' '),
            'msgdate': b"01-01-90", # 8s
            'msgtime': b"12:00", # 5s
            'msgto': b"To".ljust(25, b' '),
            'msgfrom': b"From".ljust(25, b' '),
            'msgsubject': b"Subj".ljust(25, b' '),
            'msgpassword': b"".ljust(12, b' '),
            'refnum': b"0".ljust(8, b' '),
            'numblocks': b"0".ljust(6, b' '),
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

    record = build_header(
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
