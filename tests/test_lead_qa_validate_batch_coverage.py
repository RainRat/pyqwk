import os
import zipfile
import tarfile
import tempfile
import logging
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import (
    validate_archive,
    _pack_directory_to_archive,
    matches_filters,
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
)

@pytest.fixture
def logger():
    return logging.getLogger("test_lead_qa_validate_batch")


def test_validate_archive_batch_zip_valid_and_invalid(tmp_path, logger):
    zip_path = tmp_path / "batch_validate.zip"

    with zipfile.ZipFile(zip_path, "w") as zf:
        # Create a valid JSON inside ZIP
        zf.writestr(
            "subfolder/valid.json",
            '[{"header": {"msgfrom": "Bob", "msgto": "Alice", "msgsubject": "Hi", "msgnum": 1, "confnum": 1}, "text": "Hello"}]'
        )
        # Create an invalid JSON (malformed) inside ZIP
        zf.writestr("subfolder/invalid.json", "{invalid json")

    res = validate_archive(str(zip_path), logger)
    assert res["valid"] is False
    assert res["format"] == "compressed_archive"
    assert res["messages_count"] == 1
    assert any("invalid.json" in err for err in res["errors"])


def test_validate_archive_batch_tar_valid_and_invalid(tmp_path, logger):
    tar_path = tmp_path / "batch_validate.tar"

    with tarfile.open(tar_path, "w") as tf:
        # Create a valid text file inside TAR
        valid_file = tmp_path / "valid.txt"
        valid_file.write_text("From: Bob\nTo: Alice\nSubject: Hi\nDate: 10-12-23\n\nBody text")
        tf.add(valid_file, arcname="valid.txt")

        # Create a JSON missing header inside TAR to generate warning
        warning_file = tmp_path / "warn.json"
        warning_file.write_text('[{"text": "Hello without header"}]')
        tf.add(warning_file, arcname="warn.json")

    res = validate_archive(str(tar_path), logger)
    assert res["valid"] is True
    assert res["format"] == "compressed_archive"
    assert res["messages_count"] == 2
    assert any("warn.json" in warn for warn in res["warnings"])


def test_validate_archive_batch_zip_exception_handling(tmp_path, logger):
    zip_path = tmp_path / "corrupt_batch.zip"
    zip_path.write_text("rubbish zip content that will fail parsing")

    # Mock is_zipfile to return True so it enters the zipfile block,
    # but ZipFile constructor raises an exception
    with patch("zipfile.is_zipfile", return_value=True):
        res = validate_archive(str(zip_path), logger)
        assert res["valid"] is False
        assert any("ZIP archive read error" in err for err in res["errors"])


def test_validate_archive_batch_tar_exception_handling(tmp_path, logger):
    tar_path = tmp_path / "corrupt_batch.tar"
    tar_path.write_text("rubbish tar content that will fail parsing")

    with patch("tarfile.is_tarfile", return_value=True):
        res = validate_archive(str(tar_path), logger)
        assert res["valid"] is False
        assert any("TAR archive read error" in err for err in res["errors"])


def test_pack_directory_to_archive_tar_bz2(tmp_path, logger):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "test.txt").write_text("Hello Tar BZ2")

    archive_path = tmp_path / "test.tar.bz2"
    _pack_directory_to_archive(str(src_dir), str(archive_path), logger)

    assert archive_path.exists()
    assert tarfile.is_tarfile(archive_path)


def test_matches_filters_attachment_pattern_substring_fallback():
    h = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Hello",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=h,
        attachments=["file[1].txt"]
    )

    # We use file[1].txt which has glob brackets.
    # fnmatch.fnmatch("file[1].txt", "file[1].txt") is False because character class matches '1', not '[1]'.
    # Hence it triggers the substring fallback in matches_filters.
    settings = ProcessingSettings(
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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8",
        attachment_pattern="file[1].txt"
    )

    assert matches_filters(msg, settings, set()) is True
