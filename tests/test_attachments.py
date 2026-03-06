import os
import shutil
import tempfile
import pytest
from pyqwk.core import extract_binaries, ProcessingSettings, process_merged_files, ParsedMessage, MessageHeader
from unittest.mock import MagicMock
import dataclasses

def _make_settings(**kwargs):
    defaults = dict(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437',
        conferences=None, authors=None, recipients=None, subjects=None,
        search_term=None, after=None, before=None,
        regex=False, dry_run=False, strip_ansi=False,
        quiet=False, headers_only=False, oneline=False,
        extract_attachments=False, limit=None, skip=None,
        sort=None, reverse=False, merge=False, unique=False, organize=False,
        organize_by_bbs=False, include_toc=False
    )
    defaults.update(kwargs)
    field_names = {f.name for f in dataclasses.fields(ProcessingSettings)}
    filtered_defaults = {k: v for k, v in defaults.items() if k in field_names}
    return ProcessingSettings(**filtered_defaults)

def test_extract_uue():
    text = """
Hello, here is a file:
begin 644 test.txt
#0V%T
`
end
Nice, isn't it?
"""
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][0] == "test.txt"
    assert binaries[0][1] == b"Cat"

def test_extract_base64():
    text = """
Some B64 data follows:
RGF0YQ==
"""
    # Note: RE_BASE64_PATTERN requires 60+ chars for initial detection to avoid false positives.
    # So I need a longer string for the test.
    long_b64 = "R" * 64 + "\n" + "RGF0YQ=="
    binaries = extract_binaries(long_b64)
    assert len(binaries) == 1
    # Base64 decoder in my implementation uses "attachment.bin" as default
    assert binaries[0][0] == "attachment.bin"
    # It will contain the first line of Rs too
    assert binaries[0][1].endswith(b"Data")

def test_extract_yenc():
    text = """
=ybegin line=128 size=4 name=test.txt
=yend size=4 crc32=00000000
"""
    # My yEnc decoder is very basic and expects data between begin and end.
    # The example above has no data lines, but let's try with one.
    text_with_data = """
=ybegin line=128 size=4 name=test.txt
*+,/
=yend size=4 crc32=00000000
"""
    # yEnc: char - 42. '*' is 42, so 42-42=0. '+' is 43, so 43-42=1.
    binaries = extract_binaries(text_with_data)
    assert len(binaries) == 1
    assert binaries[0][0] == "test.txt"
    assert binaries[0][1][0] == 0
    assert binaries[0][1][1] == 1

def test_yenc_escaping_comprehensive():
    # Test normal escaping, multiple escapes, and escape at the end
    # yEnc: char = (orig + 42) % 256. If char in {0, 10, 13, 61}, then it's escaped with '=' and char = (char + 64) % 256.
    # To get orig 19: (19 + 42) = 61 ('='). Critical!
    # So orig 19 is encoded as '=' followed by (61 + 64) = 125 ('}').
    text = """
=ybegin name=test.txt
=}
=yend
"""
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][1] == b"\x13" # 19 in hex

def test_base64_terminated_by_non_base64_line():
    # To hit line 207-208, we need a line that terminates the base64 block
    long_line = "A" * 64
    text = f"{long_line}\nNOT_B64\n"
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][0] == "attachment.bin"

def test_base64_invalid_padding_exception():
    # Base64 with invalid length/padding to trigger exception (line 209-210)
    invalid_b64 = "A" * 61 # Matches RE_BASE64_PATTERN but invalid length
    text = f"{invalid_b64}\n!!!"
    binaries = extract_binaries(text)
    assert len(binaries) == 0

def test_base64_unterminated_at_end():
    # Base64 block that is never terminated (line 240-245)
    long_line = "A" * 64
    text = f"{long_line}\n{long_line}"
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][0] == "attachment.bin"

def test_uue_empty_line_skip():
    # Coverage for line 192: continue if not l
    text = """
begin 644 test.txt
#0V%T

`
end
"""
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][1] == b"Cat"

def test_process_merged_files_with_attachments():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.txt")

        # Create a mock message with UUE
        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
            msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
            refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
        )
        msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
        message = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header)

        settings = _make_settings(
            private=True,
            output_mode='file',
            output_path=output_path,
            extract_attachments=True
        )

        # We need to mock load_data and parse_messages
        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        original_parse_messages = pyqwk.core.parse_messages

        pyqwk.core.load_data = MagicMock(return_value=(bytearray(), {1: "General"}))
        pyqwk.core.parse_messages = MagicMock(return_value=[message])

        try:
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())

            attach_dir = os.path.join(tmpdir, "attachments")
            assert os.path.exists(attach_dir)
            assert os.path.exists(os.path.join(attach_dir, "file.txt"))
            with open(os.path.join(attach_dir, "file.txt"), 'rb') as f:
                assert f.read() == b"Cat"
        finally:
            pyqwk.core.load_data = original_load_data
            pyqwk.core.parse_messages = original_parse_messages


def test_uue_unterminated_at_end():
    text = "begin 644 test.txt\n#0V%T"
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][0] == "test.txt"
    assert binaries[0][1] == b"Cat"


def test_yenc_unterminated_at_end():
    text = "=ybegin name=test.txt\n*+,/"
    binaries = extract_binaries(text)
    assert len(binaries) == 1
    assert binaries[0][0] == "test.txt"
    # yEnc decode: (val - 42) % 256
    # '*'=42 -> 0, '+'=43 -> 1, ','=44 -> 2, '/'=47 -> 5
    assert binaries[0][1] == b"\x00\x01\x02\x05"


