import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import process_message

def test_process_message_transforms_content() -> None:
    message = (
        "Intro line\r\n"
        "> quoted text that should be removed\r\n"
        "Another line\r\n"
        "Contact: someone@example.com or 555-123-4567\r\n"
        "-----BEGIN PGP SIGNATURE-----\r\n"
        "Signature block\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=True,
        cut_quoting=True,
        binaries_removal=False,
        redact_pii=True,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
        "Contact: [EMAIL] or [PHONE]\r\n"
    )


def test_process_message_preserves_dates_when_redacting() -> None:
    message = "On 1994-10-05, call 555-123-4567.\r\n"

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=True,
    )

    assert "1994-10-05" in processed
    assert "[PHONE]" in processed


def test_process_message_redacts_local_numbers() -> None:
    message = "Local contact: 555-1234 or 555 6789.\r\n"

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=True,
    )

    assert processed == "Local contact: [PHONE] or [PHONE].\r\n"


def test_process_message_removes_yenc_binaries() -> None:
    message = (
        "Intro line\r\n"
        "=ybegin line=128 size=12345 name=test.zip\r\n"
        "yEnc encoded data\r\n"
        "=ypart begin=1 end=1024\r\n"
        "more yEnc data\r\n"
        "=yend size=12345 crc32=12345678\r\n"
        "Another line\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
    )


def test_process_message_removes_base64_binaries() -> None:
    message = (
        "Intro line\r\n"
        "VGhpcyBpcyBhIHRlc3QgbWVzc2FnZSB3aXRoIGEgbG9uZyBtdWx0aS1saW5lIEJhc2U2NCBibG9jaw0K"
        "aW4gdGhlIG1pZGRsZS4NCg==\r\n"
        "Another line\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
    )


def test_process_message_removes_uue_binaries() -> None:
    message = (
        "Intro line\r\n"
        "begin 644 test.txt\r\n"
        "M" + ("A" * 60) + "\r\n"
        "Another line\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
    )

def test_process_message_preserves_leading_whitespace() -> None:
    message = "   Indented line\r\nNormal line"
    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=False,
    )
    assert processed == "   Indented line\r\nNormal line\r\n"

# New Tests

def test_process_message_handles_sandwich_quoting() -> None:
    message = (
        "> line 1\r\n"
        "wrapped line\r\n"
        "> line 3\r\n"
        "keep me\r\n"
    )
    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=True,
        binaries_removal=False,
        redact_pii=False,
    )
    assert processed == "keep me\r\n"

def test_process_message_handles_cp437_quoting() -> None:
    # 0xB3 in CP437 is U+2502 (│)
    # This simulates a message decoded with cp437
    quote_char = b'\xb3'.decode('cp437')
    message = (
        f"{quote_char} quoted line\r\n"
        "keep me\r\n"
    )
    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=True,
        binaries_removal=False,
        redact_pii=False,
    )
    assert processed == "keep me\r\n"

def test_process_message_handles_cp437_signature() -> None:
    # 0xFE in CP437 is U+25A0 (■)
    sig_char = b'\xfe'.decode('cp437')
    message = (
        "Body\r\n"
        f" {sig_char} Signature start\r\n"
        "Signature line\r\n"
    )
    processed = process_message(
        message,
        truncate_signatures=True,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=False,
    )
    assert processed == "Body\r\n"

def test_process_message_handles_uue_loose_pattern() -> None:
    # Test that loose UUE pattern is removed if following a strict pattern
    message = (
        "Intro\r\n"
        "begin 644 test.txt\r\n"
        "M" + ("A" * 60) + "\r\n" # Strict UUE Data
        + ("A" * 60) + "\r\n"    # Loose UUE Data
        "end\r\n"
    )
    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )
    # The current implementation might be strict about what terminates UUE.
    # _is_binary_line returns True as long as loose matches if previous matched.
    # "end" does NOT match loose pattern (len 3). So it should stop skipping.
    assert processed == "Intro\r\n"


def test_process_message_redacts_complex_phone_formats() -> None:
    message = (
        "(555) 123-4567\r\n"
        "+61-5-555-1234\r\n"
        "Call me at 555-1234\r\n"
        "123-456-7890\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=True,
    )

    expected = (
        "[PHONE]\r\n"
        "[PHONE]\r\n"
        "Call me at [PHONE]\r\n"
        "[PHONE]\r\n"
    )
    assert processed == expected

def test_process_message_removes_consecutive_loose_uue_lines() -> None:
    # Test case for UUE removal where loose binary lines follow each other
    message = (
        "Intro\r\n"
        "begin 644 test.txt\r\n" # Strict UUE header
        "M" + ("!" * 60) + "\r\n" # Strict UUE data
        "L" + ("!" * 50) + "\r\n" # Loose UUE data (previous was strict)
        "K" + ("!" * 50) + "\r\n" # Loose UUE data (previous was loose)
        "end\r\n"
        "Outro\r\n"
    )
    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )
    assert processed == "Intro\r\nOutro\r\n"
