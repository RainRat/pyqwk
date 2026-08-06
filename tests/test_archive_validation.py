import os
import json
import csv
import sqlite3
import xml.etree.ElementTree as ET
import pytest
import logging
import zipfile
import tarfile
import io
from unittest.mock import MagicMock
from pyqwk.core import validate_archive, MessageHeader, ParsedMessage, BLOCK_SIZE


@pytest.fixture
def logger():
    return logging.getLogger("test_validation")


def make_qwk_messages_content(msgnum=1, msgfrom="Bob", msgto="Alice", msgsubject="Hello", numblocks=2, msgnum_val=None):
    first_block = b"Produced by pyqwk".ljust(128, b" ")
    actual_msgnum = msgnum if msgnum_val is None else msgnum_val
    hdr = MessageHeader(
        status=" ",
        msgnum=actual_msgnum,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=None,
        numblocks=numblocks,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )
    hdr_bytes = hdr.to_bytes()
    body_bytes = b"Hello world".ljust(128 * (numblocks - 1), b" ")
    return first_block + hdr_bytes + body_bytes


def test_validate_archive_nonexistent(logger):
    res = validate_archive("nonexistent_file_path.qwk", logger)
    assert res["valid"] is False
    assert any("File not found" in err for err in res["errors"])


def test_validate_archive_empty(tmp_path, logger):
    p = tmp_path / "empty.json"
    p.write_text("")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("File is empty" in err for err in res["errors"])


def test_validate_archive_qwk_good(tmp_path, logger):
    p = tmp_path / "messages.dat"
    # Create a valid QWK messages file:
    # First block: "Produced by pyqwk"
    first_block = b"Produced by pyqwk".ljust(128, b" ")
    # Second block: A valid message header (128 bytes)
    hdr = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Hello",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )
    hdr_bytes = hdr.to_bytes()
    # Third block: Body text (128 bytes)
    body_bytes = b"Hello Alice\xe3".ljust(128, b" ")

    content = first_block + hdr_bytes + body_bytes
    p.write_bytes(content)

    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] in ("qwk", "rep")
    assert res["messages_count"] == 1
    assert len(res["errors"]) == 0


def test_validate_archive_qwk_misaligned(tmp_path, logger):
    p = tmp_path / "messages.dat"
    content = b"Some random garbage dat"
    p.write_bytes(content)

    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("Block misalignment detected" in err or "too small" in err for err in res["errors"])


def test_validate_archive_json_good(tmp_path, logger):
    p = tmp_path / "archive.json"
    msg_data = {
        "type": "qwk_archive",
        "messages": [
            {
                "header": {
                    "msgfrom": "Bob",
                    "msgto": "Alice",
                    "msgsubject": "Hi",
                    "msgnum": 1,
                    "confnum": 1,
                    "status": " ",
                    "msgflag": " "
                },
                "text": "Hello World"
            }
        ]
    }
    p.write_text(json.dumps(msg_data))

    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "json"
    assert res["messages_count"] == 1


def test_validate_archive_json_malformed(tmp_path, logger):
    p = tmp_path / "archive.json"
    p.write_text("{invalid json")

    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("JSON syntax error" in err for err in res["errors"])


def test_validate_archive_json_missing_fields(tmp_path, logger):
    p = tmp_path / "archive.json"
    msg_data = {
        "type": "qwk_archive",
        "messages": [
            {
                "header": {
                    "msgnum": 1
                    # missing sender, to, subject
                },
                "text": "Hello"
            }
        ]
    }
    p.write_text(json.dumps(msg_data))

    res = validate_archive(str(p), logger)
    assert res["format"] == "json"
    assert len(res["warnings"]) > 0
    assert any("missing sender" in w or "missing recipient" in w or "missing subject" in w for w in res["warnings"])


def test_validate_archive_jsonl(tmp_path, logger):
    p = tmp_path / "archive.jsonl"
    p.write_text('{"type": "metadata", "conferences": {}}\n{"header": {"msgfrom": "Bob", "msgto": "Alice", "msgsubject": "Test", "msgnum": 1}, "text": "Hi"}')
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "jsonl"
    assert res["messages_count"] == 1


def test_validate_archive_csv_good(tmp_path, logger):
    p = tmp_path / "archive.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["msgfrom", "msgto", "msgsubject", "text", "msgnum"])
        writer.writerow(["Bob", "Alice", "Subject", "Hello!", "1"])

    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "csv"
    assert res["messages_count"] == 1


def test_validate_archive_csv_missing_headers(tmp_path, logger):
    p = tmp_path / "archive.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["some_random_column"])
        writer.writerow(["val"])

    res = validate_archive(str(p), logger)
    assert res["format"] == "csv"
    assert any("missing recommended standard headers" in w for w in res["warnings"])


