import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import process_message

class TestPhoneRedaction:
    """Tests for phone number redaction logic."""

    @pytest.mark.parametrize("phone_number", [
        "555-1234",
        "555 1234",
        "(555) 123-4567",
        "(555) 123 4567",
        "555.123.4567",
        "+1-555-123-4567",
        "1-800-555-1212",
        "020 7946 0123",  # UK formatish
        "123-456-7890",
        "1234 567 890",
    ])
    def test_redacts_valid_phone_numbers(self, phone_number):
        msg = f"Call me at {phone_number}."
        processed = process_message(
            msg,
            truncate_signatures=False,
            cut_quoting=False,
            binaries_removal=False,
            redact_pii=True
        )
        assert "[PHONE]" in processed
        assert phone_number not in processed

    @pytest.mark.parametrize("safe_text", [
        "12345",         # Too short
        "12-34",         # Too short
        "1999-12-31",    # Date (19xx)
        "2023-10-27",    # Date (20xx)
        "2000-01-01",    # Date (2000)
        "10.0.0.1",      # IP Address (looks like 2-1-1-1 digits, fails {3,4} check usually)
        "127.0.0.1",     # IP
        "v1.2.3",        # Version
        "$1,234.56",     # Currency
        "100 - 200",     # Math
        "Model 1234",    # ID
    ])
    def test_does_not_redact_non_phone_numbers(self, safe_text):
        msg = f"Value is {safe_text}."
        processed = process_message(
            msg,
            truncate_signatures=False,
            cut_quoting=False,
            binaries_removal=False,
            redact_pii=True
        )
        assert safe_text in processed
        assert "[PHONE]" not in processed

    def test_preserves_dates_pre_1900(self):
        # The regex has negative lookahead for 19xx and 20xx.
        # But 1800-01-01 should theoretically be preserved if it doesn't look like a phone number.
        # 1800-01-01: "1800" (4), "01" (2), "01" (2).
        # Phone regex expects blocks of 3 or 4 digits. "01" is 2.
        # So it should NOT match.
        date_str = "1850-12-25"
        processed = process_message(
            f"Born on {date_str}.",
            truncate_signatures=False,
            cut_quoting=False,
            binaries_removal=False,
            redact_pii=True
        )
        assert date_str in processed
        assert "[PHONE]" not in processed

    def test_redacts_embedded_phone_numbers(self):
        msg = "Call (555) 123-4567 or (555) 987-6543 immediately."
        processed = process_message(
            msg,
            truncate_signatures=False,
            cut_quoting=False,
            binaries_removal=False,
            redact_pii=True
        )
        assert processed.count("[PHONE]") == 2
        assert "555" not in processed

class TestEmailRedaction:
    """Tests for email redaction logic."""

    @pytest.mark.parametrize("email", [
        "user@example.com",
        "first.last@domain.co.uk",
        "user123@sub.domain.org",
        "email+tag@example.com",
    ])
    def test_redacts_valid_emails(self, email):
        msg = f"Email me at {email} please."
        processed = process_message(
            msg,
            truncate_signatures=False,
            cut_quoting=False,
            binaries_removal=False,
            redact_pii=True
        )
        assert "[EMAIL]" in processed
        assert email not in processed

    @pytest.mark.parametrize("safe_text", [
        "user at example dot com",
        "@handle",
        "example.com",
        "user@",
        "@domain",
    ])
    def test_does_not_redact_invalid_emails(self, safe_text):
        msg = f"Contact {safe_text}."
        processed = process_message(
            msg,
            truncate_signatures=False,
            cut_quoting=False,
            binaries_removal=False,
            redact_pii=True
        )
        assert safe_text in processed
        assert "[EMAIL]" not in processed
