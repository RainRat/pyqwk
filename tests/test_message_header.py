import sys
from pathlib import Path
import struct
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import MessageHeader, MessagesDatFormatError, InvalidMessageTypeError

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

class TestMessageHeaderParsing:
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

    def test_status_flags_parsing(self) -> None:
        """Verify that status bytes correctly map to private/password flags."""
        for status in [b'+', b'*', b'~', b'`']:
            _, is_private, is_password = MessageHeader.from_bytes(build_header_bytes(status=status))
            assert is_private is True
            assert is_password is False

        for status in [b'%', b'^', b'!', b'#', b'$']:
            _, is_private, is_password = MessageHeader.from_bytes(build_header_bytes(status=status))
            assert is_private is True
            assert is_password is True

        for status in [b' ', b'-']:
            _, is_private, is_password = MessageHeader.from_bytes(build_header_bytes(status=status))
            assert is_private is False
            assert is_password is False

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(InvalidMessageTypeError) as exc_info:
            MessageHeader.from_bytes(build_header_bytes(status=b'X'))

        assert exc_info.value.message_type == 'X'


class TestMessageHeaderFormatting:
    """Unit tests for MessageHeader formatting and serialization logic."""

    @pytest.fixture
    def sample_header(self) -> MessageHeader:
        return MessageHeader(
            status=' ',
            msgnum=100,
            msgdate='01-01-90',
            msgtime='12:00',
            msgto='All Users',
            msgfrom='SysOp',
            msgsubject='Welcome!',
            msgpassword='',
            refnum=99,
            numblocks=1,
            msgflag=' ',
            confnum=1,
            lognum=0,
            nettag='',
        )

    def test_format_text_basic(self, sample_header: MessageHeader) -> None:
        """Test default formatting (verbose=False, conf found)."""
        board_dict = {1: "General"}
        text = sample_header.format_text(board_dict, verbose=False)

        assert "Conference: General" in text
        assert "Date: 01-01-90 12:00" in text
        assert "From: SysOp" in text
        assert "To: All Users" in text
        assert "Subject: Welcome!" in text
        assert "Message number:" not in text
        assert "Reference number:" not in text
        assert text.startswith("-" * 80)

    def test_format_text_conf_not_found(self, sample_header: MessageHeader) -> None:
        """Test formatting when conference is missing from board_dict."""
        board_dict: dict[int, str] = {}
        # verbose=False, conf not found -> "Conference: ..." line should be omitted
        text = sample_header.format_text(board_dict, verbose=False)

        assert "Conference:" not in text
        assert "Date: 01-01-90 12:00" in text

    def test_format_text_verbose(self, sample_header: MessageHeader) -> None:
        """Test verbose formatting."""
        board_dict = {1: "General"}
        text = sample_header.format_text(board_dict, verbose=True)

        assert "Conference: General" in text
        assert "Message number: 100" in text
        assert "Reference number: 99" in text
        # Check layout: Message number is followed by Date on the same line (sort of)
        # qwk.py: header_parts.append("Message number: " + message_number + (" " * 20))
        #         header_parts.append("Date: " + self.msgdate ...)
        # So it should be "Message number: 100                    Date: ..."
        assert "Message number: 100                    Date: 01-01-90 12:00" in text

    def test_format_text_verbose_conf_not_found(self, sample_header: MessageHeader) -> None:
        """Test verbose formatting when conference is missing."""
        board_dict: dict[int, str] = {}
        text = sample_header.format_text(board_dict, verbose=True)

        # verbose=True forces conference display even if not found, using the number
        assert "Conference: 1" in text

    def test_format_text_no_separator(self, sample_header: MessageHeader) -> None:
        """Test formatting without leading separator."""
        board_dict = {1: "General"}
        text = sample_header.format_text(board_dict, verbose=False, include_separator=False)

        assert not text.startswith("-")
        assert "Conference: General" in text

    def test_as_dict(self, sample_header: MessageHeader) -> None:
        """Test conversion to dictionary."""
        d = sample_header.as_dict

        assert d['msgnum'] == 100
        assert d['msgto'] == 'All Users'
        assert d['refnum'] == 99
        assert d['confnum'] == 1

    def test_as_dict_handles_none(self, sample_header: MessageHeader) -> None:
        """Test that None values are converted to empty strings in as_dict."""
        sample_header.msgnum = None
        sample_header.refnum = None

        d = sample_header.as_dict
        assert d['msgnum'] == ""
        assert d['refnum'] == ""
