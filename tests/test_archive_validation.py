import os
import json
import csv
import sqlite3
import xml.etree.ElementTree as ET
import pytest
import logging
from unittest.mock import MagicMock
from pyqwk.core import validate_archive, MessageHeader, ParsedMessage, BLOCK_SIZE


@pytest.fixture
def logger():
    return logging.getLogger("test_validation")


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