def test_validate_archive_xml(tmp_path, logger):
    p = tmp_path / "archive.xml"
    p.write_text("<messages><message><header><msgfrom>Bob</msgfrom><msgto>Alice</msgto><msgsubject>S</msgsubject><msgnum>1</msgnum></header><text>T</text></message></messages>")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "xml"
    assert res["messages_count"] == 1


def test_validate_archive_rss(tmp_path, logger):
    p = tmp_path / "archive.rss"
    p.write_text('<rss><channel><title>Test Feed</title><item><title>Test Subject</title><author>Bob</author><description>Hello</description></item></channel></rss>')
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "xml"
    assert res["messages_count"] == 1


def test_validate_archive_sqlite(tmp_path, logger):
    p = tmp_path / "archive.db"
    conn = sqlite3.connect(p)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE messages (
            conference_number INTEGER,
            message_number INTEGER,
            date TEXT,
            author TEXT,
            recipient TEXT,
            subject TEXT,
            status TEXT,
            text TEXT,
            reference_number INTEGER,
            thread_id TEXT,
            depth INTEGER,
            parent_message_number INTEGER,
            conference_name TEXT,
            bbs_name TEXT,
            bbs_id TEXT,
            source_file TEXT,
            attachments TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO messages (conference_number, author, recipient, subject, text)
        VALUES (1, 'Bob', 'Alice', 'Subj', 'Body')
    """)
    conn.commit()
    conn.close()

    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "sqlite"
    assert res["messages_count"] == 1


def test_validate_archive_maildir_and_text(tmp_path, logger):
    # Plain text format validation
    p = tmp_path / "archive.txt"
    p.write_text("From: Bob\nTo: Alice\nSubject: Hi\nDate: 10-12-23\n\nBody text")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "text"
    assert res["messages_count"] == 1


# --- NEW COMPREHENSIVE PATH COVERAGE TESTS ---

def test_validate_archive_directory_not_maildir(tmp_path, logger):
    d = tmp_path / "not_maildir_dir"
    d.mkdir()
    res = validate_archive(str(d), logger)
    assert res["valid"] is False
    assert any("Path is a directory but not a valid Maildir" in err for err in res["errors"])


def test_validate_archive_directory_valid_maildir(tmp_path, logger):
    d = tmp_path / "valid_maildir"
    d.mkdir()
    (d / "cur").mkdir()
    (d / "new").mkdir()
    (d / "tmp").mkdir()
    res = validate_archive(str(d), logger)
    assert res["valid"] is True
    assert res["format"] == "maildir"


def test_validate_archive_zip_crc_failure(tmp_path, logger, monkeypatch):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("dummy.txt", "dummy content")
    monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda self: "dummy.txt")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("ZIP file CRC check failed for: dummy.txt" in err for err in res["errors"])


def test_validate_archive_zip_standard_qwk(tmp_path, logger):
    p = tmp_path / "test.zip"
    content = make_qwk_messages_content()
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("messages.dat", content)
        zf.writestr("control.dat", "control block content")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "compressed_archive"
    assert res["messages_count"] == 1


def test_validate_archive_zip_misaligned_internal(tmp_path, logger):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("messages.dat", "not 128 bytes multiple")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("not a multiple of 128 bytes" in err for err in res["errors"])


def test_validate_archive_zip_missing_control(tmp_path, logger):
    p = tmp_path / "test.zip"
    content = make_qwk_messages_content()
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("messages.dat", content)
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert any("CONTROL.DAT is missing from the QWK archive" in w for w in res["warnings"])


def test_validate_archive_zip_parse_failure(tmp_path, logger, monkeypatch):
    import pyqwk.core
    p = tmp_path / "test.zip"
    content = make_qwk_messages_content()
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("messages.dat", content)

    def mock_parse_messages(*args, **kwargs):
        raise ValueError("Malformed QWK message block")

    monkeypatch.setattr(pyqwk.core, "parse_messages", mock_parse_messages)
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("Failed to parse messages from" in err for err in res["errors"])


def test_validate_archive_zip_batch(tmp_path, logger):
    p = tmp_path / "batch.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("subfolder/msg.txt", "From: Bob\nTo: Alice\nSubject: Hi\nDate: 10-12-23\n\nBody text")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["messages_count"] == 1
    assert any("does not contain standard MESSAGES.DAT or REPLY.DAT" in w for w in res["warnings"])


def test_validate_archive_zip_read_error(tmp_path, logger, monkeypatch):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("dummy.txt", "dummy content")

    def mock_init(self, *args, **kwargs):
        raise OSError("Simulated read error")

    monkeypatch.setattr(zipfile.ZipFile, "__init__", mock_init)
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("ZIP archive read error: Simulated read error" in err for err in res["errors"])


def test_validate_archive_tar_standard_qwk(tmp_path, logger):
    p = tmp_path / "test.tar"
    content = make_qwk_messages_content()
    with tarfile.open(p, "w") as tf:
        tinfo = tarfile.TarInfo(name="messages.dat")
        tinfo.size = len(content)
        tf.addfile(tinfo, io.BytesIO(content))

        tinfo_ctrl = tarfile.TarInfo(name="control.dat")
        ctrl_content = b"control content"
        tinfo_ctrl.size = len(ctrl_content)
        tf.addfile(tinfo_ctrl, io.BytesIO(ctrl_content))

    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["format"] == "compressed_archive"
    assert res["messages_count"] == 1


def test_validate_archive_tar_misaligned_internal(tmp_path, logger):
    p = tmp_path / "test.tar"
    content = b"not 128 multiple"
    with tarfile.open(p, "w") as tf:
        tinfo = tarfile.TarInfo(name="messages.dat")
        tinfo.size = len(content)
        tf.addfile(tinfo, io.BytesIO(content))
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("not a multiple of 128 bytes" in err for err in res["errors"])


def test_validate_archive_tar_missing_control(tmp_path, logger):
    p = tmp_path / "test.tar"
    content = make_qwk_messages_content()
    with tarfile.open(p, "w") as tf:
        tinfo = tarfile.TarInfo(name="messages.dat")
        tinfo.size = len(content)
        tf.addfile(tinfo, io.BytesIO(content))
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert any("CONTROL.DAT is missing from the QWK archive" in w for w in res["warnings"])


def test_validate_archive_tar_parse_failure(tmp_path, logger, monkeypatch):
    import pyqwk.core
    p = tmp_path / "test.tar"
    content = make_qwk_messages_content()
    with tarfile.open(p, "w") as tf:
        tinfo = tarfile.TarInfo(name="messages.dat")
        tinfo.size = len(content)
        tf.addfile(tinfo, io.BytesIO(content))

    def mock_parse_messages(*args, **kwargs):
        raise ValueError("Malformed QWK message block")

    monkeypatch.setattr(pyqwk.core, "parse_messages", mock_parse_messages)
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("Failed to parse messages from" in err for err in res["errors"])


def test_validate_archive_tar_batch(tmp_path, logger):
    p = tmp_path / "batch.tar"
    content = b"From: Bob\nTo: Alice\nSubject: Hi\nDate: 10-12-23\n\nBody text"
    with tarfile.open(p, "w") as tf:
        tinfo = tarfile.TarInfo(name="subfolder/msg.txt")
        tinfo.size = len(content)
        tf.addfile(tinfo, io.BytesIO(content))
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["messages_count"] == 1
    assert any("does not contain standard MESSAGES.DAT or REPLY.DAT" in w for w in res["warnings"])


def test_validate_archive_tar_read_error(tmp_path, logger, monkeypatch):
    p = tmp_path / "test.tar"
    p.write_text("dummy")

    monkeypatch.setattr(tarfile, "is_tarfile", lambda path: True)

    def mock_open(*args, **kwargs):
        raise OSError("Simulated TAR read error")

    monkeypatch.setattr(tarfile, "open", mock_open)
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("TAR archive read error: Simulated TAR read error" in err for err in res["errors"])


def test_validate_archive_unsupported_compressed(tmp_path, logger):
    p = tmp_path / "corrupt.zip"
    p.write_text("not a zip file at all")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("Unsupported or corrupted compressed archive format" in err for err in res["errors"])


def test_validate_archive_json_invalid_schema(tmp_path, logger):
    p = tmp_path / "missing_msgs.json"
    p.write_text(json.dumps({"type": "qwk_archive"}))
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("JSON dictionary format lacks 'messages' field" in err for err in res["errors"])

    p2 = tmp_path / "scalar.json"
    p2.write_text(json.dumps("some string"))
    res2 = validate_archive(str(p2), logger)
    assert res2["valid"] is False
    assert any("JSON data must be a list of messages or a structured dictionary" in err for err in res2["errors"])


def test_validate_archive_json_list_of_non_objects(tmp_path, logger):
    p = tmp_path / "non_objects.json"
    p.write_text(json.dumps([123, "not a dict"]))
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("Message at index 0 is not a valid JSON object" in err for err in res["errors"])
    assert any("Message at index 1 is not a valid JSON object" in err for err in res["errors"])


def test_validate_archive_json_msg_missing_header(tmp_path, logger):
    p = tmp_path / "missing_header.json"
    p.write_text(json.dumps([{"text": "Hello"}]))
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert any("missing 'header' metadata" in w for w in res["warnings"])


def test_validate_archive_json_msg_header_invalid_type(tmp_path, logger):
    p = tmp_path / "invalid_header_type.json"
    p.write_text(json.dumps([{"header": "not a dict", "text": "Hello"}]))
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("has invalid 'header' type" in err for err in res["errors"])


def test_validate_archive_jsonl_errors(tmp_path, logger):
    p1 = tmp_path / "err1.jsonl"
    p1.write_text("123\n")
    res1 = validate_archive(str(p1), logger)
    assert res1["valid"] is False
    assert any("JSONL line 1 is not a valid object" in err for err in res1["errors"])

    p2 = tmp_path / "err2.jsonl"
    p2.write_text('{"text": "Hello"}\n')
    res2 = validate_archive(str(p2), logger)
    assert res2["valid"] is True
    assert any("JSONL line 1 is missing 'header' metadata" in w for w in res2["warnings"])

    p3 = tmp_path / "err3.jsonl"
    p3.write_text('{"unclosed dict\n')
    res3 = validate_archive(str(p3), logger)
    assert res3["valid"] is False
    assert any("JSONL syntax error on line 1" in err for err in res3["errors"])


def test_validate_archive_xml_rss_errors(tmp_path, logger):
    p1 = tmp_path / "rss_missing_channel.xml"
    p1.write_text("<rss></rss>")
    res1 = validate_archive(str(p1), logger)
    assert res1["valid"] is False
    assert any("RSS XML is missing the '<channel>' element" in err for err in res1["errors"])

    p2 = tmp_path / "rss_missing_fields.xml"
    p2.write_text("<rss><channel><item><title></title></item></channel></rss>")
    res2 = validate_archive(str(p2), logger)
    assert res2["valid"] is True
    assert any("missing '<title>'" in w for w in res2["warnings"])
    assert any("missing '<author>'" in w for w in res2["warnings"])

    p3 = tmp_path / "xml_missing_header.xml"
    p3.write_text("<messages><message><text>Hello</text></message></messages>")
    res3 = validate_archive(str(p3), logger)
    assert res3["valid"] is True
    assert any("XML message 1 is missing '<header>' metadata" in w for w in res3["warnings"])

    p4 = tmp_path / "xml_parse_fail.xml"
    p4.write_text("<messages><message>")
    res4 = validate_archive(str(p4), logger)
    assert res4["valid"] is False
    assert any("XML parsing failed" in err for err in res4["errors"])


def test_validate_archive_sqlite_missing_columns(tmp_path, logger):
    p = tmp_path / "missing_cols.db"
    conn = sqlite3.connect(p)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE messages (author TEXT, recipient TEXT)")
    conn.commit()
    conn.close()

    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("SQLite 'messages' table is missing required columns" in err for err in res["errors"])
    assert any("subject" in err for err in res["errors"])


def test_validate_archive_metadata_warnings(tmp_path, logger):
    p1 = tmp_path / "messages.dat"
    content1 = make_qwk_messages_content(msgnum_val=0)
    p1.write_bytes(content1)
    res1 = validate_archive(str(p1), logger)
    assert res1["valid"] is True
    assert any("has invalid/non-positive message number: 0" in w for w in res1["warnings"])

    p2 = tmp_path / "messages.dat"
    content2 = make_qwk_messages_content(msgfrom="   ", msgto="  ", msgsubject=" ")
    p2.write_bytes(content2)
    res2 = validate_archive(str(p2), logger)
    assert res2["valid"] is True
    assert any("is missing sender (msgfrom) field" in w for w in res2["warnings"])
    assert any("is missing recipient (msgto) field" in w for w in res2["warnings"])
    assert any("is missing subject field" in w for w in res2["warnings"])


def test_validate_archive_unrecognized_format(tmp_path, logger):
    p = tmp_path / "test.xyz"
    p.write_text("random content")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert any("Unrecognized archive format" in w for w in res["warnings"])


def test_validate_archive_load_data_returns_bytes(tmp_path, logger, monkeypatch):
    import pyqwk.core
    p = tmp_path / "test.txt"
    p.write_text("From: Bob\nTo: Alice\nSubject: Hi\nDate: 10-12-23\n\nBody text")

    monkeypatch.setattr(pyqwk.core, "load_data", lambda *args, **kwargs: (b"byte stream", "utf-8"))

    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert any("Load returned byte stream instead of parsed messages" in w for w in res["warnings"])
