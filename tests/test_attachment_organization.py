import os
import logging
from pathlib import Path
import pytest

from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        regex=False,
        dry_run=False,
        strip_ansi=False,
        quiet=True,
        headers_only=False,
        merge=False,
        unique=False,
        organize=False,
        organize_by_date=False,
        organize_by_bbs=False,
        organize_by_author=False,
        organize_by_to=False,
        organize_by_subject=False,
        include_toc=False,
        extract_attachments=True,
        organize_attachments=True,
        msgnum_filters=None,
        search_term=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

@pytest.fixture
def logger():
    return logging.getLogger("test")

def test_attachment_organization_by_conference(tmp_path, logger, monkeypatch):
    # Setup dummy message with UUE attachment
    # # is length 3. "Cat" is 3 bytes.
    uue_content = "begin 644 attachment.txt\n#0V%T\n`\nend\n"
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="AuthorName",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=10,
        lognum=0,
        nettag=" ",
    )
    msg = ParsedMessage(
        text=uue_content,
        msgnum=123,
        refnum=None,
        confnum=10,
        header=header,
        confname="General",
        bbs_name="MyBBS",
    )

    # Mock load_data to return our dummy message
    def mock_load_data(path, logger, encoding):
        return [msg], {10: "General"}

    import pyqwk.core as core
    monkeypatch.setattr(core, "load_data", mock_load_data)

    output_dir = tmp_path / "output"
    settings = _make_settings(
        individual_files=True,
        output_mode="file",
        output_path=str(output_dir),
        organize=True  # Organize by conference
    )

    process_merged_files(["dummy.qwk"], settings, logger)

    # Verify attachment path
    # Expected: output/attachments/010-general/attachment.txt
    expected_attach_path = output_dir / "attachments" / "010-general" / "attachment.txt"

    if not expected_attach_path.exists():
        print(f"DEBUG: Files in output: {list(output_dir.rglob('*'))}")

    assert expected_attach_path.exists()
    assert expected_attach_path.read_bytes() == b"Cat"

def test_attachment_organization_by_author(tmp_path, logger, monkeypatch):
    uue_content = "begin 644 doc.pdf\n#0V%T\n`\nend\n"
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Recipient", msgfrom="Jane Doe", msgsubject="Sub",
        msgpassword="", refnum=None, numblocks=2, msgflag=" ",
        confnum=1, lognum=0, nettag=" ",
    )
    msg = ParsedMessage(
        text=uue_content, msgnum=1, refnum=None, confnum=1, header=header,
        confname="Conf", bbs_name="BBS"
    )

    monkeypatch.setattr("pyqwk.core.load_data", lambda p, l, e: ([msg], {1: "Conf"}))

    output_dir = tmp_path / "output"
    settings = _make_settings(
        individual_files=True,
        output_mode="file",
        output_path=str(output_dir),
        organize_by_author=True
    )

    process_merged_files(["dummy.qwk"], settings, logger)

    # Expected: output/attachments/jane_doe/doc.pdf
    expected_attach_path = output_dir / "attachments" / "jane_doe" / "doc.pdf"
    assert expected_attach_path.exists()

def test_attachment_html_links_with_organization(tmp_path, logger, monkeypatch):
    uue_content = "begin 644 file.zip\n#0V%T\n`\nend\n"
    header = MessageHeader(
        status=" ", msgnum=50, msgdate="10-10-23", msgtime="10:00",
        msgto="Everyone", msgfrom="Sysop", msgsubject="Files",
        msgpassword="", refnum=None, numblocks=2, msgflag=" ",
        confnum=5, lognum=0, nettag=" ",
    )
    msg = ParsedMessage(
        text=uue_content, msgnum=50, refnum=None, confnum=5, header=header,
        confname="FilesArea", bbs_name="The BBS"
    )

    monkeypatch.setattr("pyqwk.core.load_data", lambda p, l, e: ([msg], {5: "FilesArea"}))

    output_dir = tmp_path / "output"
    settings = _make_settings(
        individual_files=True,
        output_mode="file",
        output_path=str(output_dir),
        format="html",
        organize=True # by conference
    )

    process_merged_files(["dummy.qwk"], settings, logger)

    # Message path: output/005-filesarea/005-00050-files.html
    # Attachment path: output/attachments/005-filesarea/file.zip
    # Link in HTML should be: ../attachments/005-filesarea/file.zip

    msg_file = output_dir / "005-filesarea" / "005-00050-files.html"
    assert msg_file.exists()

    content = msg_file.read_text()
    assert 'href="../attachments/005-filesarea/file.zip"' in content
