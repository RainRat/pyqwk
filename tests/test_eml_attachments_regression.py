import unittest
import base64
from pyqwk.core import MessageHeader, ProcessedMessage, _serialize_rfc822, _bytes_to_uue

class TestEMLAttachmentsRegression(unittest.TestCase):
    def test_serialize_rfc822_preserves_attachments_from_original_text(self):
        header = MessageHeader(
            status=" ",
            msgnum=1,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Recipient",
            msgfrom="Author",
            msgsubject="Test Subject",
            msgpassword="",
            refnum=0,
            numblocks=1,
            msgflag="",
            confnum=1,
            lognum=0,
            nettag=""
        )

        # Create a valid UUE block using the internal helper
        test_data = b"Hello, this is a test attachment."
        uue_block = _bytes_to_uue(test_data, "test.txt")

        # Scenario: body is cleaned (binaries removed), but they are in original_text
        msg = ProcessedMessage(
            header=header,
            text="This is the clean body.\n",
            original_text="This is the original body.\n" + uue_block,
            confnum=1,
            depth=0,
            msgnum=1,
            refnum=0
        )

        # Act
        eml = _serialize_rfc822(msg, include_mbox_header=False)

        # Assert: The attachment should be present in the EML output
        self.assertIn('Content-Disposition: attachment; filename="test.txt"', eml)

        # The test_data should be base64 encoded in the EML
        expected_b64 = base64.b64encode(test_data).decode('ascii')
        self.assertIn(expected_b64, eml)

if __name__ == "__main__":
    unittest.main()
