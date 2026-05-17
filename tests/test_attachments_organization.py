import os
import tempfile
import logging
from pyqwk.core import ProcessingSettings, ParsedMessage, MessageHeader, process_merged_files

# Valid UUE attachment
UUE_BODY = """
begin 644 test.txt
M5&AI<R!I<R!A('1E<W0@96QS92!F:6QU<B!F<F]M(&ES<W5E+B!W:71H(&9I
M;&5N86UE(&%N9"!D871A+g==
`
end
"""

def test_attachment_organization_by_conference():
    """Test that attachments are organized by conference when --organize-attachments is used."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        header = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-24", msgtime="10:00",
            msgto="Bob", msgfrom="Alice", msgsubject="Hello", msgpassword="",
            refnum=None, numblocks=1, msgflag=" ", confnum=10, lognum=0, nettag=""
        )
        msg = ParsedMessage(
            text=UUE_BODY, msgnum=1, refnum=None, confnum=10, header=header,
            confname="General", bbs_name="TestBBS"
        )

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        pyqwk.core.load_data = lambda path, logger, encoding: ([msg], {10: "General"})

        try:
            settings = ProcessingSettings(
                verbose=False, private=True, no_header=False,
                truncate_signatures=False, cut_quoting=False,
                individual_files=True, threaded=False,
                binaries_removal=False, redact_pii=False,
                format="text", separator="none", output_mode="file",
                output_path=tmp_dir, encoding="utf-8",
                extract_attachments=True,
                organize=True,
                organize_attachments=True
            )

            logger = logging.getLogger("test")
            process_merged_files(["dummy.qwk"], settings, logger)

            # Check for message file
            expected_msg_dir = os.path.join(tmp_dir, "010-general")
            assert os.path.exists(expected_msg_dir)

            # Check for organized attachment
            expected_attach_dir = os.path.join(tmp_dir, "attachments", "010-general")
            assert os.path.exists(expected_attach_dir)
            assert os.path.exists(os.path.join(expected_attach_dir, "test.txt"))

        finally:
            pyqwk.core.load_data = original_load_data

def test_attachment_organization_by_date():
    """Test that attachments are organized by date when --organize-attachments is used."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        header = MessageHeader(
            status=" ", msgnum=1, msgdate="05-15-24", msgtime="10:00",
            msgto="Bob", msgfrom="Alice", msgsubject="Hello", msgpassword="",
            refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
        )
        msg = ParsedMessage(
            text=UUE_BODY.replace("test.txt", "date.bin"), msgnum=1, refnum=None, confnum=1, header=header,
            confname="General"
        )

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        pyqwk.core.load_data = lambda path, logger, encoding: ([msg], {1: "General"})

        try:
            settings = ProcessingSettings(
                verbose=False, private=True, no_header=False,
                truncate_signatures=False, cut_quoting=False,
                individual_files=True, threaded=False,
                binaries_removal=False, redact_pii=False,
                format="text", separator="none", output_mode="file",
                output_path=tmp_dir, encoding="utf-8",
                extract_attachments=True,
                organize_by_date=True,
                organize_attachments=True
            )

            logger = logging.getLogger("test")
            process_merged_files(["dummy.qwk"], settings, logger)

            # Check for organized attachment in YYYY/MM structure
            expected_attach_dir = os.path.join(tmp_dir, "attachments", "2024", "05")
            assert os.path.exists(expected_attach_dir)
            assert os.path.exists(os.path.join(expected_attach_dir, "date.bin"))

        finally:
            pyqwk.core.load_data = original_load_data

def test_attachment_prefix_in_html():
    """Test that HTML attachment links reflect organized paths."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        header = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-24", msgtime="10:00",
            msgto="Bob", msgfrom="Alice", msgsubject="Hello", msgpassword="",
            refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
        )
        msg = ParsedMessage(
            text=UUE_BODY.replace("test.txt", "image.jpg"), msgnum=1, refnum=None, confnum=1, header=header,
            confname="General"
        )

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        pyqwk.core.load_data = lambda path, logger, encoding: ([msg], {1: "General"})

        try:
            settings = ProcessingSettings(
                verbose=False, private=True, no_header=False,
                truncate_signatures=False, cut_quoting=False,
                individual_files=True, threaded=False,
                binaries_removal=False, redact_pii=False,
                format="html", separator="none", output_mode="file",
                output_path=tmp_dir, encoding="utf-8",
                extract_attachments=True,
                organize=True,
                organize_attachments=True
            )

            logger = logging.getLogger("test")
            process_merged_files(["dummy.qwk"], settings, logger)

            # Find the HTML file
            msg_dir = os.path.join(tmp_dir, "001-general")
            html_files = [f for f in os.listdir(msg_dir) if f.endswith(".html")]
            assert len(html_files) == 1

            with open(os.path.join(msg_dir, html_files[0]), "r") as f:
                content = f.read()
                # Relative path from 001-general/msg.html to attachments/001-general/image.jpg
                # should be ../attachments/001-general/image.jpg
                assert 'href="../attachments/001-general/image.jpg"' in content

        finally:
            pyqwk.core.load_data = original_load_data

def test_default_attachment_behavior():
    """Test that attachments are NOT organized by default."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        header = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-24", msgtime="10:00",
            msgto="Bob", msgfrom="Alice", msgsubject="Hello", msgpassword="",
            refnum=None, numblocks=1, msgflag=" ", confnum=10, lognum=0, nettag=""
        )
        msg = ParsedMessage(
            text=UUE_BODY.replace("test.txt", "default.txt"), msgnum=1, refnum=None, confnum=10, header=header,
            confname="General"
        )

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        pyqwk.core.load_data = lambda path, logger, encoding: ([msg], {10: "General"})

        try:
            settings = ProcessingSettings(
                verbose=False, private=True, no_header=False,
                truncate_signatures=False, cut_quoting=False,
                individual_files=True, threaded=False,
                binaries_removal=False, redact_pii=False,
                format="text", separator="none", output_mode="file",
                output_path=tmp_dir, encoding="utf-8",
                extract_attachments=True,
                organize=True,
                organize_attachments=False # Default
            )

            logger = logging.getLogger("test")
            process_merged_files(["dummy.qwk"], settings, logger)

            # Attachments should be in root attachments/ folder
            expected_attach_dir = os.path.join(tmp_dir, "attachments")
            assert os.path.exists(expected_attach_dir)
            assert os.path.exists(os.path.join(expected_attach_dir, "default.txt"))
            # And NOT in conference subfolder
            assert not os.path.exists(os.path.join(expected_attach_dir, "010-general"))

        finally:
            pyqwk.core.load_data = original_load_data