def test_uue_invalid_data():
    # Trigger (binascii.Error, ValueError) in _decode_uue
    text_invalid = "begin 644 test.txt\n\x00\x00\x00\nend"
    binaries = extract_binaries(text_invalid)
    assert len(binaries) == 0


def test_base64_unterminated_invalid():
    # Trigger (binascii.Error, ValueError) in _decode_base64 at end of text
    long_line = "A" * 64
    invalid_data = "A" * 61  # 125 chars total, invalid length
    text = f"{long_line}\n{invalid_data}"
    binaries = extract_binaries(text)
    assert len(binaries) == 0

def test_collision_avoidance():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.txt")
        attach_dir = os.path.join(tmpdir, "attachments")
        os.makedirs(attach_dir)

        # Create an existing file
        with open(os.path.join(attach_dir, "file.txt"), 'w') as f:
            f.write("existing")

        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
            msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
            refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
        )
        msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
        message = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header)

        settings = _make_settings(
            output_mode='file',
            output_path=output_path,
            extract_attachments=True
        )

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        original_parse_messages = pyqwk.core.parse_messages
        pyqwk.core.load_data = MagicMock(return_value=(bytearray(), {1: "General"}))
        pyqwk.core.parse_messages = MagicMock(return_value=[message])

        try:
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
            # Should have created file_1.txt
            assert os.path.exists(os.path.join(attach_dir, "file_1.txt"))
        finally:
            pyqwk.core.load_data = original_load_data
            pyqwk.core.parse_messages = original_parse_messages

def test_yenc_empty_filename_fallback():
    # Test fallback to attachment.bin when filename is empty (line 1150)
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.txt")
        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
            msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
            refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
        )
        # yEnc with name that becomes empty after basename
        msg_text = "=ybegin name=/\n*+,/\n=yend\n"
        message = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header)

        settings = _make_settings(
            output_mode='file',
            output_path=output_path,
            extract_attachments=True
        )

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        original_parse_messages = pyqwk.core.parse_messages
        pyqwk.core.load_data = MagicMock(return_value=(bytearray(), {1: "General"}))
        pyqwk.core.parse_messages = MagicMock(return_value=[message])

        try:
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
            attach_dir = os.path.join(tmpdir, "attachments")
            assert os.path.exists(os.path.join(attach_dir, "attachment.bin"))
        finally:
            pyqwk.core.load_data = original_load_data
            pyqwk.core.parse_messages = original_parse_messages

def test_attachment_base_directory_logic(monkeypatch):
    # Coverage for lines 1126, 1129, 1133
    with tempfile.TemporaryDirectory() as tmpdir:
        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
            msgto='All', msgfrom='Author', msgsubject='Test', msgpassword='',
            refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
        )
        msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
        message = ParsedMessage(text=msg_text, msgnum=1, refnum=None, confnum=1, header=header)

        import pyqwk.core
        original_load_data = pyqwk.core.load_data
        original_parse_messages = pyqwk.core.parse_messages
        pyqwk.core.load_data = MagicMock(return_value=(bytearray(), {1: "General"}))
        pyqwk.core.parse_messages = MagicMock(return_value=[message])

        try:
            # Case 1: output_path is a directory and individual_files=True (line 1126)
            settings = _make_settings(
                individual_files=True,
                output_mode='file',
                output_path=tmpdir,
                extract_attachments=True
            )
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
            assert os.path.exists(os.path.join(tmpdir, "attachments", "file.txt"))

            # Case 2: output_path is a file (line 1129)
            shutil.rmtree(os.path.join(tmpdir, "attachments"), ignore_errors=True)
            file_path = os.path.join(tmpdir, "somefile.txt")
            settings = _make_settings(
                output_mode='file',
                output_path=file_path,
                extract_attachments=True
            )
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
            assert os.path.exists(os.path.join(tmpdir, "attachments", "file.txt"))

            # Case 3: no output_path (line 1133)
            shutil.rmtree(os.path.join(tmpdir, "attachments"), ignore_errors=True)
            monkeypatch.chdir(tmpdir)
            settings = _make_settings(
                output_mode='stdout',
                output_path=None,
                extract_attachments=True
            )
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
            assert os.path.exists(os.path.join(tmpdir, "attachments", "file.txt"))

            # Case 4: output_path is a directory and individual_files=False (line 1129)
            shutil.rmtree(os.path.join(tmpdir, "attachments"), ignore_errors=True)
            original_write_text = pyqwk.core._write_text
            pyqwk.core._write_text = MagicMock()
            try:
                settings = _make_settings(
                    individual_files=False,
                    output_mode='file',
                    output_path=tmpdir,
                    extract_attachments=True
                )
                pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
                assert os.path.exists(os.path.join(tmpdir, "attachments", "file.txt"))
            finally:
                pyqwk.core._write_text = original_write_text

            # Case 5: dry_run (line 1155)
            shutil.rmtree(os.path.join(tmpdir, "attachments"), ignore_errors=True)
            settings = _make_settings(
                output_mode='stdout',
                output_path=None,
                extract_attachments=True,
                dry_run=True
            )
            pyqwk.core.process_merged_files(["mock.qwk"], settings, MagicMock())
            assert not os.path.exists(os.path.join(tmpdir, "attachments"))
        finally:
            pyqwk.core.load_data = original_load_data
            pyqwk.core.parse_messages = original_parse_messages
