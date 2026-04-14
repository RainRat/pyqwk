import unittest
import os
import tempfile
import shutil
import logging
from pyqwk.core import (
    load_data,
    ProcessingSettings,
    process_merged_files,
)

class TestMarkdownImport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.logger = logging.getLogger("pyqwk_test")
        self.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_markdown_round_trip(self):
        # 1. Create a sample archive or use existing test data
        # We'll use testdata/test1_qwk.zip
        input_path = "testdata/test1_qwk.zip"
        if not os.path.exists(input_path):
            self.skipTest("testdata/test1_qwk.zip not found")

        markdown_path = os.path.join(self.test_dir, "test_output.md")

        # 2. Export to Markdown
        settings_export = ProcessingSettings(
            verbose=True,
            private=True,
            no_header=False,
            truncate_signatures=False,
            cut_quoting=False,
            individual_files=False,
            threaded=False,
            binaries_removal=False,
            redact_pii=False,
            format='markdown',
            separator='auto',
            output_mode='file',
            output_path=markdown_path,
            encoding='cp437',
            quiet=True
        )
        process_merged_files([input_path], settings_export, self.logger)

        # Verify export exists
        self.assertTrue(os.path.exists(markdown_path))

        # 3. Import from Markdown
        messages, board_dict = load_data(markdown_path, self.logger)

        # 4. Assertions
        self.assertEqual(len(messages), 1)
        msg = messages[0]

        # Check metadata
        self.assertEqual(msg.header.msgsubject.strip(), "Re: Fujitsu hard drive")
        self.assertEqual(msg.header.msgfrom.strip(), "Warren Zatwarniski")
        self.assertEqual(msg.header.msgto.strip(), "Wes Kitchen")
        self.assertEqual(msg.confnum, 4)
        self.assertEqual(msg.confname, "Pnw.Tech")
        self.assertEqual(msg.bbs_name, "Benden Weyr, Pern, Sagittarius Sector")
        self.assertEqual(msg.header.msgnum, 158)
        self.assertEqual(msg.header.msgdate, "09-03-94")
        self.assertEqual(msg.header.msgtime, "23:45")

        # Check body content (basic check)
        self.assertIn("Hi Wes. Seen your message", msg.text)
        self.assertIn("M2261SA", msg.text)

    def test_markdown_multi_message_round_trip(self):
        input_path = "testdata/test2_qwk.zip"
        if not os.path.exists(input_path):
            self.skipTest("testdata/test2_qwk.zip not found")

        markdown_path = os.path.join(self.test_dir, "test_multi.md")

        # Export
        settings_export = ProcessingSettings(
            verbose=True,
            private=True,
            no_header=False,
            truncate_signatures=False,
            cut_quoting=False,
            individual_files=False,
            threaded=False,
            binaries_removal=False,
            redact_pii=False,
            format='markdown',
            separator='auto',
            output_mode='file',
            output_path=markdown_path,
            encoding='cp437',
            quiet=True
        )
        process_merged_files([input_path], settings_export, self.logger)

        # Import
        messages, board_dict = load_data(markdown_path, self.logger)

        # Assertions
        self.assertEqual(len(messages), 2)

        # First message
        msg1 = messages[0]
        self.assertEqual(msg1.header.msgsubject.strip(), "I NEED A DOOM FIX......")
        self.assertEqual(msg1.header.msgnum, 199)
        self.assertIn("Try the Alternative BBS", msg1.text)

        # Second message
        msg2 = messages[1]
        self.assertEqual(msg2.header.msgsubject.strip(), "GUS Problem")
        self.assertEqual(msg2.header.msgnum, 200)
        self.assertIn("Are you sure that you have stereo wires", msg2.text)

    def test_markdown_import_with_attachments(self):
        markdown_content = """
# Archive

## Message with Attachments
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Conference:** General (1)
- **Attachments:** [image.jpg](attachments/image.jpg), [data.zip](attachments/data.zip)

Hello with files.
"""
        markdown_path = os.path.join(self.test_dir, "test_attach.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        messages, _ = load_data(markdown_path, self.logger)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].attachments, ["image.jpg", "data.zip"])

    def test_markdown_import_plain_attachments(self):
        markdown_content = """
# Archive

## Message with Attachments
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Conference:** General (1)
- **Attachments:** file1.txt, file2.txt

Hello with plain attachments.
"""
        markdown_path = os.path.join(self.test_dir, "test_attach_plain.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        messages, _ = load_data(markdown_path, self.logger)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].attachments, ["file1.txt", "file2.txt"])

    def test_markdown_import_threaded(self):
        markdown_content = """
# Archive

## Root Message
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Conference:** General (1)

Root content.

---

> ## Reply Message
> - **Date:** 01-01-24 12:10
> - **From:** Bob
> - **To:** Alice
> - **Conference:** General (1)
>
> Reply content.
"""
        markdown_path = os.path.join(self.test_dir, "test_threaded.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        messages, _ = load_data(markdown_path, self.logger)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].depth, 0)
        self.assertEqual(messages[1].depth, 1)
        self.assertEqual(messages[1].header.msgfrom, "Bob")
        self.assertEqual(messages[1].text, "Reply content.")

    def test_markdown_import_threaded_no_space(self):
        markdown_content = """
# Archive

## Root Message
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Conference:** General (1)

Root content.

---

>## Reply Message
>- **Date:** 01-01-24 12:10
>- **From:** Bob
>- **To:** Alice
>- **Conference:** General (1)
>
>Reply content.
"""
        markdown_path = os.path.join(self.test_dir, "test_threaded_no_space.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        messages, _ = load_data(markdown_path, self.logger)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].depth, 0)
        self.assertEqual(messages[1].depth, 1)
        self.assertEqual(messages[1].header.msgfrom, "Bob")
        self.assertEqual(messages[1].text, "Reply content.")

    def test_markdown_import_with_internal_separators(self):
        markdown_content = """
# Archive

## Message with HR
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Conference:** General (1)

This is the first part.

---

This is the second part (after a horizontal rule).
"""
        markdown_path = os.path.join(self.test_dir, "test_hr.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        messages, _ = load_data(markdown_path, self.logger)
        self.assertEqual(len(messages), 1)
        self.assertIn("first part", messages[0].text)
        self.assertIn("---", messages[0].text)
        self.assertIn("second part", messages[0].text)

    def test_markdown_import_preserves_body_headers(self):
        """Verify that Markdown headers in the body are not stripped during import."""
        markdown_content = """
# Archive

## Metadata Subject
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Conference:** General (1)

## Body Header
Body text here.

- **Bullet in body**
More text.
"""
        markdown_path = os.path.join(self.test_dir, "test_body_headers.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        messages, _ = load_data(markdown_path, self.logger)
        self.assertEqual(len(messages), 1)
        self.assertIn("## Body Header", messages[0].text)
        self.assertIn("- **Bullet in body**", messages[0].text)

if __name__ == '__main__':
    unittest.main()
