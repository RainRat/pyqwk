import sys
import struct
from pathlib import Path

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import parse_messages, process_message


def build_header_bytes(**kwargs) -> bytes:
    defaults = {
        "status": b" ",
        "msgnum": b"1".ljust(7, b" "),
        "msgdate": b"01-01-90",
        "msgtime": b"12:00",
        "msgto": b"To".ljust(25, b" "),
        "msgfrom": b"From".ljust(25, b" "),
        "msgsubject": b"Subj".ljust(25, b" "),
        "msgpassword": b"".ljust(12, b" "),
        "refnum": b"0".ljust(8, b" "),
        "numblocks": b"2".ljust(6, b" "),  # 1 header + 1 body
        "msgflag": b" ",
        "confnum": 1,
        "lognum": 1,
        "nettag": b" ",
    }
    defaults.update(kwargs)
    return struct.pack(
        "<c7s8s5s25s25s25s12s8s6scHHc",
        defaults["status"],
        defaults["msgnum"],
        defaults["msgdate"],
        defaults["msgtime"],
        defaults["msgto"],
        defaults["msgfrom"],
        defaults["msgsubject"],
        defaults["msgpassword"],
        defaults["refnum"],
        defaults["numblocks"],
        defaults["msgflag"],
        defaults["confnum"],
        defaults["lognum"],
        defaults["nettag"],
    )


class TestParserRobustness:
    """Tests for parser recovery from corrupt data."""

    def test_parse_messages_skips_invalid_message_type(self):
        """
        Verify that parse_messages skips blocks with invalid message status types
        and continues to parse subsequent valid messages.
        """
        # Block 0: QWK Header
        qwk_header = b"Produced " + b"\x00" * (128 - 9)

        # Message 1: Valid
        header1 = build_header_bytes(
            msgnum=b"1".ljust(7, b" "),
            msgsubject=b"Valid 1".ljust(25, b" "),
            numblocks=b"2".ljust(6, b" "),
        )
        body1 = b"Body 1".ljust(128, b" ")

        # Message 2: Invalid Status Byte (e.g., 'X')
        # This will raise InvalidMessageTypeError in MessageHeader.from_bytes
        header2 = build_header_bytes(
            status=b"X",
            msgnum=b"2".ljust(7, b" "),
            msgsubject=b"Invalid".ljust(25, b" "),
            numblocks=b"2".ljust(6, b" "),
        )
        body2 = b"Body 2".ljust(128, b" ")  # Should be skipped along with header?

        # Message 3: Valid
        header3 = build_header_bytes(
            msgnum=b"3".ljust(7, b" "),
            msgsubject=b"Valid 2".ljust(25, b" "),
            numblocks=b"2".ljust(6, b" "),
        )
        body3 = b"Body 3".ljust(128, b" ")

        data = bytearray(
            qwk_header + header1 + body1 + header2 + body2 + header3 + body3
        )

        messages = list(parse_messages(data, progress_bar=None))

        # Should recover and return the two valid messages
        assert len(messages) == 2
        assert messages[0].header.msgsubject.strip() == "Valid 1"
        assert messages[1].header.msgsubject.strip() == "Valid 2"

    def test_process_message_with_zero_length_uue_line(self):
        """
        Regression test: Verify that a UUE block with a zero-length line (a single space)
        is correctly identified and removed, reaching the 'end' terminator.
        """
        text = (
            "begin 644 test.txt\r\n"
            "M123456789012345678901234567890123456789012345\r\n"
            " \r\n"
            "end\r\n"
            "Keep this part"
        )
        # process_message arguments:
        # truncate_signatures=False, cut_quoting=False, binaries_removal=True, redact_pii=False
        processed = process_message(text, False, False, True, False)

        assert "M12345" not in processed
        assert "end" not in processed
        assert "Keep this part" in processed
