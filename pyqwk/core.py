import sys
import atexit
import zipfile
import tarfile
import subprocess
import tempfile
import struct
import re
import hashlib
import os
import shutil
import logging
import json
import html
import csv
import io
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, fields, replace
import mailbox
import email
from contextlib import nullcontext
from typing import Any, Callable, Protocol
import datetime
import email.utils
import sqlite3
import binascii
import base64
import random

__version__ = "0.1.0"

BLOCK_SIZE = 128
QWK_HEADER_FORMAT = "<c7s8s5s25s25s25s12s8s6scHHc"
MESSAGES_FILENAME = "messages.dat"
REPLY_FILENAME = "reply.dat"
CONTROL_FILENAME = "control.dat"


def _is_maildir(path: str) -> bool:
    """Check if a directory is a valid Maildir."""
    if not os.path.isdir(path):
        return False
    # A Maildir is a directory containing 'cur', 'new', and 'tmp' subdirectories.
    try:
        subdirs = set(os.listdir(path))
        return {"cur", "new", "tmp"}.issubset(subdirs)
    except OSError:
        return False


def expand_paths(paths: list[str]) -> list[str]:
    """Recursively find supported QWK files in directories, expanding glob wildcards."""
    import glob
    expanded_paths = []

    # Expand glob patterns first
    globbed_paths = []
    for path in paths:
        if any(char in path for char in ("*", "?", "[", "]")):
            matches = glob.glob(path, recursive=True)
            if matches:
                globbed_paths.extend(matches)
            else:
                globbed_paths.append(path)
        else:
            globbed_paths.append(path)

    for path in globbed_paths:
        if os.path.isdir(path):
            if _is_maildir(path):
                expanded_paths.append(path)
                continue

            for root, dirs, files in os.walk(path):
                if _is_maildir(root):
                    expanded_paths.append(root)
                    del dirs[:]  # Don't recurse into Maildir subdirectories
                    continue

                for file in files:
                    lower_file = file.lower()
                    if lower_file.endswith(
                        (
                            ".qwk",
                            ".zip",
                            ".tar",
                            ".tar.gz",
                            ".tar.bz2",
                            ".tgz",
                            ".rep",
                            ".json",
                            ".jsonl",
                            ".csv",
                            ".db",
                            ".sqlite",
                            ".xml",
                            ".rss",
                            ".mbox",
                            ".eml",
                            ".md",
                            ".markdown",
                            ".html",
                            ".htm",
                            ".txt",
                        )
                    ) or lower_file in (MESSAGES_FILENAME, REPLY_FILENAME):
                        expanded_paths.append(os.path.join(root, file))
        else:
            expanded_paths.append(path)
    return sorted(expanded_paths)


FORMAT_EXTENSIONS = {
    "text": ".txt",
    "json": ".json",
    "jsonl": ".jsonl",
    "xml": ".xml",
    "html": ".html",
    "markdown": ".md",
    "mbox": ".mbox",
    "csv": ".csv",
    "rss": ".rss",
    "sqlite": ".db",
    "eml": ".eml",
    "maildir": ".maildir",
    "qwk": ".qwk",
    "rep": ".rep",
}


def resolve_output_format(
    output_format: str | None,
    output_path: str | None,
    output_mode: str,
) -> str:
    """Determine the output format based on the user's choice or the file extension.

    Args:
        output_format: The format explicitly requested by the user (e.g., 'json', 'html').
        output_path: The path where the output will be saved.
        output_mode: Whether the output is going to a 'file' or 'the screen'.

    Returns:
        The resolved format name (e.g., 'text', 'json', 'html').
    """
    if output_format is not None:
        return output_format

    if output_path and output_mode == "file":
        ext = os.path.splitext(output_path)[1].lower()
        mapping = {
            ".json": "json",
            ".jsonl": "jsonl",
            ".xml": "xml",
            ".html": "html",
            ".csv": "csv",
            ".mbox": "mbox",
            ".eml": "eml",
            ".rss": "rss",
            ".md": "markdown",
            ".markdown": "markdown",
            ".sqlite": "sqlite",
            ".db": "sqlite",
            ".maildir": "maildir",
            ".mdir": "maildir",
            ".qwk": "qwk",
            ".rep": "rep",
        }
        if ext in mapping:
            return mapping[ext]

    return "text"


def detect_extension(data: bytes) -> str:
    """Auto-detect the file extension/format based on the leading bytes of piped data."""
    if not data:
        return ".txt"

    # SQLite
    if data.startswith(b"SQLite format 3\x00"):
        return ".db"

    # ZIP
    if data.startswith(b"PK\x03\x04"):
        return ".zip"

    # GZIP (often TAR)
    if data.startswith(b"\x1f\x8b"):
        return ".tar.gz"

    # BZIP2 (often TAR)
    if data.startswith(b"BZh"):
        return ".tar.bz2"

    # Check for TAR signature (ustar at offset 257)
    if len(data) > 262 and data[257:262] == b"ustar":
        return ".tar"

    # Decode a chunk of data as utf-8 to inspect text
    sample = data[:2048].decode("utf-8", errors="replace").strip()
    sample_lower = sample.lower()

    # JSON or JSONL
    if sample.startswith("{") or sample.startswith("["):
        try:
            json.loads(data.decode("utf-8", errors="replace"))
            return ".json"
        except Exception:
            return ".jsonl"

    # XML or RSS
    if sample.startswith("<?xml") or sample.startswith("<rss") or "<channel" in sample_lower:
        if "<rss" in sample_lower or "<channel" in sample_lower:
            return ".rss"
        return ".xml"

    # HTML
    if sample_lower.startswith("<!doctype html") or sample_lower.startswith("<html") or "<body" in sample_lower:
        return ".html"

    # mbox
    if sample.startswith("From "):
        return ".mbox"

    # EML / Email headers
    has_headers = (
        "date:" in sample_lower and
        "from:" in sample_lower and
        "to:" in sample_lower and
        "subject:" in sample_lower
    )
    if has_headers:
        return ".eml"

    # Markdown
    if (
        sample.startswith("# ") or
        "\n# " in sample or
        "## " in sample or
        "- **" in sample or
        "\n- **" in sample
    ) and "---" in sample:
        return ".md"

    # CSV
    lines = sample.splitlines()
    if lines:
        first_line = lines[0].lower()
        if "," in first_line and any(h in first_line for h in ("msgfrom", "msgto", "msgsubject", "text", "author", "recipient")):
            return ".csv"

    # Default to text
    return ".txt"


_temp_files_to_clean: list[str] = []


def _cleanup_temp_files():
    for path in _temp_files_to_clean:
        try:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        except Exception:
            pass


atexit.register(_cleanup_temp_files)


def check_and_handle_stdin(paths: list[str], logger: logging.Logger) -> list[str]:
    """Check for standard input ('-') in paths, read it, and save to a temporary file."""
    if not paths:
        return paths

    new_paths = []
    for path in paths:
        if path == "-":
            try:
                logger.info("Reading from standard input...")
                data = sys.stdin.buffer.read()
                ext = detect_extension(data)

                # Write to a temporary file with the auto-detected extension
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                temp_file.write(data)
                temp_file.close()

                logger.info("Auto-detected piped format as %s", ext.lstrip("."))

                # Register for cleanup
                _temp_files_to_clean.append(temp_file.name)
                new_paths.append(temp_file.name)
            except Exception as e:
                logger.error("Failed to read from standard input: %s", e)
                sys.exit(1)
        else:
            new_paths.append(path)

    return new_paths


RE_QUOTE_PATTERN = re.compile(r"^\s*[A-Za-z\-\=]{0,4}\s?(>|\xb3|\||\}|│)")
RE_UUE_PATTERN = re.compile(r"^begin\s+\d{3}\s+")
# Match UUE data lines, which traditionally start with 'M' and contain 60 characters of encoded data.
RE_UUE_DATA_PATTERN = re.compile(r"^M[\x20-\x60]{60}$")
RE_UUE_LOOSE_PATTERN = re.compile(r"^[\x21-\x4d][\x20-\x60]{1,60}$")
# Identify Base64 blocks by looking for long strings of characters commonly used in Base64 encoding.
RE_BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/=]{60,}$")
RE_YENC_PATTERN = re.compile(r"^=y(begin|part|end)")
RE_BASE64_LOOSE_PATTERN = re.compile(r"^[A-Za-z0-9+/=]{1,}$")
RE_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_URL_PATTERN = re.compile(
    r'\b(?:https?|ftp|telnet|gopher)://[^\s<>"]+|www\.[^\s<>"]+', re.IGNORECASE
)
# Match phone numbers while avoiding false positives from dates (like 2023-10-12).
# It requires at least 7 digits to ensure the match is likely a phone number.
RE_PHONE_PATTERN = re.compile(
    r"(?<!\w)"
    r"(?!(?:19|20)\d{2}[-./]\d{2}[-./]\d{2}\b)"
    r"(?=(?:\D*\d){7,})"
    r"(?:"
    r"(?:\+\d{1,3}[-\.\s]?)?"
    r"(?:\(\d{1,4}\)|\d{1,4})"
    r"[-\.\s]?\d{3,4}(?:[-\.\s]?\d{3,4}){1,3}"
    r"|"
    r"\d{3}[-\.\s]?\d{4}"
    r")"
    r"\b"
)

RE_SUBJECT_PREFIX_PATTERN = re.compile(
    r"^\s*(?:re|fw|fwd)(?:\[\d+\])?[:\s-]+\s*", re.IGNORECASE
)

RE_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# Identify internal message references like "msg #123" or "message 456".
RE_MSG_LINK_PATTERN = re.compile(r"(?i)\b(?:msg|message|msg#)\s*#?(\d+)\b")

# Exclude common words from keyword statistics to ensure the report highlights unique and meaningful terms.
DEFAULT_STOP_WORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "have",
    "was",
    "were",
    "but",
    "not",
    "are",
    "you",
    "your",
    "his",
    "her",
    "they",
    "them",
    "their",
    "will",
    "can",
    "has",
    "had",
    "been",
    "which",
    "who",
    "how",
    "when",
    "where",
    "all",
    "any",
    "some",
    "there",
    "what",
    "about",
    "just",
    "more",
    "very",
    "than",
    "then",
    "also",
    "only",
    "even",
    "into",
    "most",
    "well",
    "would",
    "could",
    "should",
    "these",
    "those",
    "much",
    "many",
    "once",
    "here",
    "back",
    "still",
    "over",
    "must",
    "does",
    "made",
    "said",
    "went",
    "came",
    "down",
    "give",
    "take",
    "find",
    "look",
    "work",
    "part",
}

# Identify common markers that separate a message's body from the user's signature.
# This allows the tool to hide signatures for a cleaner reading experience.
SIGNATURE_PATTERNS_EXACT = {
    "---",
    "___",
    "--",
    "-----BEGIN PGP SIGNATURE-----",
    "___--BEGIN PGP SIGNATURE-----",
    "-----BEGIN GPG SIGNATURE-----",
}

SIGNATURE_PATTERNS_STARTSWITH = (
    " * ",
    "--- ",
    "-- ",
    "___ ",
    "... ",
    "-+- ",
    "~~~ ",
    " \xfe ",
    " ■ ",
    " *** ",
)


def _is_binary_line(
    line: str,
    previous_line: str | None,
    in_yenc_block: bool,
    in_uue_block: bool,
    in_base64_block: bool,
) -> tuple[bool, bool, bool, bool]:
    """Check if a line of text is part of an attachment (like an image).

    This function tracks whether we are currently inside an attachment block
    (yEnc, UUE, or Base64) to find where they start and end within a message.

    Returns a group of four values:
    - True if the line is part of an attachment and should be hidden.
    - True if we are currently in a yEnc block.
    - True if we are currently in a UUE block.
    - True if we are currently in a Base64 block.
    """
    stripped_line = line.strip()

    if in_base64_block:
        if RE_BASE64_LOOSE_PATTERN.match(stripped_line):
            return True, in_yenc_block, in_uue_block, True
        in_base64_block = False

    is_yenc_marker = RE_YENC_PATTERN.match(stripped_line)

    if is_yenc_marker:
        return (
            True,
            not stripped_line.startswith("=yend"),
            in_uue_block,
            in_base64_block,
        )

    if in_yenc_block:
        return True, True, in_uue_block, in_base64_block

    if in_uue_block:
        if stripped_line in ("end", "`"):
            return True, in_yenc_block, False, in_base64_block
        if not stripped_line or RE_UUE_LOOSE_PATTERN.match(stripped_line):
            return True, in_yenc_block, True, in_base64_block
        in_uue_block = False

    if stripped_line == "end" and previous_line and previous_line.strip() == "`":
        return True, in_yenc_block, False, in_base64_block

    if RE_BASE64_PATTERN.match(stripped_line):
        return True, in_yenc_block, in_uue_block, True
    elif RE_UUE_DATA_PATTERN.match(stripped_line) or RE_UUE_PATTERN.match(
        stripped_line
    ):
        return True, in_yenc_block, True, in_base64_block
    elif RE_UUE_LOOSE_PATTERN.match(stripped_line):
        if previous_line and (
            RE_UUE_DATA_PATTERN.match(previous_line)
            or RE_UUE_PATTERN.match(previous_line)
        ):
            return True, in_yenc_block, True, in_base64_block

    return False, in_yenc_block, False, in_base64_block


def extract_binaries(text: str) -> list[tuple[str, bytes]]:
    """Scan text for attachments (like UUE, yEnc, or Base64) and decode them.

    Returns:
        A list of pairs containing the filename and the file data as bytes.
    """
    lines = text.splitlines()
    binaries: list[tuple[str, bytes]] = []

    in_uue = False
    in_base64 = False
    in_yenc = False

    current_filename = ""
    current_data: list[str] = []

    uue_begin_re = re.compile(r"^begin\s+\d{3}\s+(.+)$")
    yenc_begin_re = re.compile(r"^=ybegin.*name=(.+)$")

    def _flush_binary():
        nonlocal in_uue, in_base64, in_yenc
        decoded = b""
        if in_uue:
            for line in current_data:
                if not line:
                    continue
                try:
                    # binascii.a2b_uu expects the length character at the start
                    decoded += binascii.a2b_uu(line)
                except (binascii.Error, ValueError):
                    continue
        elif in_base64:
            try:
                # Append missing padding to ensure valid Base64 decoding
                b64_str = "".join(current_data)
                padding_needed = (4 - (len(b64_str) % 4)) % 4
                if padding_needed != 3:  # 1 extra char is invalid in Base64
                    b64_str += "=" * padding_needed
                decoded = base64.b64decode(b64_str)
            except (binascii.Error, ValueError, TypeError):
                decoded = b""
        elif in_yenc:
            try:
                encoded_str = "".join(current_data)
                decoded_bytes = bytearray()
                escaped = False
                for char in encoded_str:
                    if char == "=" and not escaped:
                        escaped = True
                        continue
                    val = ord(char)
                    if escaped:
                        val = (val - 64) % 256
                        escaped = False
                    decoded_bytes.append((val - 42) % 256)
                decoded = bytes(decoded_bytes)
            except Exception:
                decoded = b""

        if decoded:
            binaries.append((current_filename, decoded))
        in_uue = in_base64 = in_yenc = False

    for line in lines:
        clean_line = line.strip()

        if in_uue:
            if clean_line == "end" or clean_line == "`":
                _flush_binary()
                continue
            elif uue_begin_re.match(clean_line) or yenc_begin_re.match(clean_line):
                _flush_binary()
            else:
                # Basic check: if it looks like a UUE line (starts with M and has decent length)
                # or is a common last line (length character at start matches line length)
                # we add it.
                current_data.append(line)  # Use original line for UUE as spaces matter
                continue

        if in_base64:
            if not RE_BASE64_LOOSE_PATTERN.match(clean_line):
                _flush_binary()
                # Fall through to check if this line starts another block
            else:
                current_data.append(clean_line)
                continue

        if in_yenc:
            if clean_line.startswith("=yend"):
                _flush_binary()
                continue
            elif uue_begin_re.match(clean_line) or yenc_begin_re.match(clean_line):
                _flush_binary()
            else:
                current_data.append(line)
                continue

        # Check for block starts
        # Check for UUE begin
        uue_match = uue_begin_re.match(clean_line)
        if uue_match:
            in_uue = True
            current_filename = uue_match.group(1).strip()
            current_data = []
            continue

        # Check for yEnc begin
        yenc_match = yenc_begin_re.match(clean_line)
        if yenc_match:
            in_yenc = True
            current_filename = yenc_match.group(1).strip()
            current_data = []
            continue

        # Check for Base64 (starts with high density line)
        if RE_BASE64_PATTERN.match(clean_line):
            in_base64 = True
            current_filename = "attachment.bin"
            current_data = [clean_line]
            continue

    # Handle unterminated blocks at end of text
    _flush_binary()

    return binaries


def _bytes_to_uue(data: bytes, filename: str) -> str:
    """Convert binary data into a UUE-encoded text block.

    Args:
        data: The binary data to encode.
        filename: The filename to include in the UUE header.

    Returns:
        A string containing the formatted UUE block.
    """
    if not data:
        return ""

    result = [f"begin 644 {filename}"]

    # Process data in 45-byte chunks as per UUE standard
    for i in range(0, len(data), 45):
        chunk = data[i : i + 45]
        # b2a_uu handles the length prefix and encoding
        line = binascii.b2a_uu(chunk).decode("ascii").rstrip("\n")
        result.append(line)

    result.append("`")  # UUE zero-length line indicator
    result.append("end")
    return "\n".join(result) + "\n"


class ProgressBar(Protocol):
    def update(self, __n: int, /) -> None:
        """Advance the progress by ``__n`` units."""


@dataclass
class ProcessingSettings:
    """A collection of settings used to control how messages are processed.

    This class stores user preferences and configuration for reading,
    filtering, and saving messages.
    """

    verbose: bool
    private: bool
    no_header: bool
    truncate_signatures: bool
    cut_quoting: bool
    individual_files: bool
    threaded: bool
    binaries_removal: bool
    redact_pii: bool
    format: str
    separator: str
    output_mode: str
    output_path: str | None
    encoding: str
    filename_pattern: str | None = None
    oneline_pattern: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    regex: bool = False
    dry_run: bool = False
    strip_ansi: bool = False
    quiet: bool = False
    headers_only: bool = False
    merge: bool = False
    unique: bool = False
    organize: bool = False
    organize_by_date: bool = False
    organize_by_bbs: bool = False
    organize_by_author: bool = False
    organize_by_to: bool = False
    organize_by_subject: bool = False
    include_toc: bool = False
    extract_attachments: bool = False
    embed_attachments: bool = False
    organize_attachments: bool = False
    msgnum_filters: set[int] | None = None
    conferences: list[str] | None = None
    bbs_names: list[str] | None = None
    authors: list[str] | None = None
    recipients: list[str] | None = None
    subjects: list[str] | None = None
    search_term: str | None = None
    after: datetime.datetime | None = None
    before: datetime.datetime | None = None
    limit: int | None = None
    skip: int | None = None
    sort: str | None = None
    reverse: bool = False
    oneline: bool = False
    has_attachments: bool = False
    mine: bool = False
    on_this_day: bool = False
    reference_date: datetime.datetime | None = None
    merge_stats: bool = False
    has_links: bool = False
    has_emails: bool = False
    has_phones: bool = False
    has_ansi: bool = False
    has_msg_links: bool = False
    my_name: str | None = None
    body_search: str | None = None
    exclude_search: str | None = None
    exclude_authors: list[str] | None = None
    exclude_recipients: list[str] | None = None
    exclude_subjects: list[str] | None = None
    exclude_conferences: list[str] | None = None
    exclude_bbs_names: list[str] | None = None
    organize_pattern: str | None = None
    tail: int | None = None
    min_words: int | None = None
    max_words: int | None = None
    limit_per_conf: int | None = None
    limit_per_author: int | None = None
    limit_per_to: int | None = None
    limit_per_subject: int | None = None
    limit_per_bbs: int | None = None
    min_attachments: int | None = None
    max_attachments: int | None = None
    min_depth: int | None = None
    max_depth: int | None = None
    min_replies: int | None = None
    max_replies: int | None = None
    min_thread_size: int | None = None
    max_thread_size: int | None = None
    refnum_filters: set[int] | None = None
    thread_id_filters: set[int] | None = None
    attachment_pattern: str | None = None
    count_only: bool = False


@dataclass
class BBSInfo:
    """Information about the Bulletin Board System (BBS) that created the archive.

    This is usually found in the 'CONTROL.DAT' file in QWK packets or in
    the header of files like SQLite.
    """

    name: str = ""
    location: str = ""
    phone: str = ""
    sysop: str = ""
    serial_number: str = ""
    bbs_id: str = ""
    user_name: str = ""
    packet_at: str = ""
    total_messages: int = 0
    num_conferences: int = 0


class ConferenceMap(dict):
    """A dictionary mapping conference numbers to names, with optional BBS information."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bbs_info: BBSInfo | None = None


@dataclass
class ParsedMessage:
    """A fully parsed and processed message from an archive.

    This class contains the message body text, conference details, and
    information used for organizing conversations.
    """

    text: str
    msgnum: int | None
    refnum: int | None
    confnum: int
    header: "MessageHeader"
    depth: int = 0
    thread_id: str | None = None
    parent_msgnum: int | None = None
    confname: str | None = None
    bbs_name: str | None = None
    bbs_id: str | None = None
    source_file: str | None = None
    attachments: list[str] | None = None
    original_text: str | None = None
    reply_count: int = 0
    thread_size: int = 1

    def discover_attachments(self) -> list[str] | None:
        """Lazily discover and cache attachment filenames from the message text."""
        if self.text and self.attachments is None:
            found_binaries = extract_binaries(self.text)
            self.attachments = [name for name, data in found_binaries]
        return self.attachments


# Keep old names for compatibility
ProcessedMessage = ParsedMessage


@dataclass
class MessageHeader:
    """The information header for a single message in the QWK format.

    These fields match the fixed-length structure used in older BBS
    message packets.
    """

    status: str
    msgnum: int | None
    msgdate: str
    msgtime: str
    msgto: str
    msgfrom: str
    msgsubject: str
    msgpassword: str
    refnum: int | None
    numblocks: int | None
    msgflag: str
    confnum: int
    lognum: int
    nettag: str

    @property
    def is_private(self) -> bool:
        """Return True if the message is marked as private."""
        return self.status not in (" ", "-")

    @property
    def is_password(self) -> bool:
        """Return True if the message is protected by a password."""
        return self.status in ("%", "^", "!", "#", "$")

    @property
    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            result[field.name] = "" if value is None else value
        return result

    def to_bytes(self, encoding: str = "cp437") -> bytes:
        """Convert the message header into a 128-byte QWK record."""

        def encode_pad(text: str, length: int, align: str = "left") -> bytes:
            if align == "right":
                return text.rjust(length).encode(encoding)[:length]
            return text.ljust(length).encode(encoding)[:length]

        def get_char_bytes(text: str) -> bytes:
            b = text.encode(encoding)
            return b[:1] if b else b" "

        # QWK headers use right-aligned, space-padded strings for numeric fields
        msgnum_raw = str(self.msgnum if self.msgnum is not None else 0)
        refnum_raw = str(self.refnum if self.refnum is not None else 0)
        numblocks_raw = str(self.numblocks if self.numblocks is not None else 0)

        # Re-pack the data using the same format as from_bytes
        return struct.pack(
            QWK_HEADER_FORMAT,
            get_char_bytes(self.status),
            encode_pad(msgnum_raw, 7, "right"),
            encode_pad(self.msgdate, 8),
            encode_pad(self.msgtime, 5),
            encode_pad(self.msgto, 25),
            encode_pad(self.msgfrom, 25),
            encode_pad(self.msgsubject, 25),
            encode_pad(self.msgpassword, 12),
            encode_pad(refnum_raw, 8, "right"),
            encode_pad(numblocks_raw, 6, "right"),
            get_char_bytes(self.msgflag),
            self.confnum,
            self.lognum,
            get_char_bytes(self.nettag),
        )

    @classmethod
    def from_bytes(cls, record: bytes, encoding: str = "cp437") -> "MessageHeader":
        try:
            header_data = struct.unpack(QWK_HEADER_FORMAT, record)
        except struct.error as error:
            raise MessagesDatFormatError(
                "messages.dat header record has invalid size or format."
            ) from error

        (
            status,
            raw_msgnum,
            raw_msgdate,
            raw_msgtime,
            raw_msgto,
            raw_msgfrom,
            raw_msgsubject,
            raw_msgpassword,
            raw_refnum,
            raw_numblocks,
            msgflag,
            confnum,
            lognum,
            nettag,
        ) = header_data

        def decode_clean(b: bytes, strip_whitespace: bool = True) -> str:
            try:
                s = b.decode(encoding).split("\x00")[0]
                return s.strip() if strip_whitespace else s
            except UnicodeDecodeError as e:
                raise MessagesDatFormatError(
                    f"Failed to decode header field with encoding '{encoding}'."
                ) from e

        msgnum_text = decode_clean(raw_msgnum)
        msgnum = int(msgnum_text) if msgnum_text.isdigit() else None

        msgdate = decode_clean(raw_msgdate)
        msgtime = decode_clean(raw_msgtime)
        msgto = decode_clean(raw_msgto, strip_whitespace=False)
        msgfrom = decode_clean(raw_msgfrom, strip_whitespace=False)
        msgsubject = decode_clean(raw_msgsubject, strip_whitespace=False)
        msgpassword = decode_clean(raw_msgpassword)

        refnum_text = decode_clean(raw_refnum)
        refnum: int | None
        if refnum_text.isdigit():
            refnum_value = int(refnum_text)
            refnum = None if refnum_value == 0 else refnum_value
        else:
            refnum = None

        numblocks_text = decode_clean(raw_numblocks)
        try:
            numblocks = int(numblocks_text)
        except ValueError:
            numblocks = None

        header = cls(
            status=status.decode(encoding),
            msgnum=msgnum,
            msgdate=msgdate,
            msgtime=msgtime,
            msgto=msgto,
            msgfrom=msgfrom,
            msgsubject=msgsubject,
            msgpassword=msgpassword,
            refnum=refnum,
            numblocks=numblocks,
            msgflag=msgflag.decode(encoding),
            confnum=confnum,
            lognum=lognum,
            nettag=nettag.decode(encoding),
        )

        header._numblocks_raw = numblocks_text  # type: ignore[attr-defined]
        message_type = header.status

        valid_status_chars = {"+", "*", "~", "`", "%", "^", "!", "#", "$", " ", "-"}
        if message_type not in valid_status_chars:
            raise InvalidMessageTypeError(message_type)

        return header

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageHeader":
        """Reconstruct a MessageHeader from a dictionary."""
        kwargs = {}
        for field_info in fields(cls):
            name = field_info.name
            val = data.get(name)
            if name in ("msgnum", "refnum", "numblocks", "confnum", "lognum"):
                kwargs[name] = _safe_to_int(val)
            else:
                kwargs[name] = val if val is not None else ""

        return cls(**kwargs)

    def format_text(
        self,
        board_dict: Mapping[int, str],
        verbose: bool,
        include_separator: bool = True,
        use_colors: bool = False,
        highlight_term: str | None = None,
        is_regex: bool = False,
        attachments: list[str] | None = None,
        bbs_name: str | None = None,
        redact_pii: bool = False,
    ) -> str:
        """Render a message header into readable text.

        Args:
            board_dict: Mapping of conference numbers to human-readable names.
            verbose: Whether to include extra information such as message numbers and reference numbers.
            include_separator: Whether to prepend the message separator line.
            use_colors: Whether to use ANSI colors for terminal output.
            highlight_term: Optional term to highlight in the header values.
            is_regex: Whether the highlight_term is a regular expression.
            redact_pii: Whether to hide personal information.

        Returns:
            The formatted header text with DOS-style newlines appended.
        """
        not_found_flag = False
        try:
            conf_name = board_dict[self.confnum]
        except KeyError:
            conf_name = str(self.confnum)
            not_found_flag = True

        def fmt_line(
            label: str, value: str, newline: bool = True, pad: int = 16
        ) -> str:
            suffix = "\r\n" if newline else ""
            label_fmt = f"{label:<{pad}}"
            label_part = _colorize(label_fmt, "90", enabled=use_colors)
            if redact_pii:
                value = _redact_pii(value)
            formatted_val = _linkify_text(
                value, "ansi", search_term=highlight_term, is_regex=is_regex, use_colors=use_colors
            )
            return f"{label_part}{formatted_val}{suffix}"

        header_parts: list[str] = []
        if include_separator:
            # Match terminal width up to 80 chars for a polished look
            try:
                width = shutil.get_terminal_size().columns
            except (AttributeError, ValueError):  # pragma: no cover
                width = 80
            width = min(80, width)

            sep = ("-" * width) + "\r\n"
            header_parts.append(_colorize(sep, "90", enabled=use_colors))

        if verbose or not not_found_flag:
            header_parts.append(fmt_line("Conference:", str(conf_name)))

        if bbs_name:
            header_parts.append(fmt_line("BBS:", bbs_name))

        if self.is_private:
            header_parts.append(fmt_line("Status:", "[PRIVATE]"))

        if verbose:
            message_number = str(self.msgnum) if self.msgnum is not None else ""
            # Message number and Date share a line in verbose mode for better information density
            header_parts.append(
                fmt_line("Message #:", message_number, newline=False, pad=16)
            )
            header_parts.append("    ")  # Spacer between columns
            header_parts.append(
                fmt_line("Date:", self.msgdate + " " + self.msgtime, pad=12)
            )
        else:
            header_parts.append(fmt_line("Date:", self.msgdate + " " + self.msgtime))

        header_parts.append(fmt_line("From:", self.msgfrom.strip()))
        header_parts.append(fmt_line("To:", self.msgto.strip()))
        header_parts.append(fmt_line("Subject:", self.msgsubject.strip()))

        if verbose:
            reference_number = str(self.refnum) if self.refnum is not None else ""
            header_parts.append(fmt_line("Reference #:", reference_number))

            if attachments:
                header_parts.append(fmt_line("Attachments:", ", ".join(attachments)))

        header_parts.append("\r\n")
        return "".join(header_parts)

    def format_oneline(
        self,
        board_dict: Mapping[int, str],
        use_colors: bool = False,
        highlight_term: str | None = None,
        is_regex: bool = False,
        verbose: bool = False,
        depth: int = 0,
        conf_name: str | None = None,
        is_private: bool = False,
        has_attachments: bool = False,
        redact_pii: bool = False,
    ) -> str:
        """Render a message header as a single line summary."""
        if conf_name is None:
            conf_name = board_dict.get(self.confnum, str(self.confnum))
        date_str = f"{self.msgdate} {self.msgtime}"
        from_name = self.msgfrom.strip()
        to_name = self.msgto.strip()
        subject = self.msgsubject.strip()

        if redact_pii:
            from_name = _redact_pii(from_name)
            to_name = _redact_pii(to_name)
            subject = _redact_pii(subject)

        def prepare_field(text: str, width: int, dim: bool = False) -> str:
            truncated = text[:width]
            display_len = len(truncated)
            truncated = _linkify_text(
                truncated, "ansi", search_term=highlight_term, is_regex=is_regex, use_colors=use_colors
            )
            res = truncated + (" " * (width - display_len))
            return _colorize(res, "90", enabled=use_colors and dim)

        conf_part = prepare_field(conf_name, 12, dim=True)
        from_part = prepare_field(from_name, 15)
        to_part = prepare_field(to_name, 15)

        # Indicators for private and attachments
        flags = ""
        if is_private:
            flags += "*"
        if has_attachments:
            flags += "@"

        # Apply conversation indent to subject
        if depth > 0:
            indent = "  " * (depth - 1)
            subject = f"{indent}└ {subject}"

        flags_display = flags.ljust(3)
        flags_display = _colorize(flags_display, "90", enabled=use_colors)
        subject = f"{flags_display} {subject}"
        subject_part = _linkify_text(
            subject, "ansi", search_term=highlight_term, is_regex=is_regex, use_colors=use_colors
        )

        msgnum_part = ""
        if verbose:
            msgnum_val = str(self.msgnum or "")
            msgnum_part = _colorize(f"{msgnum_val:<6}", "90", enabled=use_colors) + " "

        date_part = date_str.ljust(14)
        date_part = _colorize(date_part, "90", enabled=use_colors)

        return f"{msgnum_part}{conf_part} {date_part} {from_part} {to_part} {subject_part}\r\n"


class MessagesDatFormatError(Exception):
    """Raised when the input file is not a valid messages.dat file."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "Invalid messages.dat format.")


class ControlDatFormatError(Exception):
    """Raised when the control.dat file is not a valid format."""


class InvalidMessageTypeError(Exception):
    """Raised when an unexpected message type is encountered."""

    def __init__(self, message_type: str) -> None:
        super().__init__(f"Invalid message type '{message_type}'")
        self.message_type = message_type


PROCESSING_EXCEPTIONS = (
    MessagesDatFormatError,
    ControlDatFormatError,
    InvalidMessageTypeError,
    FileNotFoundError,
    zipfile.BadZipFile,
    IOError,
)


class LogFormatter(logging.Formatter):
    """Custom log formatter that applies colors to log levels."""

    GREY = "\x1b[90m"
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    def __init__(self, use_colors: bool = True) -> None:
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = "%(levelname)s: %(message)s"

        if record.levelno == logging.INFO:
            # For INFO, just show the message
            log_fmt = "%(message)s"

        if self.use_colors:
            if record.levelno == logging.DEBUG:
                log_fmt = f"{self.GREY}{log_fmt}{self.RESET}"
            elif record.levelno == logging.WARNING:
                log_fmt = f"{self.YELLOW}{log_fmt}{self.RESET}"
            elif record.levelno == logging.ERROR:
                log_fmt = f"{self.RED}{log_fmt}{self.RESET}"
            elif record.levelno == logging.CRITICAL:
                log_fmt = f"{self.BOLD_RED}{log_fmt}{self.RESET}"

        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def _parse_sqlite_messages(db_path: str) -> tuple[list[ParsedMessage], ConferenceMap]:
    """Import messages and archive information from a pyqwk SQLite database."""
    # Ensure the file exists before connecting to avoid creating an empty database
    if db_path and db_path != ":memory:" and not os.path.exists(db_path):
        raise sqlite3.OperationalError(f"unable to open database file: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        try:
            cursor.execute("SELECT 1 FROM messages LIMIT 1")
        except sqlite3.OperationalError as e:
            raise ValueError(f"SQLite database is missing the 'messages' table: {e}")

        # Try to load BBS Info
        bbs_info = BBSInfo()
        try:
            cursor.execute("SELECT * FROM bbs_info LIMIT 1")
            row = cursor.fetchone()
            if row:
                for field in fields(BBSInfo):
                    if field.name in row.keys():
                        setattr(bbs_info, field.name, row[field.name])
        except sqlite3.OperationalError:
            pass

        # Try to load Conferences
        board_dict = ConferenceMap()
        board_dict.bbs_info = bbs_info
        try:
            cursor.execute("SELECT * FROM conferences")
            for row in cursor.fetchall():
                board_dict[row["number"]] = row["name"]
        except sqlite3.OperationalError:
            pass

        cursor.execute("SELECT * FROM messages")
        messages = []
        for row in cursor.fetchall():
            # Reconstruct header dict
            header_dict = {
                "confnum": row["conference_number"],
                "msgnum": row["message_number"],
                "msgdate": row["date"],
                "msgtime": "",  # ISO date in SQLite includes time
                "msgfrom": row["author"],
                "msgto": row["recipient"],
                "msgsubject": row["subject"],
                "status": row["status"],
                "refnum": row["reference_number"],
            }

            header = MessageHeader.from_dict(header_dict)

            attachments = row["attachments"].split(";") if row["attachments"] else None

            msg = ParsedMessage(
                text=row["text"],
                msgnum=header.msgnum,
                refnum=header.refnum,
                confnum=header.confnum,
                header=header,
                depth=_safe_to_int(row["depth"]) or 0,
                thread_id=row["thread_id"],
                parent_msgnum=_safe_to_int(row["parent_message_number"]),
                confname=row["conference_name"],
                bbs_name=row["bbs_name"] or bbs_info.name,
                bbs_id=(row["bbs_id"] if "bbs_id" in row.keys() else None)
                or bbs_info.bbs_id,
                source_file=row["source_file"],
                attachments=attachments,
            )
            messages.append(msg)
    finally:
        conn.close()

    # If board_dict is empty, we reconstruct it from messages to keep compatibility
    if not board_dict:
        # Preserve existing bbs_info if it was loaded from a table.
        # We only restore it if it's not a default empty BBSInfo object.
        loaded_bbs_info = board_dict.bbs_info
        board_dict = _reconstruct_archive_information(messages)
        if loaded_bbs_info and loaded_bbs_info != BBSInfo():
            # Merge: prefer data loaded from SQLite tables, but fill gaps from reconstruction
            for field in fields(BBSInfo):
                if not getattr(loaded_bbs_info, field.name):
                    setattr(
                        loaded_bbs_info,
                        field.name,
                        getattr(board_dict.bbs_info, field.name),
                    )
            board_dict.bbs_info = loaded_bbs_info

    return messages, board_dict


def _parse_json_messages(
    data: list[dict[str, Any]] | dict[str, Any],
) -> list[ParsedMessage]:
    """Convert a list of dictionaries or a single dictionary into ParsedMessage objects.

    This function supports both a plain list of message objects and a structured
    dictionary containing metadata and a 'messages' list.
    """
    if isinstance(data, dict):
        if data.get("type") == "qwk_archive" and "messages" in data:
            data = data["messages"]
        elif data.get("type") == "metadata":
            return []
        else:
            data = [data]
    messages = []
    for entry in data:
        if not isinstance(entry, dict) or entry.get("type") == "metadata":
            continue
        header_dict = entry.get("header", {})
        header = MessageHeader.from_dict(header_dict)

        msg = ParsedMessage(
            text=entry.get("text", ""),
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=_safe_to_int(entry.get("depth", 0)) or 0,
            thread_id=entry.get("thread_id"),
            parent_msgnum=_safe_to_int(entry.get("parent_msgnum")),
            confname=entry.get("conference"),
            bbs_name=entry.get("bbs_name"),
            bbs_id=entry.get("bbs_id"),
            source_file=entry.get("source_file"),
            attachments=entry.get("attachments"),
        )
        messages.append(msg)
    return messages


def _safe_to_int(v: Any) -> int | None:
    """Safely convert a value to an integer, returning None on failure."""
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _parse_rfc_date_string(date_str: str) -> tuple[str, str]:
    """Parse an RFC 2822/5322 date-time string into a tuple of (date, time)."""
    dt = email.utils.parsedate_to_datetime(date_str)
    return dt.strftime("%m-%d-%y"), dt.strftime("%H:%M")


def _parse_rss_messages(root: ET.Element) -> list[ParsedMessage]:
    """Convert an RSS XML tree into ParsedMessage objects."""
    messages = []
    channel = root.find("channel")
    if channel is None:
        return messages

    # Global BBS info from channel title/description if available
    channel_title = channel.findtext("title") or ""
    if channel_title == "QWK Message Archive":
        bbs_name = ""
    else:
        bbs_name = (
            channel_title.removesuffix(" Archive")
            if channel_title.endswith(" Archive")
            else channel_title
        )

    for item in channel.findall("item"):
        title = item.findtext("title") or ""
        author = item.findtext("author") or ""
        pub_date_str = item.findtext("pubDate")
        guid = item.findtext("guid") or ""
        description = item.findtext("description") or ""
        category = item.findtext("category") or ""

        # Parse date
        msg_date = "01-01-70"
        msg_time = "00:00"
        if pub_date_str:
            try:
                msg_date, msg_time = _parse_rfc_date_string(pub_date_str)
            except (ValueError, TypeError):
                logging.getLogger("pyqwk.core").warning("Failed to parse RSS pubDate: %r", pub_date_str)

        # Parse GUID: {confnum}.{msgnum}@qwk
        confnum = 0
        msgnum = None
        if "@qwk" in guid:
            parts = guid.split("@")[0].split(".")
            if len(parts) == 2:
                confnum = _safe_to_int(parts[0]) or 0
                msgnum = _safe_to_int(parts[1])

        header = MessageHeader(
            status=" ",
            msgnum=msgnum,
            msgdate=msg_date,
            msgtime=msg_time,
            msgto="All",
            msgfrom=author,
            msgsubject=title,
            msgpassword="",
            refnum=None,
            numblocks=None,
            msgflag=" ",
            confnum=confnum,
            lognum=0,
            nettag=" ",
        )

        msg = ParsedMessage(
            text=description,
            msgnum=msgnum,
            refnum=None,
            confnum=confnum,
            header=header,
            confname=category or None,
            bbs_name=bbs_name or None,
        )
        messages.append(msg)
    return messages


def _parse_xml_messages(root: ET.Element) -> list[ParsedMessage]:
    """Convert an XML tree into ParsedMessage objects."""
    messages = []

    if root.tag == "message":
        entries = [root]
    else:
        entries = root.findall("message")

    for entry in entries:
        header_el = entry.find("header")
        header_dict = (
            {el.tag: el.text for el in header_el} if header_el is not None else {}
        )

        header = MessageHeader.from_dict(header_dict)

        attachments_el = entry.find("attachments")
        attachments = []
        if attachments_el is not None:
            for attach_el in attachments_el.findall("attachment"):
                if attach_el.text:
                    attachments.append(attach_el.text)

        msg = ParsedMessage(
            text=entry.findtext("text", default=""),
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=_safe_to_int(entry.findtext("depth")) or 0,
            thread_id=entry.findtext("thread_id") or None,
            parent_msgnum=_safe_to_int(entry.findtext("parent_msgnum")),
            confname=entry.findtext("conference_name")
            or entry.findtext("conference")
            or None,
            bbs_name=entry.findtext("bbs_name") or None,
            bbs_id=entry.findtext("bbs_id") or None,
            source_file=entry.findtext("source_file") or None,
            attachments=attachments or None,
        )
        messages.append(msg)
    return messages


def _parse_csv_messages(data: Iterator[dict[str, Any]]) -> list[ParsedMessage]:
    """Convert CSV rows into ParsedMessage objects."""
    messages = []

    for row in data:
        header = MessageHeader.from_dict(row)

        attachments = (
            row.get("attachments", "").split(";") if row.get("attachments") else None
        )

        msg = ParsedMessage(
            text=row.get("text", ""),
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=_safe_to_int(row.get("depth", 0)) or 0,
            thread_id=row.get("thread_id"),
            parent_msgnum=_safe_to_int(row.get("parent_msgnum")),
            confname=row.get("conference_name") or row.get("conference"),
            bbs_name=row.get("bbs_name"),
            bbs_id=row.get("bbs_id"),
            source_file=row.get("source_file"),
            attachments=attachments,
        )
        messages.append(msg)
    return messages


def _reconstruct_archive_information(messages: list[ParsedMessage]) -> ConferenceMap:
    """Reconstruct conference and BBS information from a list of messages."""
    board_dict = ConferenceMap()
    bbs_info = BBSInfo()
    for msg in messages:
        if msg.confnum is not None:
            default_name = f"Conference {msg.confnum}"
            if msg.confnum not in board_dict:
                board_dict[msg.confnum] = msg.confname or default_name
            elif msg.confname and board_dict[msg.confnum] == default_name:
                board_dict[msg.confnum] = msg.confname
        if msg.bbs_name:
            bbs_info.name = msg.bbs_name
        if msg.bbs_id:
            bbs_info.bbs_id = msg.bbs_id

    board_dict.bbs_info = bbs_info
    return board_dict


def _message_from_email(msg_obj: Any) -> ParsedMessage:
    """Convert an email message object to a ParsedMessage."""

    # Extract headers
    def get_hdr(name: str) -> str:
        return str(msg_obj.get(name, ""))

    # QWK specific headers (if they exist)
    conf_num = _safe_to_int(get_hdr("X-QWK-Conference")) or 0
    msg_num = _safe_to_int(get_hdr("X-QWK-Message-Number"))
    ref_num = _safe_to_int(get_hdr("X-QWK-Reference"))
    status = get_hdr("X-QWK-Status") or " "
    msg_flag = get_hdr("X-QWK-Flags") or " "
    conf_name = get_hdr("X-QWK-Conference-Name")
    bbs_name = get_hdr("X-QWK-BBS-Name")
    bbs_id = get_hdr("X-QWK-BBS-ID")
    source_file = get_hdr("X-QWK-Source-File")

    # Attachments
    attachments = None
    attach_hdr = get_hdr("X-QWK-Attachments")
    if attach_hdr:
        attachments = [a.strip() for a in attach_hdr.split(";") if a.strip()]

    # Standard Email headers
    msg_to = get_hdr("To")
    msg_from = get_hdr("From")
    msg_subject = get_hdr("Subject")

    # Date/Time
    msg_date = "01-01-70"
    msg_time = "00:00"
    date_hdr = get_hdr("Date")
    if date_hdr:
        try:
            msg_date, msg_time = _parse_rfc_date_string(date_hdr)
        except (ValueError, TypeError):
            pass

    # Message body and MIME attachments
    body = ""
    uue_blocks = []
    if msg_obj.is_multipart():
        for part in msg_obj.walk():
            content_type = part.get_content_type()
            filename = part.get_filename()
            payload = part.get_payload(decode=True)

            if payload:
                # Capture the first plain text part as the main body
                if content_type == "text/plain" and not filename and not body:
                    body = payload.decode("utf-8", errors="replace")
                else:
                    # Convert other MIME parts into UUE blocks appended to the body
                    # This ensures compatibility with pyqwk's internal attachment pipeline
                    fname = filename or f"attachment_{len(uue_blocks) + 1}.bin"
                    uue_blocks.append(_bytes_to_uue(payload, fname))
    else:
        payload = msg_obj.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    if uue_blocks:
        if body and not body.endswith("\n"):
            body += "\n"
        body += "\n" + "\n".join(uue_blocks)

    # Construct MessageHeader
    header = MessageHeader(
        status=status[:1] if status else " ",
        msgnum=msg_num,
        msgdate=msg_date,
        msgtime=msg_time,
        msgto=msg_to,
        msgfrom=msg_from,
        msgsubject=msg_subject,
        msgpassword="",
        refnum=ref_num,
        numblocks=None,
        msgflag=msg_flag[:1] if msg_flag else " ",
        confnum=conf_num,
        lognum=0,
        nettag="",
    )

    return ParsedMessage(
        text=body,
        msgnum=msg_num,
        refnum=ref_num,
        confnum=conf_num,
        header=header,
        depth=_safe_to_int(get_hdr("X-QWK-Depth") or 0) or 0,
        thread_id=get_hdr("X-QWK-Thread-ID") or None,
        parent_msgnum=_safe_to_int(get_hdr("X-QWK-Parent-Msgnum")),
        confname=conf_name or None,
        bbs_name=bbs_name or None,
        bbs_id=bbs_id or None,
        source_file=source_file or None,
        attachments=attachments,
        reply_count=_safe_to_int(get_hdr("X-QWK-Reply-Count") or 0) or 0,
        thread_size=_safe_to_int(get_hdr("X-QWK-Thread-Size") or 1) or 1,
    )






def _parse_html_messages(path: str) -> list[ParsedMessage]:
    """Import messages from an HTML file."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    messages = []

    # Identify message blocks
    msg_blocks = list(
        re.finditer(r'<div class="message"(?: id="[^"]*")?>', content, re.IGNORECASE)
    )

    # Pre-calculate depths for all message starts in a single pass
    div_tags = list(re.finditer(r"<(div|/div)\b([^>]*)>", content, re.IGNORECASE))
    msg_depths = {}
    current_depth = 0
    stack = []
    div_idx = 0

    for block in msg_blocks:
        start = block.start()
        # Advance div_idx and update depth until we reach the current message block
        while div_idx < len(div_tags) and div_tags[div_idx].start() < start:
            m_tag = div_tags[div_idx]
            tag_name = m_tag.group(1).lower()
            attrs = m_tag.group(2).lower()
            if tag_name == "div":
                if 'class="reply"' in attrs:
                    stack.append("reply")
                    current_depth += 1
                else:
                    stack.append("other")
            else:  # tag_name == "/div"
                if stack:
                    if stack.pop() == "reply":
                        current_depth -= 1
            div_idx += 1
        msg_depths[start] = max(0, current_depth)

    re_date = re.compile(r"<strong>Date:</strong>\s*(.*?)\s*</div>", re.IGNORECASE)
    re_from = re.compile(r"<strong>From:</strong>\s*(.*?)\s*</div>", re.IGNORECASE)
    re_to = re.compile(r"<strong>To:</strong>\s*(.*?)\s*</div>", re.IGNORECASE)
    re_subject = re.compile(
        r"<strong>Subject:</strong>\s*(.*?)\s*</div>", re.IGNORECASE
    )
    re_conf = re.compile(
        r"<strong>Conference:</strong>\s*(.*?)\s*\((\d+)\)\s*</div>", re.IGNORECASE
    )
    re_bbs = re.compile(r"<strong>BBS:</strong>\s*(.*?)\s*</div>", re.IGNORECASE)
    re_source = re.compile(r"<strong>Source:</strong>\s*(.*?)\s*</div>", re.IGNORECASE)
    re_number = re.compile(r"<strong>Number:</strong>\s*(\d+)\s*</div>", re.IGNORECASE)
    re_attachments = re.compile(
        r"<strong>Attachments:</strong>\s*(.*?)\s*</div>", re.IGNORECASE
    )
    re_body = re.compile(r'<pre class="body">(.*?)</pre>', re.DOTALL | re.IGNORECASE)

    def clean_html(text: str) -> str:
        # Remove tags like <mark>, </mark>, <span class="quote">, </span>, and <a> tags
        text = re.sub(r"<[^>]+>", "", text)
        return html.unescape(text).strip()

    for i, match in enumerate(msg_blocks):
        start = match.start()
        end = msg_blocks[i + 1].start() if i + 1 < len(msg_blocks) else len(content)
        block = content[start:end]

        depth = msg_depths.get(start, 0)
        header_match = re.search(r'<div class="header">(.*?)\s*<pre', block, re.DOTALL)
        header_part = header_match.group(1) if header_match else block

        date_match = re_date.search(header_part)
        from_match = re_from.search(header_part)
        to_match = re_to.search(header_part)
        subject_match = re_subject.search(header_part)
        conf_match = re_conf.search(header_part)
        bbs_match = re_bbs.search(header_part)
        source_match = re_source.search(header_part)
        number_match = re_number.search(header_part)
        attach_match = re_attachments.search(header_part)

        msg_date = "01-01-70"
        msg_time = "00:00"
        if date_match:
            dt_parts = clean_html(date_match.group(1)).split()
            if len(dt_parts) >= 1:
                msg_date = dt_parts[0]
            if len(dt_parts) >= 2:
                msg_time = dt_parts[1]

        conf_num = 0
        conf_name = None
        if conf_match:
            conf_name = clean_html(conf_match.group(1))
            conf_num = int(conf_match.group(2))

        attachments = None
        if attach_match:
            attachments = [
                clean_html(a) for a in attach_match.group(1).split(",") if clean_html(a)
            ]
            if not attachments:
                attachments = None

        body = ""
        body_match = re_body.search(block)
        if body_match:
            body = clean_html(body_match.group(1))

        header = MessageHeader(
            status=" ",
            msgnum=int(number_match.group(1)) if number_match else None,
            msgdate=msg_date,
            msgtime=msg_time,
            msgto=clean_html(to_match.group(1)) if to_match else "",
            msgfrom=clean_html(from_match.group(1)) if from_match else "",
            msgsubject=clean_html(subject_match.group(1))
            if subject_match
            else "(no subject)",
            msgpassword="",
            refnum=None,
            numblocks=None,
            msgflag=" ",
            confnum=conf_num,
            lognum=0,
            nettag="",
        )

        msg = ParsedMessage(
            text=body,
            msgnum=header.msgnum,
            refnum=None,
            confnum=conf_num,
            header=header,
            depth=depth,
            confname=conf_name,
            bbs_name=clean_html(bbs_match.group(1)) if bbs_match else None,
            source_file=clean_html(source_match.group(1)) if source_match else None,
            attachments=attachments,
        )
        messages.append(msg)

    return messages


def _parse_text_messages(path: str, encoding: str = "utf-8") -> list[ParsedMessage]:
    """Import messages from a Plain Text file."""
    try:
        with open(path, "r", encoding=encoding) as f:
            content = f.read()
    except (UnicodeDecodeError, LookupError):
        with open(path, "r", encoding="latin1") as f:
            content = f.read()

    # Split by horizontal separators (dashes) or double newlines
    content_norm = content.replace("\r\n", "\n")
    sections = re.split(r"\n-{20,}\n", content_norm)
    if len(sections) <= 1:
        # Try splitting by double newlines if no dashes found, looking ahead for headers
        sections = re.split(r"\n\n(?=Conference:|Area:|Message #:|Date:)", content_norm)

    messages = []

    re_conf = re.compile(
        r"^\s*(?:Conference|Area):[ \t]*(.*?)(?:[ \t]*\((\d+)\))?$", re.MULTILINE
    )
    re_bbs = re.compile(r"^\s*BBS:[ \t]*(.*)$", re.MULTILINE)
    re_status = re.compile(r"^\s*Status:[ \t]*(.*)$", re.MULTILINE)
    re_msgnum_verbose = re.compile(r"^\s*Message #:[ \t]*(\d+)", re.MULTILINE)
    re_date = re.compile(r"^\s*Date:[ \t]*(.*)$", re.MULTILINE)
    re_from = re.compile(r"^\s*From:[ \t]*(.*)$", re.MULTILINE)
    re_to = re.compile(r"^\s*To:[ \t]*(.*)$", re.MULTILINE)
    re_subject = re.compile(r"^\s*Subject:[ \t]*(.*)$", re.MULTILINE)
    re_refnum = re.compile(r"^\s*(?:Reference #|Ref #):[ \t]*(\d+)", re.MULTILINE)
    re_attachments = re.compile(r"^\s*Attachments:[ \t]*(.*)$", re.MULTILINE)
    re_any_header = re.compile(
        r"^\s*(Conference|Area|BBS|Status|Message #|Date|From|To|Subject|Reference #|Ref #|Attachments):"
    )

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Skip horizontal separator if it's the first line after strip()
        lines = section.split("\n")
        if lines and re.match(r"^-{20,}$", lines[0].strip()):
            lines = lines[1:]

        # Separate headers from body to avoid fake headers in body being matched
        header_lines = []
        body_idx = 0
        for i, line in enumerate(lines):
            if re_any_header.match(line):
                header_lines.append(line)
                body_idx = i + 1
            elif not line.strip() and not header_lines:
                # Skip leading empty lines before any headers
                body_idx = i + 1
                continue
            else:
                # First non-header line (or empty line) marks end of headers
                break

        header_part = "\n".join(header_lines)
        body = "\n".join(lines[body_idx:]).strip()

        from_match = re_from.search(header_part)
        to_match = re_to.search(header_part)
        subj_match = re_subject.search(header_part)

        # Minimum required headers to consider it a message
        if not (from_match and to_match and subj_match):
            continue

        conf_match = re_conf.search(header_part)
        bbs_match = re_bbs.search(header_part)
        status_match = re_status.search(header_part)
        msgnum_v_match = re_msgnum_verbose.search(header_part)
        date_match = re_date.search(header_part)
        ref_match = re_refnum.search(header_part)
        attach_match = re_attachments.search(header_part)

        msgnum = None
        if msgnum_v_match:
            msgnum = int(msgnum_v_match.group(1))
        date_str = date_match.group(1) if date_match else ""

        msg_date = "01-01-70"
        msg_time = "00:00"
        if date_str:
            parts = date_str.split()
            if len(parts) >= 1:
                msg_date = parts[0]
            if len(parts) >= 2:
                msg_time = parts[1]

        refnum = None
        if ref_match:
            refnum = int(ref_match.group(1))

        attachments = None
        if attach_match:
            attachments = [
                a.strip() for a in attach_match.group(1).split(",") if a.strip()
            ]

        conf_num = 0
        conf_name = None
        if conf_match:
            conf_name = conf_match.group(1).strip()
            if conf_match.group(2):
                conf_num = int(conf_match.group(2))

        header = MessageHeader(
            status="*"
            if status_match and "[PRIVATE]" in status_match.group(1)
            else " ",
            msgnum=msgnum,
            msgdate=msg_date,
            msgtime=msg_time,
            msgto=to_match.group(1).strip(),
            msgfrom=from_match.group(1).strip(),
            msgsubject=subj_match.group(1).strip(),
            msgpassword="",
            refnum=refnum,
            numblocks=None,
            msgflag=" ",
            confnum=conf_num,
            lognum=0,
            nettag="",
        )

        msg = ParsedMessage(
            text=body,
            msgnum=msgnum,
            refnum=refnum,
            confnum=conf_num,
            header=header,
            confname=conf_name,
            bbs_name=bbs_match.group(1).strip() if bbs_match else None,
            attachments=attachments,
        )
        messages.append(msg)

    return messages


def _parse_markdown_messages(path: str) -> list[ParsedMessage]:
    """Import messages from a Markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into sections by horizontal rules '---'
    raw_sections = re.split(r"\n---\n", content)
    sections = []
    current_chunk = ""
    for s in raw_sections:
        # A new message section contains '## ' or '> ## '
        if "## " in s:
            if current_chunk:
                sections.append(current_chunk)
            current_chunk = s
        else:
            if current_chunk:
                current_chunk += "\n---\n" + s
            else:
                # Header of the file before any message
                continue
    if current_chunk:
        sections.append(current_chunk)

    messages = []

    # Regex patterns for fields
    re_subject = re.compile(r"^## (.*)", re.MULTILINE)
    re_date = re.compile(r"^- \*\*Date:\*\* (.*)", re.MULTILINE)
    re_from = re.compile(r"^- \*\*From:\*\* (.*)", re.MULTILINE)
    re_to = re.compile(r"^- \*\*To:\*\* (.*)", re.MULTILINE)
    re_conf = re.compile(r"^- \*\*Conference:\*\* (.*) \((\d+)\)", re.MULTILINE)
    re_bbs = re.compile(r"^- \*\*BBS:\*\* (.*)", re.MULTILINE)
    re_source = re.compile(r"^- \*\*Source:\*\* (.*)", re.MULTILINE)
    re_number = re.compile(r"^- \*\*Number:\*\* (.*)", re.MULTILINE)
    re_attachments = re.compile(r"^- \*\*Attachments:\*\* (.*)", re.MULTILINE)

    for section in sections:
        # Detect blockquote depth for threaded Markdown
        depth = 0
        working_section = section.lstrip("\n")
        while working_section.startswith(">"):
            depth += 1
            lines = working_section.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith("> "):
                    new_lines.append(line[2:])
                elif line.startswith(">"):
                    new_lines.append(line[1:])
                elif not line.strip():
                    new_lines.append("")
                else:
                    new_lines.append(line)
            working_section = "\n".join(new_lines).strip()

        # If it's the first section, it might start with the archive title (# )
        msg_start = working_section.find("## ")
        if msg_start == -1:
            continue

        working_section = working_section[msg_start:]

        # Extract message information
        subject_match = re_subject.search(working_section)
        if not subject_match:
            continue

        subject = subject_match.group(1).strip().replace("**", "")
        # Remove HTML anchors from subject for round-trip compatibility
        subject = re.sub(r"\s*<a name=\".*?\"></a>", "", subject)
        date_match = re_date.search(working_section)
        from_match = re_from.search(working_section)
        to_match = re_to.search(working_section)
        conf_match = re_conf.search(working_section)
        bbs_match = re_bbs.search(working_section)
        source_match = re_source.search(working_section)
        num_match = re_number.search(working_section)
        attach_match = re_attachments.search(working_section)

        # Date and Time
        msg_date = "01-01-70"
        msg_time = "00:00"
        if date_match:
            dt_parts = date_match.group(1).split()
            if len(dt_parts) >= 1:
                msg_date = dt_parts[0]
            if len(dt_parts) >= 2:
                msg_time = dt_parts[1]

        # Conference
        conf_num = 0
        conf_name = None
        if conf_match:
            conf_name = conf_match.group(1).strip().replace("**", "")
            conf_num = int(conf_match.group(2))

        # BBS info
        bbs_name = bbs_match.group(1).strip().replace("**", "") if bbs_match else None
        source_file = (
            source_match.group(1).strip().replace("**", "") if source_match else None
        )
        msg_num = _safe_to_int(num_match.group(1).strip()) if num_match else None

        attachments = None
        if attach_match:
            attach_str = attach_match.group(1).strip()
            if "[" in attach_str:
                attachments = re.findall(r"\[(.*?)\]", attach_str)
            else:
                attachments = [a.strip() for a in attach_str.split(",") if a.strip()]
            if not attachments:
                attachments = None

        # Message body: everything after the information lines
        # In our Markdown format, the information section ends at the first blank line.
        lines = working_section.splitlines()
        body_start_idx = 0
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if not line_strip:
                body_start_idx = i + 1
                break
            if line_strip.startswith("## ") or line_strip.startswith("- **"):
                body_start_idx = i + 1
            else:
                body_start_idx = i
                break

        body = "\n".join(lines[body_start_idx:]).strip()

        # Clean Markdown links from body for round-trip compatibility
        body = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", body)

        # Construct MessageHeader
        header = MessageHeader(
            status=" ",
            msgnum=msg_num,
            msgdate=msg_date,
            msgtime=msg_time,
            msgto=to_match.group(1).strip().replace("**", "") if to_match else "",
            msgfrom=from_match.group(1).strip().replace("**", "") if from_match else "",
            msgsubject=subject,
            msgpassword="",
            refnum=None,
            numblocks=None,
            msgflag=" ",
            confnum=conf_num,
            lognum=0,
            nettag="",
        )

        msg = ParsedMessage(
            text=body,
            msgnum=msg_num,
            refnum=None,
            confnum=conf_num,
            header=header,
            depth=depth,
            confname=conf_name,
            bbs_name=bbs_name,
            source_file=source_file,
            attachments=attachments,
        )
        messages.append(msg)

    return messages


def _process_batch_candidate_paths(
    candidate_paths: list[str],
    logger: logging.Logger,
    encoding: str,
    archive_type: str,
) -> tuple[list[ParsedMessage], ConferenceMap]:
    """Process and merge messages from a list of candidate file paths."""
    all_messages = []
    merged_board_dict = ConferenceMap()

    for p in candidate_paths:
        try:
            # Recursive load_data for each file found
            data, b_dict = load_data(p, logger, encoding)

            # Merge conference map and BBS information
            if b_dict.bbs_info:
                if not merged_board_dict.bbs_info:
                    merged_board_dict.bbs_info = b_dict.bbs_info
                elif b_dict.bbs_info.name and not merged_board_dict.bbs_info.name:
                    merged_board_dict.bbs_info = b_dict.bbs_info

            for cid, name in b_dict.items():
                if cid not in merged_board_dict:
                    merged_board_dict[cid] = name

            # Consolidate messages
            if isinstance(data, bytearray):
                # For QWK/REP, we must parse the bytes using the conference map from its own source
                msgs = list(parse_messages(data, None, encoding))
                # Attach conference names since we are merging into a shared board_dict
                for m in msgs:
                    m.confname = b_dict.get(m.confnum)
                all_messages.extend(msgs)
            else:
                all_messages.extend(data)
        except Exception as e:
            logger.warning(
                "Skipping file %s in %s due to error: %s",
                os.path.basename(p),
                archive_type,
                e,
            )

    return all_messages, merged_board_dict


def load_data(
    input_path: str, logger: logging.Logger, encoding: str = "cp437"
) -> tuple[bytearray | list[ParsedMessage], ConferenceMap]:
    """Load message data and conference mappings from an archive file.

    This function handles both older formats (QWK, REP) and modern
    formats (JSON, JSONL, SQLite, XML, RSS, CSV, mbox, EML, Markdown, HTML, Plain Text).

    Args:
        input_path: Path to the archive file or an original 'MESSAGES.DAT' file.
        logger: Logger for reporting warnings and informational messages.
        encoding: The text encoding used to decode text (default is 'cp437').

    Returns:
        A pair of values (file_data, board_dict):
        - file_data: The original bytes for QWK/REP files, or
          a list of 'ParsedMessage' objects for modern formats.
        - board_dict: A 'ConferenceMap' linking conference numbers to names,
          which may also include BBS information.

        Note: When loading an original 'MESSAGES.DAT' file, it automatically searches
        for a corresponding 'CONTROL.DAT' in the same folder to load conference names.
    """
    board_dict = ConferenceMap()

    if input_path.lower().endswith((".db", ".sqlite")) or input_path == ":memory:":
        try:
            messages, board_dict = _parse_sqlite_messages(input_path)
        except (ValueError, sqlite3.Error) as e:
            raise ValueError(f"Failed to load SQLite archive: {e}")

        return messages, board_dict

    if input_path.lower().endswith(".json"):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            messages = _parse_json_messages(data)

            if isinstance(data, dict) and data.get("type") == "qwk_archive":
                board_dict = ConferenceMap()
                if data.get("bbs_info"):
                    board_dict.bbs_info = BBSInfo(**data["bbs_info"])
                if data.get("conferences"):
                    for k, v in data["conferences"].items():
                        board_dict[int(k)] = v
            else:
                board_dict = _reconstruct_archive_information(messages)
            return messages, board_dict

    if input_path.lower().endswith(".jsonl"):
        messages = []
        board_dict = ConferenceMap()
        has_metadata = False
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if isinstance(data, dict) and data.get("type") == "metadata":
                        has_metadata = True
                        if data.get("bbs_info"):
                            board_dict.bbs_info = BBSInfo(**data["bbs_info"])
                        if data.get("conferences"):
                            for k, v in data["conferences"].items():
                                board_dict[int(k)] = v
                    else:
                        messages.extend(_parse_json_messages(data))

        if not has_metadata:
            board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    messages = None

    if _is_maildir(input_path) or input_path.lower().endswith((".maildir", ".mdir")):
        try:
            messages = []
            mdir = mailbox.Maildir(input_path)
            for msg_obj in mdir:
                messages.append(_message_from_email(msg_obj))
            mdir.close()
        except Exception as e:
            raise ValueError(f"Failed to load Maildir: {e}")

    elif input_path.lower().endswith((".html", ".htm")):
        try:
            messages = _parse_html_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load HTML archive: {e}")

    elif input_path.lower().endswith(".mbox"):
        try:
            messages = []
            mbox = mailbox.mbox(input_path)
            for msg_obj in mbox:
                messages.append(_message_from_email(msg_obj))
            mbox.close()
        except Exception as e:
            raise ValueError(f"Failed to load mbox archive: {e}")

    elif input_path.lower().endswith((".md", ".markdown")):
        try:
            messages = _parse_markdown_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load Markdown archive: {e}")

    elif input_path.lower().endswith(".eml"):
        try:
            with open(input_path, "rb") as f:
                msg_obj = email.message_from_binary_file(f)
            messages = [_message_from_email(msg_obj)]
        except Exception as e:
            raise ValueError(f"Failed to load EML file: {e}")

    elif input_path.lower().endswith((".xml", ".rss")):
        try:
            tree = ET.parse(input_path)
            root = tree.getroot()
            if input_path.lower().endswith(".rss") or root.tag == "rss":
                messages = _parse_rss_messages(root)
            else:
                messages = _parse_xml_messages(root)
        except Exception as e:
            raise ValueError(f"Failed to load XML archive: {e}")

    elif input_path.lower().endswith(".csv"):
        with open(input_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            messages = _parse_csv_messages(reader)

    elif input_path.lower().endswith(".txt"):
        try:
            messages = _parse_text_messages(input_path, encoding)
        except Exception as e:
            raise ValueError(f"Failed to load text archive: {e}")

    if messages is not None:
        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if zipfile.is_zipfile(input_path):
        # Support multi-format batch loading from ZIP archives.
        # We extract the ZIP to a temporary directory and process all supported files found within.
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(input_path) as myzip:
                    file_list = myzip.namelist()

                    # Classic QWK check: contains MESSAGES.DAT or REPLY.DAT at the top level
                    messages_dat = next(
                        (n for n in file_list if n.lower() == MESSAGES_FILENAME), None
                    )
                    reply_dat = next(
                        (n for n in file_list if n.lower() == REPLY_FILENAME), None
                    )

                    if (messages_dat or reply_dat) and len(file_list) <= 12:
                        # Extract only what we need for classic packets
                        myzip.extractall(temp_dir)
                        target = os.path.join(temp_dir, messages_dat or reply_dat)

                        with open(target, "rb") as f:
                            file_data = bytearray(f.read())

                        board_dict = ConferenceMap()
                        control_name = next(
                            (n for n in file_list if n.lower() == CONTROL_FILENAME),
                            None,
                        )
                        if control_name:
                            with myzip.open(control_name) as f:
                                control_data = f.read().splitlines()
                            board_dict = _parse_control_dat(
                                control_data, logger, encoding
                            )
                        elif messages_dat:
                            logger.warning("CONTROL.DAT not found in the zip archive.")
                        return file_data, board_dict

                    # If not a simple QWK packet, extract everything for batch processing
                    myzip.extractall(temp_dir)

            except (RuntimeError, NotImplementedError, zipfile.BadZipFile) as e:
                # Fallback to system 'unzip' if built-in zipfile fails (e.g., unsupported compression)
                logger.info(
                    "Built-in zipfile failed (%s); attempting fallback to system 'unzip'.",
                    str(e),
                )
                abs_input_path = os.path.abspath(input_path)
                try:
                    # We try to extract and then check if it's a standard QWK
                    result = subprocess.run(
                        ["unzip", "-o", abs_input_path],
                        cwd=temp_dir,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode not in (0, 1):
                        error_msg = f"unzip failed with return code {result.returncode}: {result.stderr}"
                        if os.name == "nt" and result.returncode == 127:
                            error_msg += "\nTip: On Windows, run 'winget install GnuWin32.UnZip' or install 'unzip.exe' via Git Bash."
                        raise RuntimeError(error_msg)

                    # Check if standard QWK after unzip
                    extracted_files = os.listdir(temp_dir)
                    messages_dat = next(
                        (f for f in extracted_files if f.lower() == MESSAGES_FILENAME),
                        None,
                    )
                    reply_dat = next(
                        (f for f in extracted_files if f.lower() == REPLY_FILENAME),
                        None,
                    )

                    if (messages_dat or reply_dat) and len(extracted_files) <= 12:
                        target = os.path.join(temp_dir, messages_dat or reply_dat)
                        with open(target, "rb") as f:
                            file_data = bytearray(f.read())

                        board_dict = ConferenceMap()
                        control_dat = next(
                            (
                                f
                                for f in extracted_files
                                if f.lower() == CONTROL_FILENAME
                            ),
                            None,
                        )
                        if control_dat:
                            with open(os.path.join(temp_dir, control_dat), "rb") as f:
                                control_lines = f.read().splitlines()
                            board_dict = _parse_control_dat(
                                control_lines, logger, encoding
                            )
                        elif messages_dat:
                            logger.warning("CONTROL.DAT not found in the zip archive.")
                        return file_data, board_dict
                except Exception as final_e:
                    error_msg = f"An error occurred while handling older ZIP archive: {str(final_e)}"
                    if os.name == "nt" and "[WinError 2]" in str(final_e):
                        error_msg += (
                            "\nTip: On Windows, install 'unzip' via winget or Git Bash."
                        )
                    raise RuntimeError(error_msg) from final_e

            # Perform a recursive search for all supported formats in the extracted content.
            candidate_paths = expand_paths([temp_dir])

            if not candidate_paths:
                # Classic error message for empty/unsupported ZIPs to satisfy existing tests
                raise FileNotFoundError(
                    f"Error: Neither '{MESSAGES_FILENAME}' nor '{REPLY_FILENAME}' found in the zip archive {input_path}."
                )

            all_messages, merged_board_dict = _process_batch_candidate_paths(
                candidate_paths, logger, encoding, "ZIP"
            )

            if not all_messages:
                raise ValueError(
                    f"No messages could be loaded from ZIP archive: {input_path}"
                )

            return all_messages, merged_board_dict
    elif tarfile.is_tarfile(input_path) if os.path.isfile(input_path) else False:
        # Support multi-format batch loading from TAR archives.
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with tarfile.open(input_path) as mytar:
                    # In Python 3.12+, we should use the 'data' filter for safety
                    if hasattr(tarfile, "data_filter"):
                        mytar.extractall(temp_dir, filter="data")
                    else:
                        mytar.extractall(temp_dir)
            except Exception as e:
                raise RuntimeError(
                    f"An error occurred while extracting TAR archive: {str(e)}"
                )

            candidate_paths = expand_paths([temp_dir])

            if not candidate_paths:
                raise ValueError(
                    f"No supported message files found in TAR archive: {input_path}"
                )

            all_messages, merged_board_dict = _process_batch_candidate_paths(
                candidate_paths, logger, encoding, "TAR"
            )

            if not all_messages:
                raise ValueError(
                    f"No messages could be loaded from TAR archive: {input_path}"
                )

            return all_messages, merged_board_dict
    else:
        with open(input_path, "rb") as f:
            file_data = bytearray(f.read())

        # If the file is MESSAGES.DAT, look for an accompanying CONTROL.DAT in the same folder
        if os.path.basename(input_path).lower() == MESSAGES_FILENAME:
            parent_dir = os.path.dirname(input_path)
            control_path = os.path.join(parent_dir, CONTROL_FILENAME)

            # Check for case-insensitive CONTROL.DAT
            if not os.path.exists(control_path):
                # Try all files in the directory to find a match
                if os.path.isdir(parent_dir or "."):
                    for filename in os.listdir(parent_dir or "."):
                        if filename.lower() == CONTROL_FILENAME:
                            control_path = os.path.join(parent_dir, filename)
                            break

            if os.path.exists(control_path) and not os.path.isdir(control_path):
                try:
                    with open(control_path, "rb") as f:
                        control_data = f.read().splitlines()
                    board_dict = _parse_control_dat(control_data, logger, encoding)
                    logger.info(
                        "Found accompanying %s; loaded conference names.",
                        os.path.basename(control_path),
                    )
                except Exception as e:
                    logger.warning(
                        "Found accompanying CONTROL.DAT but failed to parse it: %s",
                        str(e),
                    )

    return file_data, board_dict


def _parse_control_dat(
    control_data: list[bytes],
    logger: logging.Logger | None = None,
    encoding: str = "cp437",
) -> ConferenceMap:
    if logger is None:
        logger = logging.getLogger(__name__)

    if len(control_data) < 11:
        raise ControlDatFormatError(
            "CONTROL.DAT is too short; header information missing."
        )

    bbs_info = BBSInfo()

    def dec(b):
        try:
            return b.decode(encoding).strip()
        except UnicodeDecodeError:
            return b.decode("latin1").strip()

    bbs_info.name = dec(control_data[0])
    bbs_info.location = dec(control_data[1])
    bbs_info.phone = dec(control_data[2])
    bbs_info.sysop = dec(control_data[3])

    line5 = dec(control_data[4]).split(",", 1)
    bbs_info.serial_number = line5[0].strip()
    if len(line5) > 1:
        bbs_info.bbs_id = line5[1].strip()

    bbs_info.packet_at = dec(control_data[5])
    bbs_info.user_name = dec(control_data[6])

    try:
        num_conferences = int(control_data[10]) + 1
    except ValueError as error:
        raise ControlDatFormatError(
            f"Invalid conference count in CONTROL.DAT: {control_data[10]!r}"
        ) from error

    bbs_info.num_conferences = num_conferences

    board_dict = ConferenceMap()
    board_dict.bbs_info = bbs_info

    for i in range(num_conferences):
        index = 11 + i * 2
        try:
            conf_number_raw = control_data[index]
            conf_name_raw = control_data[index + 1]
        except IndexError:
            available_entries = max((len(control_data) - 11) // 2, 0)
            logger.warning(
                "CONTROL.DAT is truncated; missing conference entry %d "
                "(expected %d entries, found %d).",
                i,
                num_conferences,
                available_entries,
            )
            break
        try:
            conf_number = int(conf_number_raw)
        except ValueError:
            logger.warning(
                "Invalid conference number in CONTROL.DAT: %r; skipping entry.",
                conf_number_raw,
            )
            continue
        board_dict[conf_number] = dec(conf_name_raw)

    return board_dict


def parse_messages(
    file_data: bytearray,
    progress_bar: ProgressBar | None,
    encoding: str = "cp437",
    headers_only: bool = False,
) -> Iterator[ParsedMessage]:
    """Convert the original bytes from a QWK message file into a list of messages.

    Args:
        file_data: Original bytes from a messages.dat file.
        progress_bar: Optional progress reporter to update as blocks are read.
        encoding: The text format to use when reading messages.
        headers_only: If True, skips reading the message body content.

    Yields:
        ParsedMessage instances containing the message body, header, and information flags.

    Raises:
        MessagesDatFormatError: If the data does not start with a valid messages.dat header.
        InvalidMessageTypeError: If a message header encodes an unknown message type.
    """
    blocks_remaining = 0
    message_buffer = ""
    header: MessageHeader | None = None

    if len(file_data) < BLOCK_SIZE:
        raise MessagesDatFormatError(
            "Input too short to contain a valid messages.dat header block."
        )

    first_record = file_data[0:BLOCK_SIZE]
    if progress_bar is not None:
        progress_bar.update(len(first_record))

    # QWK packets (MESSAGES.DAT) start with 'Produced '.
    # REP packets (REPLY.DAT) start with the BBS ID.
    # We relax the check to allow REPLY.DAT as long as it has at least one record.
    # We still check for 'Produced ' as a basic check for MESSAGES.DAT,
    # but we also accept files that don't have it if they seem like valid record-based files.
    # For now, we'll just ensure it's not obviously wrong.
    # Most REPLY.DAT files just start with the BBS ID in the first 128-byte block.

    for i in range(BLOCK_SIZE, len(file_data), BLOCK_SIZE):
        record = file_data[i : i + BLOCK_SIZE]
        if progress_bar is not None:
            progress_bar.update(len(record))
        if blocks_remaining == 0:
            try:
                header = MessageHeader.from_bytes(record, encoding)
            except (MessagesDatFormatError, InvalidMessageTypeError):
                # If the header is invalid, we skip this block and try the next one as a header.
                logging.warning(
                    "Invalid message header at offset %s; skipping block.",
                    i,
                )
                continue

            message_buffer = ""
            if header.numblocks is None or header.numblocks < 1:
                logging.warning(
                    "Invalid block count '%s' in message header at offset %s; skipping message.",
                    getattr(header, "_numblocks_raw", header.numblocks),
                    i,
                )
                continue

            blocks_remaining = header.numblocks - 1
            if blocks_remaining == 0:
                yield ParsedMessage(
                    text="",
                    msgnum=header.msgnum,
                    refnum=header.refnum,
                    confnum=header.confnum,
                    header=header,
                )
        else:
            if not headers_only:
                temp_record = record.replace(b"\xe3", b"\r\n").decode(encoding)
                if blocks_remaining == 1:
                    temp_record = temp_record.rstrip() + "\r\n"
                message_buffer += temp_record

            blocks_remaining = blocks_remaining - 1
            if blocks_remaining == 0 and header is not None:
                yield ParsedMessage(
                    text=message_buffer,
                    msgnum=header.msgnum,
                    refnum=header.refnum,
                    confnum=header.confnum,
                    header=header,
                )

    if blocks_remaining != 0:
        raise MessagesDatFormatError(
            "messages.dat is truncated; expected more blocks for current message."
        )


def _redact_pii(text: str) -> str:
    """Hide email addresses and phone numbers in text."""
    if not text:
        return text
    text = RE_EMAIL_PATTERN.sub("[EMAIL]", text)
    text = RE_PHONE_PATTERN.sub("[PHONE]", text)
    return text


def process_message(
    message_buffer: str,
    truncate_signatures: bool,
    cut_quoting: bool,
    binaries_removal: bool,
    redact_pii: bool,
    strip_ansi: bool = False,
) -> str:
    """Clean up and format a message body.

    Args:
        message_buffer: The original message text.
        truncate_signatures: If True, stop reading when a signature is found.
        cut_quoting: If True, remove quoted text from earlier messages.
        binaries_removal: If True, remove attachments (like images) from the text.
        redact_pii: If True, hide personal information like email addresses.
        strip_ansi: If True, remove color codes and other symbols from the text.

    Returns:
        The cleaned message text.
    """
    message_buffer = message_buffer.lstrip("\r\n").rstrip()
    lines = message_buffer.splitlines()

    new_lines = []
    in_yenc_block = False
    in_uue_block = False
    in_base64_block = False
    previous_line: str | None = None
    for j, line in enumerate(lines):
        if truncate_signatures and (
            line in SIGNATURE_PATTERNS_EXACT
            or line.startswith(SIGNATURE_PATTERNS_STARTSWITH)
        ):
            break
        if cut_quoting:
            if RE_QUOTE_PATTERN.match(line):
                continue
            # Remove lines between two quoted lines to handle quotes that were broken
            # across lines by the original BBS software.
            elif (
                j > 0
                and j < (len(lines) - 1)
                and RE_QUOTE_PATTERN.match(lines[j - 1])
                and RE_QUOTE_PATTERN.match(lines[j + 1])
            ):
                continue
        if binaries_removal:
            should_skip, in_yenc_block, in_uue_block, in_base64_block = _is_binary_line(
                line, previous_line, in_yenc_block, in_uue_block, in_base64_block
            )
            if should_skip:
                previous_line = line
                continue

        if redact_pii:
            line = _redact_pii(line)
        if strip_ansi:
            line = RE_ANSI_ESCAPE_PATTERN.sub("", line)
        new_lines.append(line)
        previous_line = line

    return "\r\n".join(new_lines) + "\r\n"


def _create_progress_bar(
    total: int, quiet: bool, desc: str = "Processing messages"
) -> Any:
    """Create a progress bar instance or a null context.

    Args:
        total: Total number of units (bytes).
        quiet: If True, suppress progress output.
        desc: Description text for the progress bar.

    Returns:
        A context manager that yields a ProgressBar or None.
    """
    if quiet:
        return nullcontext()

    try:
        from tqdm import tqdm  # type: ignore

        return tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            desc=desc,
        )
    except ImportError:  # pragma: no cover - tqdm is optional
        if not getattr(_create_progress_bar, "_logged_missing_tqdm", False):
            logging.getLogger(__name__).info(
                "Install tqdm to enable progress reporting."
            )
            setattr(_create_progress_bar, "_logged_missing_tqdm", True)
        return nullcontext()


def get_allowed_conferences(
    conference_filters: list[str] | None,
    board_dict: Mapping[int, str],
) -> set[int]:
    """Determine which conference numbers match the provided filters.

    Args:
        conference_filters: List of conference names or numbers.
        board_dict: Mapping of conference numbers to names.

    Returns:
        A set of conference numbers that match the filters.
    """
    allowed: set[int] = set()
    if not conference_filters:
        return allowed

    for conf_filter in conference_filters:
        if conf_filter.isdigit():
            allowed.add(int(conf_filter))
        else:
            normalized_filter = conf_filter.lower()
            for num, name in board_dict.items():
                if normalized_filter in name.lower():
                    allowed.add(num)
    return allowed


def matches_filters(
    message: ParsedMessage,
    settings: ProcessingSettings,
    allowed_conferences: set[int],
    user_name: str | None = None,
    allowed_exclude_conferences: set[int] | None = None,
) -> bool:
    """Check if a message matches all your filters.

    Args:
        message: The message to check.
        settings: Settings containing your filter choices.
        allowed_conferences: A set of allowed conference numbers.
        user_name: Your name to use for the "mine" filter.
        allowed_exclude_conferences: A set of conference numbers to exclude.

    Returns:
        True if the message matches all filters, False otherwise.
    """

    def check_str_match(pattern: str, text: str) -> bool:
        if settings.regex:
            try:
                return bool(re.search(pattern, text, re.IGNORECASE))
            except re.error:
                return False
        return pattern.lower() in text.lower()

    def any_match(patterns: list[str] | None, text: str) -> bool:
        if not patterns:
            return True

        # Check for empty collection even if truthy (like TruthyEmpty in tests)
        pattern_list = list(patterns)
        if not pattern_list:
            return True

        return any(check_str_match(p, text) for p in pattern_list)

    def matches_any_field(pattern: str) -> bool:
        message.discover_attachments()
        return (
            check_str_match(pattern, message.header.msgfrom)
            or check_str_match(pattern, message.header.msgto)
            or check_str_match(pattern, message.header.msgsubject)
            or check_str_match(pattern, message.text)
            or (message.confname and check_str_match(pattern, message.confname))
            or (message.bbs_name and check_str_match(pattern, message.bbs_name))
            or (message.bbs_id and check_str_match(pattern, message.bbs_id))
            or (message.source_file and check_str_match(pattern, message.source_file))
            or (
                message.attachments
                and any(check_str_match(pattern, a) for a in message.attachments)
            )
        )

    # --- Exclusion Filters (Negative matching) ---
    # If any exclusion matches, the message is rejected immediately.

    # 1. Exclude Search
    if settings.exclude_search and matches_any_field(settings.exclude_search):
        return False

    # 2. Exclude Author
    if settings.exclude_authors and any_match(
        settings.exclude_authors, message.header.msgfrom
    ):
        return False

    # 3. Exclude Recipient
    if settings.exclude_recipients and any_match(
        settings.exclude_recipients, message.header.msgto
    ):
        return False

    # 4. Exclude Subject
    if settings.exclude_subjects and any_match(
        settings.exclude_subjects, message.header.msgsubject
    ):
        return False

    # 5. Exclude Conference
    if allowed_exclude_conferences and message.confnum in allowed_exclude_conferences:
        return False

    # 6. Exclude BBS
    if settings.exclude_bbs_names:
        match_name = any_match(settings.exclude_bbs_names, message.bbs_name or "")
        match_id = any_match(settings.exclude_bbs_names, message.bbs_id or "")
        if match_name or match_id:
            return False

    # --- Inclusion Filters (Positive matching) ---

    # 1. Private/Password Check
    if (
        not settings.private and message.header.is_private
    ) or message.header.is_password:
        return False

    # 2. Conference Filter
    if settings.conferences and message.confnum not in allowed_conferences:
        return False

    # 2b. BBS Filter
    if settings.bbs_names:
        match_name = any_match(settings.bbs_names, message.bbs_name or "")
        match_id = any_match(settings.bbs_names, message.bbs_id or "")
        if not (match_name or match_id):
            return False

    # 2c. Mine Filter
    if settings.mine:
        if not user_name:
            return False
        is_from_me = check_str_match(user_name, message.header.msgfrom)
        is_to_me = check_str_match(user_name, message.header.msgto)
        if not (is_from_me or is_to_me):
            return False

    # 3. Message Number Filter
    if settings.msgnum_filters:
        if message.msgnum is None or message.msgnum not in settings.msgnum_filters:
            return False

    # 3b. Reference Number Filter (Reply-to / Refnum)
    if settings.refnum_filters:
        if message.refnum is None or message.refnum not in settings.refnum_filters:
            return False

    # 4. Author Filter
    if not any_match(settings.authors, message.header.msgfrom):
        return False

    # 5. Recipient Filter
    if not any_match(settings.recipients, message.header.msgto):
        return False

    # 6. Subject Filter
    if not any_match(settings.subjects, message.header.msgsubject):
        return False

    # 7. Full-Text Search
    if settings.search_term and not matches_any_field(settings.search_term):
        return False

    # 7b. Body-Specific Search
    if settings.body_search:
        if not check_str_match(settings.body_search, message.text):
            return False

    # 8. Date Filter
    if settings.after or settings.before or settings.on_this_day:
        msg_dt = _parse_qwk_date(message.header.msgdate, message.header.msgtime)
        if settings.after and msg_dt < settings.after:
            return False
        if settings.before and msg_dt > settings.before:
            return False
        if settings.on_this_day:
            ref = settings.reference_date or datetime.datetime.now()
            if msg_dt.month != ref.month or msg_dt.day != ref.day:
                return False

    # 9. Attachment Filter
    if settings.has_attachments or settings.extract_attachments or settings.attachment_pattern:
        message.discover_attachments()

        if (settings.has_attachments or settings.attachment_pattern) and not message.attachments:
            return False

        if settings.attachment_pattern and message.attachments:
            import fnmatch
            pattern = settings.attachment_pattern.lower()
            any_match = False
            for filename in message.attachments:
                fname = filename.lower()
                # 1. Direct glob match
                if fnmatch.fnmatch(fname, pattern):
                    any_match = True
                    break
                # 2. Glob match with wildcards added if not present (e.g. "zip" -> "*zip*")
                if fnmatch.fnmatch(fname, f"*{pattern}*"):
                    any_match = True
                    break
                # 3. Simple substring fallback
                if pattern in fname:
                    any_match = True
                    break
            if not any_match:
                return False

    # 9b. Links Filter
    if settings.has_links:
        if not (message.text and RE_URL_PATTERN.search(message.text)):
            return False

    # 9c. Emails Filter
    if settings.has_emails:
        if not (message.text and RE_EMAIL_PATTERN.search(message.text)):
            return False

    # 9d. Phones Filter
    if settings.has_phones:
        if not (message.text and RE_PHONE_PATTERN.search(message.text)):
            return False

    # 9e. ANSI Filter
    if settings.has_ansi:
        if not (message.text and RE_ANSI_ESCAPE_PATTERN.search(message.text)):
            return False

    # 9f. Message Links Filter
    if settings.has_msg_links:
        if not (message.text and RE_MSG_LINK_PATTERN.search(message.text)):
            return False

    # 10. Length Filter
    msg_len = len(message.text) if message.text else 0
    if settings.min_length is not None and msg_len < settings.min_length:
        return False
    if settings.max_length is not None and msg_len > settings.max_length:
        return False

    # 11. Word Count Filter
    if settings.min_words is not None or settings.max_words is not None:
        word_count = len(message.text.split()) if message.text else 0
        if settings.min_words is not None and word_count < settings.min_words:
            return False
        if settings.max_words is not None and word_count > settings.max_words:
            return False

    # 12. Attachment Count Filter
    if settings.min_attachments is not None or settings.max_attachments is not None:
        message.discover_attachments()
        attach_count = len(message.attachments) if message.attachments else 0
        if settings.min_attachments is not None and attach_count < settings.min_attachments:
            return False
        if settings.max_attachments is not None and attach_count > settings.max_attachments:
            return False

    # 13. Thread Depth Filter
    if settings.min_depth is not None and message.depth < settings.min_depth:
        return False
    if settings.max_depth is not None and message.depth > settings.max_depth:
        return False

    # 14. Reply Count Filter
    if settings.min_replies is not None and message.reply_count < settings.min_replies:
        return False
    if settings.max_replies is not None and message.reply_count > settings.max_replies:
        return False

    # 15. Thread Size Filter
    if settings.min_thread_size is not None and message.thread_size < settings.min_thread_size:
        return False
    if settings.max_thread_size is not None and message.thread_size > settings.max_thread_size:
        return False

    # 16. Thread ID Filter
    if settings.thread_id_filters:
        if message.thread_id is None:
            return False
        try:
            tid_val = int(message.thread_id)
            if tid_val not in settings.thread_id_filters:
                return False
        except (ValueError, TypeError):
            if message.thread_id not in {str(f) for f in settings.thread_id_filters}:
                return False

    return True


def _slugify(text: str, default: str) -> str:
    """Create a safe name for a file or folder by removing special characters."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()[:30]
    return slug if slug else default


def _get_organization_subpath(
    message: ParsedMessage, settings: ProcessingSettings
) -> str:
    """Determine the relative subfolder path for a message or its attachments."""
    if settings.organize_pattern:
        try:
            raw_mapping = _get_message_mapping(
                message,
                0,
                redact_pii=settings.redact_pii,
                user_name=settings.my_name,
            )

            mapping = {}
            for k, v in raw_mapping.items():
                if isinstance(v, str):
                    mapping[k] = _slugify(v, k)
                else:
                    mapping[k] = v

            subpath = settings.organize_pattern.format(**mapping)
            # Support both forward and backward slashes for cross-platform patterns
            parts = [p for p in subpath.replace("\\", "/").split("/") if p]
            return os.path.join(*parts) if parts else ""
        except (KeyError, ValueError, AttributeError):
            # Fallback to standard organization if pattern fails
            pass

    sub_parts = []

    if settings.organize_by_bbs:
        bbs_name = message.bbs_name or "unknown_bbs"
        sub_parts.append(_slugify(bbs_name, "bbs"))

    if settings.organize_by_author:
        author = message.header.msgfrom or "unknown_author"
        sub_parts.append(_slugify(author, "author"))

    if settings.organize_by_to:
        recipient = message.header.msgto or "unknown_to"
        sub_parts.append(_slugify(recipient, "to"))

    if settings.organize_by_subject:
        norm_subject = _normalize_subject(message.header.msgsubject)
        sub_parts.append(_slugify(norm_subject or "no_subject", "subject"))

    if settings.organize:
        conf_name = message.confname or "unknown"
        conf_slug = _slugify(conf_name, "conference")
        sub_parts.append(f"{message.confnum:03d}-{conf_slug}")

    if settings.organize_by_date:
        msg_dt = _parse_qwk_date(message.header.msgdate, message.header.msgtime)
        sub_parts.append(msg_dt.strftime("%Y"))
        sub_parts.append(msg_dt.strftime("%m"))

    return os.path.join(*sub_parts) if sub_parts else ""


def format_size(size: int) -> str:
    """Format byte count into a human-readable string (B, KB, MB)."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def format_duration(seconds: float) -> str:
    """Format a duration in seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    else:
        return f"{seconds / 86400:.1f}d"


def _get_message_mapping(
    message: ParsedMessage,
    count: int,
    redact_pii: bool = False,
    user_name: str | None = None,
) -> dict[str, Any]:
    """Generate a dictionary of variables representing a message's archive information."""
    message.discover_attachments()
    header = message.header
    dt = _parse_qwk_date(header.msgdate, header.msgtime)

    flags = ""
    if header.is_private:
        flags += "*"
    if message.attachments:
        flags += "@"

    snippet = ""
    if message.text:
        # Get first non-empty line
        for line in message.text.splitlines():
            clean_line = line.strip()
            if clean_line:
                if redact_pii:
                    clean_line = _redact_pii(clean_line)
                snippet = clean_line[:50]
                break

    author = header.msgfrom.strip()
    to = header.msgto.strip()
    subject = header.msgsubject.strip()

    # Determine user name for pattern variable
    my_name_val = user_name or ""
    if not my_name_val:
        bbs_info = getattr(message, "bbs_info", None)
        if bbs_info:
            my_name_val = bbs_info.user_name
        else:
            my_name_val = author

    subject_clean = _normalize_subject(subject, lowercase=False)

    if redact_pii:
        author = _redact_pii(author)
        to = _redact_pii(to)
        subject = _redact_pii(subject)
        subject_clean = _redact_pii(subject_clean)

    indent = ""
    if message.depth > 0:
        indent = "  " * (message.depth - 1) + "└ "

    is_reply = (
        header.refnum is not None and header.refnum != 0
    ) or RE_SUBJECT_PREFIX_PATTERN.match(header.msgsubject)

    attachments_list = message.attachments or []
    attachments_str = ", ".join(attachments_list)

    body = message.text or ""
    body_clean = " ".join(body.split())

    if redact_pii:
        body = _redact_pii(body)
        body_clean = _redact_pii(body_clean)

    entities = _discover_entities(message.text or "")
    urls_list = [e[3] for e in entities if e[2] == "url"]
    emails_list = [e[3] for e in entities if e[2] == "email"]
    phones_list = [e[3] for e in entities if e[2] == "phone"]
    msg_links_list = [e[3] for e in entities if e[2] == "msg_link"]

    url_count = len(urls_list)
    email_count = len(emails_list)
    phone_count = len(phones_list)
    msg_link_count = len(msg_links_list)

    msgnum_val = header.msgnum if header.msgnum is not None else 0
    bbs_id_val = message.bbs_id or ""
    msgid = f"{header.confnum}.{msgnum_val}@{bbs_id_val}"

    return {
        "confnum": header.confnum,
        "confname": message.confname or "",
        "confname_or_num": message.confname or str(header.confnum),
        "msgnum": header.msgnum if header.msgnum is not None else count,
        "author": author,
        "to": to,
        "subject": subject,
        "subject_clean": subject_clean,
        "body": body,
        "body_clean": body_clean,
        "date": header.msgdate,
        "time": header.msgtime,
        "year": dt.year,
        "month": f"{dt.month:02d}",
        "day": f"{dt.day:02d}",
        "hour": f"{dt.hour:02d}",
        "minute": f"{dt.minute:02d}",
        "second": f"{dt.second:02d}",
        "iso_date": dt.date().isoformat(),
        "iso_time": dt.time().isoformat(),
        "bbs_name": message.bbs_name or "",
        "bbs_id": message.bbs_id or "",
        "msgid": msgid,
        "source_file": message.source_file or "",
        "refnum": header.refnum if header.refnum is not None else 0,
        "status": header.status,
        "msgflag": header.msgflag,
        "is_private": "true" if header.is_private else "false",
        "is_reply": "true" if is_reply else "false",
        "attachments": attachments_str,
        "attachment_count": len(attachments_list),
        "url_count": url_count,
        "urls": ", ".join(urls_list),
        "email_count": email_count,
        "emails": ", ".join(emails_list),
        "phone_count": phone_count,
        "phones": ", ".join(phones_list),
        "msg_link_count": msg_link_count,
        "msg_links": ", ".join(msg_links_list),
        "my_name": my_name_val,
        "thread_id": message.thread_id or "",
        "parent_msgnum": message.parent_msgnum if message.parent_msgnum is not None else 0,
        "depth": message.depth,
        "length": len(message.text) if message.text else 0,
        "word_count": len(message.text.split()) if message.text else 0,
        "size": format_size(len(message.text)) if message.text else "0 B",
        "flags": flags,
        "snippet": snippet,
        "indent": indent,
        "reply_count": message.reply_count,
        "thread_size": message.thread_size,
    }


def _generate_safe_filename(
    message: ParsedMessage, settings_or_format: ProcessingSettings | str, count: int
) -> str:
    """Generate a human-readable filename for an individual message."""
    if isinstance(settings_or_format, ProcessingSettings):
        settings = settings_or_format
        output_format = settings.format
    else:
        settings = None
        output_format = settings_or_format

    ext = FORMAT_EXTENSIONS.get(output_format, ".txt")

    if settings and settings.filename_pattern:
        try:
            raw_mapping = _get_message_mapping(
                message,
                count,
                redact_pii=settings.redact_pii if settings else False,
                user_name=settings.my_name if settings else None,
            )

            # Map of variable names to their slugify defaults for filename compatibility
            defaults = {
                "confname": "conf",
                "bbs_name": "bbs",
                "bbs_id": "id",
            }

            # Slugify all string values for use in a filename
            mapping = {}
            for k, v in raw_mapping.items():
                if isinstance(v, str):
                    df = defaults.get(k, k)
                    if k == "confname" and not v:
                        mapping[k] = _slugify(f"conf_{message.confnum}", "conf")
                    else:
                        mapping[k] = _slugify(v, df)
                else:
                    mapping[k] = v

            # Use formatting while preserving the pattern's intent
            filename = settings.filename_pattern.format(**mapping)
            # Basic sanitization of the resulting filename (replace any remaining odd chars)
            filename = re.sub(r"[^\w\-.]", "_", filename)
            if not filename.endswith(ext):
                filename += ext
            return filename
        except (KeyError, ValueError, AttributeError):
            # Fallback to default if pattern is invalid
            pass

    msg_num = message.msgnum if message.msgnum is not None else count
    slug = _slugify(message.header.msgsubject, "message")

    return f"{message.confnum:03d}-{msg_num:05d}-{slug}{ext}"


def _render_message_oneline(
    message: ParsedMessage,
    settings: ProcessingSettings,
    count: int,
    use_colors: bool,
    board_dict: dict[int, str] | None = None,
    user_name: str | None = None,
) -> str:
    """Render a one-line summary for a message using patterns or standard format."""
    if settings.oneline_pattern:
        try:
            mapping = _get_message_mapping(
                message,
                count,
                redact_pii=settings.redact_pii,
                user_name=user_name,
            )
            # Apply fallbacks for oneline display
            if not mapping["confname"]:
                mapping["confname"] = f"Conference {message.confnum}"

            text = settings.oneline_pattern.format(**mapping) + "\r\n"
            # Apply search highlighting to the resulting line
            return _linkify_text(
                text,
                "ansi",
                search_term=settings.search_term,
                is_regex=settings.regex,
                use_colors=use_colors,
            )
        except (KeyError, ValueError):
            # Fallback if pattern is invalid
            pass

    return message.header.format_oneline(
        board_dict or {},
        use_colors=use_colors,
        highlight_term=settings.search_term,
        is_regex=settings.regex,
        verbose=settings.verbose,
        depth=message.depth,
        conf_name=message.confname,
        is_private=message.header.is_private,
        has_attachments=bool(message.attachments),
        redact_pii=settings.redact_pii,
    )


def _pack_directory_to_archive(src_dir: str, archive_path: str, logger: logging.Logger) -> None:
    """Pack a directory's contents into a ZIP or TAR archive."""
    logger.info("Packing exported files into archive: %s", archive_path)
    ext = archive_path.lower()
    parent_dir = os.path.dirname(archive_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    if ext.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(src_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, src_dir)
                    zf.write(full_path, rel_path)
    elif ext.endswith((".tar", ".tar.gz", ".tar.bz2", ".tgz")):
        mode = "w"
        if ext.endswith(".tar.gz") or ext.endswith(".tgz"):
            mode = "w:gz"
        elif ext.endswith(".tar.bz2"):
            mode = "w:bz2"
        with tarfile.open(archive_path, mode) as tf:
            for root, dirs, files in os.walk(src_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, src_dir)
                    tf.add(full_path, rel_path)


def process_merged_files(
    input_paths: list[str],
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:
    """Read multiple archives, filter and clean the messages, and save the results.

    This function handles the main workflow of finding messages, applying filters,
    cleaning the text, and writing the output to files or the screen.
    """
    if settings.count_only:
        settings = replace(settings, quiet=True)

    output_mode = settings.output_mode
    resolved_output_path = settings.output_path

    if output_mode == "stdout" and resolved_output_path is not None:
        raise ValueError("You cannot provide an output path when printing to the screen.")
    if (
        not settings.individual_files
        and output_mode == "file"
        and resolved_output_path is None
    ):
        raise ValueError("An output path is required when output mode is file.")

    output_dir: str | None = None
    temp_dir_obj = None
    is_archive_export = False
    if settings.individual_files:
        if resolved_output_path is None:
            raise ValueError("An output path is required when using individual files.")

        is_archive_export = resolved_output_path.lower().endswith((".zip", ".tar", ".tar.gz", ".tar.bz2", ".tgz"))
        if is_archive_export:
            if not settings.dry_run:
                temp_dir_obj = tempfile.TemporaryDirectory()
                output_dir = temp_dir_obj.name
            else:
                output_dir = "dry_run_temp_dir"
        else:
            output_dir = resolved_output_path
            if os.path.exists(output_dir) and not os.path.isdir(output_dir):
                raise ValueError(
                    "The output path must be a folder when using individual files."
                )
            if not settings.dry_run:
                os.makedirs(output_dir, exist_ok=True)

    collected_messages: list[ParsedMessage] = []
    seen_ids: set[tuple[str, int, int | str]] = set()

    use_colors = (
        output_mode == "stdout"
        and settings.format == "text"
        and hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
    )

    separator_mode = settings.separator
    if separator_mode == "auto":
        if settings.individual_files or settings.format in (
            "json",
            "xml",
            "html",
            "csv",
            "markdown",
            "sqlite",
            "mbox",
            "eml",
            "qwk",
            "rep",
        ):
            separator_mode = "none"
        else:
            separator_mode = "dashes"
    separator_str = ""
    if separator_mode == "dashes":
        separator_str = ("-" * 80) + "\r\n"
        separator_str = _colorize(separator_str, "90", enabled=use_colors)
    elif separator_mode == "blank":
        separator_str = "\r\n"

    total_matching = 0
    total_encountered = 0
    processed_count = 0
    estimated_bytes = 0
    potential_files = 0
    use_streaming = not (
        settings.sort
        or settings.reverse
        or settings.threaded
        or settings.tail
        or settings.thread_id_filters
        or settings.min_replies is not None
        or settings.max_replies is not None
        or settings.min_thread_size is not None
        or settings.max_thread_size is not None
    )

    initial_filtering_settings = settings
    if settings.threaded or settings.thread_id_filters or any(
        v is not None
        for v in (
            settings.min_replies,
            settings.max_replies,
            settings.min_thread_size,
            settings.max_thread_size,
        )
    ):
        initial_filtering_settings = replace(
            settings,
            min_depth=None,
            max_depth=None,
            min_replies=None,
            max_replies=None,
            min_thread_size=None,
            max_thread_size=None,
            thread_id_filters=None,
        )

    sort_buffer: list[tuple[ParsedMessage, dict[int, str]]] = []
    collected_for_index: list[dict[str, Any]] = []
    bbs_info_to_use = None
    board_dict_to_use = None
    total_attachments = 0
    conf_processed_counts: dict[int, int] = defaultdict(int)
    author_processed_counts: dict[str, int] = defaultdict(int)
    to_processed_counts: dict[str, int] = defaultdict(int)
    subject_processed_counts: dict[str, int] = defaultdict(int)
    bbs_processed_counts: dict[str, int] = defaultdict(int)

    include_header = not settings.no_header and settings.format == "text"
    target_encoding = "utf-8"
    if settings.individual_files and settings.format == "text":
        target_encoding = settings.encoding

    def handle_output(
        parsed_message: ParsedMessage, board_dict: dict[int, str]
    ) -> bool:
        """Process and output a single message. Returns True if processing should stop."""
        nonlocal \
            total_matching, \
            processed_count, \
            estimated_bytes, \
            potential_files, \
            collected_for_index, \
            conf_processed_counts, \
            author_processed_counts, \
            to_processed_counts, \
            subject_processed_counts, \
            bbs_processed_counts

        total_matching += 1
        if settings.skip is not None and total_matching <= settings.skip:
            return False

        if settings.limit_per_conf is not None:
            if conf_processed_counts[parsed_message.confnum] >= settings.limit_per_conf:
                return False

        if settings.limit_per_author is not None:
            author_key = parsed_message.header.msgfrom.strip().lower()
            if author_processed_counts[author_key] >= settings.limit_per_author:
                return False

        if settings.limit_per_to is not None:
            to_key = parsed_message.header.msgto.strip().lower()
            if to_processed_counts[to_key] >= settings.limit_per_to:
                return False

        if settings.limit_per_subject is not None:
            subject_key = _normalize_subject(parsed_message.header.msgsubject)
            if subject_processed_counts[subject_key] >= settings.limit_per_subject:
                return False

        if settings.limit_per_bbs is not None:
            bbs_key = (parsed_message.bbs_name or parsed_message.bbs_id or "").strip().lower()
            if bbs_processed_counts[bbs_key] >= settings.limit_per_bbs:
                return False

        if settings.limit is not None and processed_count >= settings.limit:
            return True

        conf_processed_counts[parsed_message.confnum] += 1
        author_key = parsed_message.header.msgfrom.strip().lower()
        author_processed_counts[author_key] += 1
        to_key = parsed_message.header.msgto.strip().lower()
        to_processed_counts[to_key] += 1
        subject_key = _normalize_subject(parsed_message.header.msgsubject)
        subject_processed_counts[subject_key] += 1
        bbs_key = (parsed_message.bbs_name or parsed_message.bbs_id or "").strip().lower()
        bbs_processed_counts[bbs_key] += 1
        processed_count += 1

        if settings.count_only:
            return False

        if settings.extract_attachments and parsed_message.text:
            # Re-scan to get binary data for extraction
            found_attachments = extract_binaries(parsed_message.text)

            if settings.attachment_pattern and found_attachments:
                import fnmatch
                pattern = settings.attachment_pattern.lower()
                filtered = []
                for fname, fdata in found_attachments:
                    fn_low = fname.lower()
                    matched = (
                        fnmatch.fnmatch(fn_low, pattern)
                        or fnmatch.fnmatch(fn_low, f"*{pattern}*")
                        or pattern in fn_low
                    )
                    if matched:
                        filtered.append((fname, fdata))
                found_attachments = filtered

            if found_attachments:
                nonlocal total_attachments
                # Determine attachments directory
                if settings.individual_files:
                    attach_base = resolved_output_path or "."
                elif settings.output_path:
                    if os.path.isdir(settings.output_path):
                        attach_base = settings.output_path
                    else:
                        attach_base = os.path.dirname(settings.output_path) or "."
                else:
                    attach_base = "."

                attach_dir = os.path.join(attach_base, "attachments")
                if settings.organize_attachments:
                    attach_subpath = _get_organization_subpath(parsed_message, settings)
                    if attach_subpath:
                        attach_dir = os.path.join(attach_dir, attach_subpath)

                if not settings.dry_run:
                    os.makedirs(attach_dir, exist_ok=True)
                    for filename, data in found_attachments:
                        # Use only the filename to prevent saving files in unexpected locations
                        filename = os.path.basename(filename)
                        if not filename:
                            filename = "attachment.bin"

                        total_attachments += 1
                        base, ext = os.path.splitext(filename)
                        target_path = os.path.join(attach_dir, filename)
                        counter = 1
                        while os.path.exists(target_path):
                            target_path = os.path.join(
                                attach_dir, f"{base}_{counter}{ext}"
                            )
                            counter += 1
                        with open(target_path, "wb") as f:
                            f.write(data)
                else:
                    total_attachments += len(found_attachments)

        # Pre-process the body if we are not in headers-only mode
        cleaned_body = ""
        if not settings.headers_only and parsed_message.text:
            cleaned_body = process_message(
                parsed_message.text,
                settings.truncate_signatures,
                settings.cut_quoting,
                settings.binaries_removal,
                settings.redact_pii,
                settings.strip_ansi,
            )

            # Apply quote highlighting for terminal output
            cleaned_body = _highlight_quotes(cleaned_body, use_colors)

            # Apply search highlighting to body for terminal output
            cleaned_body = _linkify_text(
                cleaned_body,
                "ansi",
                search_term=settings.search_term,
                is_regex=settings.regex,
                use_colors=use_colors,
            )

        if settings.oneline:
            processed_buffer = _render_message_oneline(
                parsed_message,
                settings,
                processed_count,
                use_colors,
                board_dict,
                user_name,
            )
        else:
            processed_buffer = cleaned_body

            if include_header:
                leading_newlines = 0
                text_prefix = parsed_message.text
                while text_prefix.startswith("\r\n"):
                    leading_newlines += 1
                    text_prefix = text_prefix[2:]
                if leading_newlines and not processed_buffer.startswith("\r\n"):
                    processed_buffer = ("\r\n" * leading_newlines) + processed_buffer

                header_text = parsed_message.header.format_text(
                    board_dict,
                    settings.verbose,
                    include_separator=False,
                    use_colors=use_colors,
                    highlight_term=settings.search_term,
                    is_regex=settings.regex,
                    attachments=parsed_message.attachments,
                    bbs_name=parsed_message.bbs_name,
                    redact_pii=settings.redact_pii,
                )
                processed_buffer = header_text + processed_buffer

            # Add separator for text format
            if settings.format == "text":
                processed_buffer = separator_str + processed_buffer

        # Determine appropriate text content for modern formats
        if (
            settings.format in ("json", "xml", "csv", "sqlite", "mbox", "eml")
            and settings.headers_only
        ):
            text_content = ""
        elif settings.oneline and settings.format in (
            "json",
            "xml",
            "csv",
            "sqlite",
            "mbox",
            "eml",
            "html",
            "markdown",
        ):
            text_content = cleaned_body
        else:
            text_content = processed_buffer

        temp_msg = replace(
            parsed_message, text=text_content, original_text=parsed_message.text
        )

        if settings.individual_files:
            assert output_dir is not None

            target_dir = output_dir
            relative_sub_path = _get_organization_subpath(parsed_message, settings)
            if relative_sub_path:
                target_dir = os.path.join(output_dir, relative_sub_path)
                if not settings.dry_run:
                    os.makedirs(target_dir, exist_ok=True)

            attachment_prefix = None
            if settings.extract_attachments:
                depth = 0
                if relative_sub_path:
                    # Each level of directory nesting requires an extra '../'
                    depth = len(relative_sub_path.replace(os.sep, "/").split("/"))

                attachment_prefix = ("../" * depth) + "attachments/"

                if settings.organize_attachments:
                    attach_subpath = _get_organization_subpath(parsed_message, settings)
                    if attach_subpath:
                        attachment_prefix += attach_subpath.replace(os.sep, "/") + "/"

            if settings.format == "text":
                encoded_buffer = processed_buffer.encode(target_encoding)
            elif settings.format == "json":
                encoded_buffer = json.dumps(
                    _message_to_dict(temp_msg), indent=4, ensure_ascii=False
                ).encode(target_encoding)
            elif settings.format == "xml":
                encoded_buffer = _xml_element_to_str(
                    _message_to_xml_element(temp_msg)
                ).encode(target_encoding)
            elif settings.format == "html":
                encoded_buffer = _serialize_message_html(
                    temp_msg,
                    attachment_prefix=attachment_prefix,
                    search_term=settings.search_term,
                    is_regex=settings.regex,
                    embed_attachments=settings.embed_attachments,
                ).encode(target_encoding)
            elif settings.format == "markdown":
                encoded_buffer = _serialize_message_markdown(
                    temp_msg,
                    attachment_prefix=attachment_prefix,
                    search_term=settings.search_term,
                    is_regex=settings.regex,
                ).encode(target_encoding)
            elif settings.format == "mbox":
                encoded_buffer = _serialize_rfc822(
                    temp_msg, include_mbox_header=True
                ).encode(target_encoding)
            elif settings.format == "eml":
                encoded_buffer = _serialize_rfc822(
                    temp_msg, include_mbox_header=False
                ).encode(target_encoding)
            else:
                encoded_buffer = processed_buffer.encode(target_encoding)

            filename = _generate_safe_filename(
                parsed_message, settings, processed_count
            )
            full_path = os.path.join(target_dir, filename)

            # Avoid duplicate filenames
            if os.path.exists(full_path):
                base, ext = os.path.splitext(filename)
                counter = 0
                while os.path.exists(full_path):
                    counter += 1
                    # Incorporate counter into hash to ensure uniqueness even for same content
                    salt = str(counter).encode()
                    short_hash = hashlib.sha1(encoded_buffer + salt).hexdigest()[:8]
                    filename = f"{base}-{short_hash}{ext}"
                    full_path = os.path.join(target_dir, filename)
                    if counter > 100:  # Safety break
                        break

            estimated_bytes += len(encoded_buffer)
            potential_files += 1

            if settings.format in ("html", "markdown"):
                rel_path = os.path.join(relative_sub_path, filename)
                collected_for_index.append(
                    {
                        "path": rel_path,
                        "subject": parsed_message.header.msgsubject.strip(),
                        "from": parsed_message.header.msgfrom.strip(),
                        "to": parsed_message.header.msgto.strip(),
                        "date": f"{parsed_message.header.msgdate} {parsed_message.header.msgtime}",
                        "conf_num": parsed_message.confnum,
                        "conf_name": parsed_message.confname
                        or f"Conference {parsed_message.confnum}",
                        "msgnum": parsed_message.header.msgnum,
                        "attachments": parsed_message.attachments,
                        "depth": parsed_message.depth,
                    }
                )

            if not settings.dry_run:
                with open(full_path, "wb") as f:
                    f.write(encoded_buffer)
        else:
            estimated_bytes += len(processed_buffer.encode("utf-8"))
            if not settings.dry_run:
                collected_messages.append(temp_msg)
        return False

    for input_path in input_paths:
        file_data, board_dict = load_data(input_path, logger, settings.encoding)
        bbs_info = getattr(board_dict, "bbs_info", None)
        user_name = settings.my_name or (bbs_info.user_name if bbs_info else None)

        if board_dict:
            if board_dict_to_use is None:
                board_dict_to_use = ConferenceMap(board_dict)
                board_dict_to_use.bbs_info = bbs_info
            else:
                for k, v in board_dict.items():
                    if k not in board_dict_to_use:
                        board_dict_to_use[k] = v
                if bbs_info and not board_dict_to_use.bbs_info:
                    board_dict_to_use.bbs_info = bbs_info

        if bbs_info and not bbs_info_to_use:
            bbs_info_to_use = bbs_info
        bbs_key = f"{bbs_info.name}|{bbs_info.bbs_id}" if bbs_info else ""

        allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)
        allowed_exclude_conferences = get_allowed_conferences(
            settings.exclude_conferences, board_dict
        )

        desc = f"Processing {os.path.basename(input_path)}"

        is_structured = isinstance(file_data, list)
        total_progress = len(file_data)

        with _create_progress_bar(
            total_progress, settings.quiet, desc=desc
        ) as progress_bar:
            if is_structured:
                messages_to_process = file_data
                if progress_bar is not None:
                    progress_bar.unit = "msg"
                    progress_bar.unit_scale = False
            else:
                messages_to_process = parse_messages(
                    file_data,
                    progress_bar,
                    settings.encoding,
                    settings.headers_only,
                )

            for parsed_message in messages_to_process:
                total_encountered += 1
                if is_structured and progress_bar is not None:
                    progress_bar.update(1)

                parsed_message = replace(
                    parsed_message,
                    confname=parsed_message.confname
                    or board_dict.get(parsed_message.confnum),
                    bbs_name=parsed_message.bbs_name
                    or (bbs_info.name if bbs_info else None),
                    bbs_id=parsed_message.bbs_id
                    or (bbs_info.bbs_id if bbs_info else None),
                    source_file=parsed_message.source_file
                    or os.path.basename(input_path),
                )
                if not matches_filters(
                    parsed_message,
                    initial_filtering_settings,
                    allowed_conferences,
                    user_name,
                    allowed_exclude_conferences,
                ):
                    continue

                if settings.unique:
                    msg_id: tuple[str, int, int | str]
                    # Use the message's own BBS information for the ID to ensure
                    # correct deduplication across mixed sources (e.g. JSONL)
                    current_bbs_key = (
                        f"{parsed_message.bbs_name}|{parsed_message.bbs_id}"
                        if parsed_message.bbs_name or parsed_message.bbs_id
                        else bbs_key
                    )
                    if parsed_message.msgnum is not None:
                        msg_id = (
                            current_bbs_key,
                            parsed_message.confnum,
                            parsed_message.msgnum,
                        )
                    else:
                        content_hash = hashlib.sha1(
                            parsed_message.text.encode(
                                settings.encoding, errors="replace"
                            )
                        ).hexdigest()
                        msg_id = (current_bbs_key, parsed_message.confnum, content_hash)

                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)

                if not use_streaming:
                    sort_buffer.append((parsed_message, board_dict))
                    continue

                should_stop = handle_output(parsed_message, board_dict)
                if should_stop:
                    break
            if settings.limit is not None and processed_count >= settings.limit:
                break

    if not use_streaming:
        reversal_needed = settings.reverse
        if settings.threaded or any(
            v is not None
            for v in (
                settings.min_replies,
                settings.max_replies,
                settings.min_thread_size,
                settings.max_thread_size,
            )
        ):
            # Apply conversation threading to calculate metrics and/or order by thread.
            msgs_only = [m for m, bd in sort_buffer]
            threaded_msgs = _order_messages_by_thread(msgs_only)

            # Apply depth and engagement filtering now that metrics are calculated.
            if any(
                v is not None
                for v in (
                    settings.min_depth,
                    settings.max_depth,
                    settings.min_replies,
                    settings.max_replies,
                    settings.min_thread_size,
                    settings.max_thread_size,
                )
            ) or settings.thread_id_filters:
                threaded_msgs = [
                    m
                    for m in threaded_msgs
                    if (settings.min_depth is None or m.depth >= settings.min_depth)
                    and (settings.max_depth is None or m.depth <= settings.max_depth)
                    and (
                        settings.min_replies is None
                        or m.reply_count >= settings.min_replies
                    )
                    and (
                        settings.max_replies is None
                        or m.reply_count <= settings.max_replies
                    )
                    and (
                        settings.min_thread_size is None
                        or m.thread_size >= settings.min_thread_size
                    )
                    and (
                        settings.max_thread_size is None
                        or m.thread_size <= settings.max_thread_size
                    )
                    and (
                        settings.thread_id_filters is None
                        or (
                            m.thread_id is not None
                            and (
                                _safe_to_int(m.thread_id) in settings.thread_id_filters
                                if _safe_to_int(m.thread_id) is not None
                                else m.thread_id in {str(f) for f in settings.thread_id_filters}
                            )
                        )
                    )
                ]

            sort_buffer = []
            for m in threaded_msgs:
                # Re-attach the merged board_dict. handle_output's use of board_dict
                # is for formatting headers, which benefits from the global map.
                sort_buffer.append((m, board_dict_to_use or {}))

        if settings.sort:
            if settings.sort == "random":
                random.shuffle(sort_buffer)
                reversal_needed = False
            else:
                sort_keys: dict[
                    str, Callable[[tuple[ParsedMessage, dict[int, str]]], Any]
                ] = {
                    "date": lambda x: _parse_qwk_date(
                        x[0].header.msgdate, x[0].header.msgtime
                    ),
                    "author": lambda x: x[0].header.msgfrom.lower(),
                    "to": lambda x: x[0].header.msgto.lower(),
                    "subject": lambda x: x[0].header.msgsubject.lower(),
                    "num": lambda x: (x[0].confnum, x[0].msgnum or 0),
                    "conference": lambda x: (
                        x[0].confnum,
                        _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime),
                    ),
                    "bbs": lambda x: (
                        x[0].bbs_name or "",
                        x[0].bbs_id or "",
                        _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime),
                    ),
                    "length": lambda x: len(x[0].text) if x[0].text else 0,
                    "size": lambda x: len(x[0].text) if x[0].text else 0,
                    "words": lambda x: len(x[0].text.split()) if x[0].text else 0,
                    "attachments": lambda x: len(x[0].discover_attachments() or []),
                    "replies": lambda x: x[0].reply_count,
                    "thread_size": lambda x: x[0].thread_size,
                }
                if settings.sort in sort_keys:
                    sort_buffer.sort(
                        key=sort_keys[settings.sort], reverse=settings.reverse
                    )
                    reversal_needed = False

        if reversal_needed:
            sort_buffer.reverse()

        # Apply skip, limit, and tail to the buffer
        if settings.skip is not None:
            sort_buffer = sort_buffer[settings.skip :]

        if settings.limit is not None:
            sort_buffer = sort_buffer[: settings.limit]

        if settings.tail is not None:
            sort_buffer = sort_buffer[-settings.tail :] if settings.tail > 0 else []

        # Temporarily clear skip/limit in settings to avoid redundant filtering in handle_output
        original_skip = settings.skip
        original_limit = settings.limit
        settings.skip = None
        settings.limit = None

        try:
            for parsed_message, board_dict in sort_buffer:
                handle_output(parsed_message, board_dict)
        finally:
            settings.skip = original_skip
            settings.limit = original_limit

    if settings.count_only:
        print(processed_count)
        return

    if settings.individual_files:
        if not settings.dry_run and collected_for_index:
            # Reconstruct dummy messages for stats if necessary, or just extract info from collected_for_index
            def gen_dummy_messages():
                for info in collected_for_index:
                    # Date is stored as "msgdate msgtime", split carefully to avoid IndexError
                    date_parts = info["date"].split(" ", 1)
                    msgdate = date_parts[0]
                    msgtime = date_parts[1] if len(date_parts) > 1 else ""

                    h = MessageHeader(
                        status=" ",
                        msgnum=info["msgnum"],
                        msgdate=msgdate,
                        msgtime=msgtime,
                        msgto=info["to"],
                        msgfrom=info["from"],
                        msgsubject=info["subject"],
                        msgpassword="",
                        refnum=None,
                        numblocks=None,
                        msgflag=" ",
                        confnum=info["conf_num"],
                        lognum=0,
                        nettag="",
                    )
                    yield ParsedMessage(
                        text="",
                        msgnum=info["msgnum"],
                        refnum=None,
                        confnum=info["conf_num"],
                        header=h,
                        confname=info["conf_name"],
                        attachments=info["attachments"],
                        depth=info.get("depth", 0),
                    )

            export_stats = _compute_stats_from_messages(gen_dummy_messages())
            _write_index(
                collected_for_index,
                output_dir,
                settings,
                bbs_info_to_use,
                stats=export_stats,
            )
    else:
        if not settings.dry_run:
            ordered_messages = (
                _order_messages_by_thread(collected_messages)
                if settings.threaded
                else collected_messages
            )
            write_messages(
                ordered_messages,
                resolved_output_path,
                settings,
                bbs_info_to_use,
                board_dict_to_use,
            )
        else:
            potential_files = 1

    if not settings.dry_run and not settings.quiet:
        BOLD = "1"
        GREEN = "32"

        count_label = "message" if processed_count == 1 else "messages"

        if total_encountered > processed_count:
            msg = f"Successfully processed {processed_count} of {total_encountered} messages"
        else:
            msg = f"Successfully processed {processed_count} {count_label}"

        if total_attachments > 0:
            attach_label = "attachment" if total_attachments == 1 else "attachments"
            msg += f" and extracted {total_attachments} {attach_label}"

        if settings.individual_files:
            msg += f" into '{resolved_output_path}'."
        elif resolved_output_path:
            msg += f" and saved to '{resolved_output_path}'."
        else:
            msg += "."

        # Use a localized colorization that respects terminal settings
        print(f"\n{_colorize(msg, BOLD, GREEN, enabled=use_colors)}")

    if settings.dry_run:
        CYAN = "36"
        BOLD = "1"
        print(f"\n{_colorize('--- Dry Run Summary ---', BOLD, CYAN, enabled=use_colors)}")
        print(f"Archives processed: {len(input_paths)}")
        print(f"Matching messages:  {processed_count}")
        if total_attachments > 0:
            print(f"Attachments:        {total_attachments}")
        if settings.individual_files:
            print(f"Files to create:    {potential_files}")
        else:
            print("Files to create:    1 (merged)")

        size_str = format_size(estimated_bytes)
        print(f"Estimated size:     {size_str}")
        print(f"{_colorize('No changes were made to the disk.', BOLD, enabled=use_colors)}")

    if temp_dir_obj:
        try:
            if not settings.dry_run:
                _pack_directory_to_archive(output_dir, resolved_output_path, logger)
        finally:
            temp_dir_obj.cleanup()


def _message_to_dict(message: ProcessedMessage) -> dict[str, Any]:
    message.discover_attachments()
    return {
        "header": message.header.as_dict,
        "conference": message.confname,
        "bbs_name": message.bbs_name,
        "bbs_id": message.bbs_id,
        "source_file": message.source_file,
        "text": message.text,
        "depth": message.depth,
        "thread_id": message.thread_id,
        "parent_msgnum": message.parent_msgnum,
        "attachments": message.attachments or [],
        "reply_count": message.reply_count,
        "thread_size": message.thread_size,
    }


def _write_json(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to a JSON file, optionally including archive metadata."""
    message_list = [_message_to_dict(msg) for msg in messages]
    # Only use the structured format if verbose/toc is set or if settings is missing (library use)
    use_wrapper = (settings and (settings.verbose or settings.include_toc)) or (
        not settings and (bbs_info or board_dict)
    )
    if use_wrapper and (bbs_info or board_dict):
        output_data = {
            "type": "qwk_archive",
            "bbs_info": asdict(bbs_info) if bbs_info else None,
            "conferences": dict(board_dict) if board_dict else None,
            "messages": message_list,
        }
    else:
        output_data = message_list
    output_json = json.dumps(output_data, indent=4, ensure_ascii=False)
    _write_text_output(output_json, output_path, encoding="utf-8")


def _write_jsonl(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to a JSONL file, optionally prepending a metadata record."""
    lines = []
    # Only include metadata line if verbose/toc is set or if settings is missing (library use)
    use_metadata = (settings and (settings.verbose or settings.include_toc)) or (
        not settings and (bbs_info or board_dict)
    )
    if use_metadata and (bbs_info or board_dict):
        metadata = {
            "type": "metadata",
            "bbs_info": asdict(bbs_info) if bbs_info else None,
            "conferences": dict(board_dict) if board_dict else None,
        }
        lines.append(json.dumps(metadata, ensure_ascii=False))
    for msg in messages:
        lines.append(json.dumps(_message_to_dict(msg), ensure_ascii=False))
    output_jsonl = "\n".join(lines) + "\n"
    _write_text_output(output_jsonl, output_path, encoding="utf-8")


XML_INVALID_CHAR_PATTERN = re.compile(
    r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]"
)


def _xml_safe(text: Any) -> str:
    """Sanitize text for XML output by removing invalid characters."""
    if text is None:
        return ""
    return XML_INVALID_CHAR_PATTERN.sub("", str(text))


def _message_to_xml_element(message: ProcessedMessage) -> ET.Element:
    """Convert a message to an XML Element."""
    msg_element = ET.Element("message")

    if message.depth > 0:
        ET.SubElement(msg_element, "depth").text = str(message.depth)
    if message.thread_id:
        ET.SubElement(msg_element, "thread_id").text = _xml_safe(message.thread_id)
    if message.parent_msgnum is not None:
        ET.SubElement(msg_element, "parent_msgnum").text = str(message.parent_msgnum)

    if message.confname:
        ET.SubElement(msg_element, "conference_name").text = _xml_safe(message.confname)
    if message.bbs_name:
        ET.SubElement(msg_element, "bbs_name").text = _xml_safe(message.bbs_name)
    if message.bbs_id:
        ET.SubElement(msg_element, "bbs_id").text = _xml_safe(message.bbs_id)
    if message.source_file:
        ET.SubElement(msg_element, "source_file").text = _xml_safe(message.source_file)

    header_element = ET.SubElement(msg_element, "header")
    header_data = message.header.as_dict
    for key, value in header_data.items():
        child = ET.SubElement(header_element, key)
        child.text = _xml_safe(value)

    text_element = ET.SubElement(msg_element, "text")
    text_element.text = _xml_safe(message.text)

    if message.attachments:
        attachments_element = ET.SubElement(msg_element, "attachments")
        for filename in message.attachments:
            ET.SubElement(attachments_element, "attachment").text = _xml_safe(filename)

    return msg_element


def _xml_element_to_str(element: ET.Element) -> str:
    """Helper to indent and convert an XML element to a string."""
    ET.indent(element, space="  ")
    return ET.tostring(element, encoding="unicode")


def _write_xml(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    root = ET.Element("messages")
    for message in messages:
        msg_element = _message_to_xml_element(message)
        root.append(msg_element)

    xml_text = _xml_element_to_str(root)
    _write_text_output(xml_text, output_path, encoding="utf-8")


def _write_rss(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Export messages to an RSS 2.0 feed."""
    title = "QWK Message Archive"
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Archive"

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = _xml_safe(title)
    ET.SubElement(channel, "link").text = "https://github.com/RainRat/pyqwk"
    ET.SubElement(channel, "description").text = _xml_safe(
        f"Syndicated messages from {title}"
    )
    ET.SubElement(channel, "generator").text = f"pyqwk {__version__}"

    for message in messages:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = _xml_safe(message.header.msgsubject)

        # pubDate
        dt = _parse_qwk_date(message.header.msgdate, message.header.msgtime)
        ET.SubElement(item, "pubDate").text = email.utils.format_datetime(dt)

        ET.SubElement(item, "author").text = _xml_safe(message.header.msgfrom)

        # GUID
        msg_id = f"{message.header.confnum}.{message.header.msgnum if message.header.msgnum is not None else 'x'}@qwk"
        guid = ET.SubElement(item, "guid", isPermaLink="false")
        guid.text = msg_id

        # Description (body)
        desc = ET.SubElement(item, "description")
        desc.text = _xml_safe(message.text)

        if message.confname:
            ET.SubElement(item, "category").text = _xml_safe(message.confname)

    xml_text = '<?xml version="1.0" encoding="utf-8"?>\n' + _xml_element_to_str(rss)
    _write_text_output(xml_text, output_path, encoding="utf-8")


def _get_html_header(title: str) -> list[str]:
    return [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8" />',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        ".reply { margin-left: 2em; border-left: 2px solid #ccc; padding-left: 1em; }",
        ".message { margin-bottom: 1em; border: 1px solid #eee; padding: 1em; }",
        ".header { background-color: #f9f9f9; padding: 0.5em; margin-bottom: 0.5em; }",
        ".body { white-space: pre-wrap; font-family: monospace; }",
        ".quote { color: #4e9a06; }",
        ".stats-container { margin-bottom: 2em; padding: 1em; border: 1px solid #ddd; background-color: #fcfcfc; }",
        ".stats-grid { display: flex; flex-wrap: wrap; gap: 2em; }",
        ".stats-box { flex: 1; min-width: 300px; }",
        ".stats-bar-container { display: flex; align-items: center; margin-bottom: 0.5em; }",
        ".stats-bar-label { width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.9em; }",
        ".stats-bar-count { width: 40px; text-align: right; margin-right: 10px; font-weight: bold; font-size: 0.9em; }",
        ".stats-bar { height: 1.2em; background-color: #00aaaa; min-width: 1px; }",
        ".stats-summary-info { margin-bottom: 1em; font-size: 0.95em; color: #555; }",
        ".message-nav { font-size: 0.85em; margin-bottom: 1em; padding-bottom: 0.5em; border-bottom: 1px solid #eee; color: #666; }",
        ".message-nav a { text-decoration: none; color: #0055aa; margin: 0 0.5em; }",
        ".message-nav a:hover { text-decoration: underline; }",
        "</style>",
        "</head>",
        "<body>",
    ]


def _get_html_footer() -> list[str]:
    return [
        "</body>",
        "</html>",
    ]


def _get_stats_distributions(stats: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Prepare distribution data lists for statistics rendering."""
    dist = {}

    dist["conferences"] = [
        {"name": f"{c['number']}: {c['name']}", "count": c["count"]}
        for c in stats.get("conferences", [])
    ]

    if stats.get("year_distribution"):
        dist["years"] = [
            {"label": y, "count": c}
            for y, c in sorted(stats["year_distribution"].items())
        ]

    if stats.get("month_distribution"):
        dist["months"] = [
            {"label": m, "count": c}
            for m, c in sorted(stats["month_distribution"].items())
        ]

    if stats.get("day_of_week"):
        days_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        dist["days"] = [
            {"label": d, "count": stats["day_of_week"].get(d, 0)} for d in days_order
        ]

    if stats.get("hour_of_day"):
        dist["hours"] = [
            {"label": f"{int(h):02}:00", "count": c}
            for h, c in sorted(stats["hour_of_day"].items(), key=lambda x: int(x[0]))
        ]

    return dist


def _render_stats_html(stats: dict[str, Any]) -> list[str]:
    """Render a statistics summary as an HTML fragment."""
    parts = []
    parts.append('<div class="stats-container">')
    parts.append("<h2>Archive Summary</h2>")

    parts.append('<div class="stats-summary-info">')
    parts.append(
        f"<div><strong>Messages:</strong> {stats['matching_messages']} matching / {stats['total_messages']} total</div>"
    )
    if stats["dates"]["earliest"]:
        earliest = datetime.datetime.fromisoformat(stats["dates"]["earliest"]).strftime(
            "%Y-%m-%d"
        )
        latest = datetime.datetime.fromisoformat(stats["dates"]["latest"]).strftime(
            "%Y-%m-%d"
        )
        parts.append(f"<div><strong>Date Range:</strong> {earliest} to {latest}</div>")
    parts.append(f"<div><strong>Reply Rate:</strong> {stats['reply_rate']}%</div>")
    parts.append(
        f"<div><strong>Avg Length:</strong> {int(stats.get('avg_message_length', 0))} characters</div>"
    )
    parts.append(
        f"<div><strong>Avg Words:</strong> {stats.get('avg_word_count', 0)}</div>"
    )

    if stats.get("conversation"):
        conv = stats["conversation"]
        parts.append(
            f"<div><strong>Threads:</strong> {conv['thread_count']} total / {conv['avg_thread_length']:.1f} avg length / {conv['max_thread_length']} max length</div>"
        )
        if conv["avg_response_time"] > 0:
            parts.append(
                f"<div><strong>Response Time:</strong> {format_duration(conv['avg_response_time'])} average / {format_duration(conv['min_response_time'])} fastest</div>"
            )
    parts.append("</div>")

    def render_html_bar_chart(title, items, label_key, count_key):
        if not items:
            return
        parts.append('<div class="stats-box">')
        parts.append(f"<h3>{title}</h3>")
        max_count = max(item[count_key] for item in items)
        for item in items[:5]:
            width = int(item[count_key] * 100 / max_count) if max_count > 0 else 0
            label = str(item[label_key])
            parts.append('<div class="stats-bar-container">')
            parts.append(
                f'<div class="stats-bar-label" title="{html.escape(label)}">{html.escape(label)}</div>'
            )
            parts.append(f'<div class="stats-bar-count">{item[count_key]}</div>')
            parts.append(f'<div class="stats-bar" style="width: {width}%"></div>')
            parts.append("</div>")
        parts.append("</div>")

    parts.append('<div class="stats-grid">')

    dist = _get_stats_distributions(stats)

    render_html_bar_chart("Top Authors", stats.get("authors"), "name", "count")
    render_html_bar_chart("Top Recipients", stats.get("recipients"), "name", "count")
    render_html_bar_chart("Top BBSes", stats.get("bbses"), "name", "count")
    render_html_bar_chart("Top Conferences", dist.get("conferences"), "name", "count")

    render_html_bar_chart("Top Subjects", stats.get("subjects"), "subject", "count")
    render_html_bar_chart("Top Keywords", stats.get("keywords"), "word", "count")
    render_html_bar_chart("Top Links", stats.get("links"), "url", "count")
    render_html_bar_chart("Top Emails", stats.get("emails"), "email", "count")
    render_html_bar_chart("Top Phones", stats.get("phones"), "phone", "count")
    render_html_bar_chart(
        "Top Attachments", stats.get("top_attachments"), "name", "count"
    )
    render_html_bar_chart(
        "Top Attachment Types", stats.get("top_attachment_types"), "extension", "count"
    )

    if stats.get("conversation") and stats["conversation"].get("top_responders"):
        items = [
            {"name": r["name"], "count": r["count"], "speed": r["avg_speed"]}
            for r in stats["conversation"]["top_responders"]
        ]

        def render_responders_chart(title, items):
            parts.append('<div class="stats-box">')
            parts.append(f"<h3>{title}</h3>")
            max_count = max(item["count"] for item in items)

            for item in items[:5]:
                width = int(item["count"] * 100 / max_count) if max_count > 0 else 0
                label = f"{item['name']} ({format_duration(item['speed'])})"
                parts.append('<div class="stats-bar-container">')
                parts.append(
                    f'<div class="stats-bar-label" title="{html.escape(label)}">{html.escape(label)}</div>'
                )
                parts.append(f'<div class="stats-bar-count">{item["count"]}</div>')
                parts.append(f'<div class="stats-bar" style="width: {width}%"></div>')
                parts.append("</div>")
            parts.append("</div>")

        render_responders_chart("Fastest Responders", items)

    # Activity Distributions
    render_html_bar_chart("Yearly Activity", dist.get("years"), "label", "count")
    render_html_bar_chart("Monthly Activity", dist.get("months"), "label", "count")
    render_html_bar_chart("Day of Week Distribution", dist.get("days"), "label", "count")
    render_html_bar_chart("Hourly Distribution", dist.get("hours"), "label", "count")

    parts.append("</div>")  # stats-grid
    parts.append("</div>")  # stats-container
    return parts


def _render_single_message_html(
    message: ProcessedMessage,
    msg_id: str | None = None,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
    prev_id: str | None = None,
    next_id: str | None = None,
    parent_id: str | None = None,
    toc_id: str | None = None,
    embed_attachments: bool = False,
) -> list[str]:
    """Render a single message into HTML components with quote highlighting."""
    parts = []
    # Use msg_id if provided, otherwise fallback to stable anchor format
    stable_anchor = f"msg-{message.confnum}-{message.header.msgnum}" if message.header.msgnum is not None else None

    id_attr = f' id="{msg_id}"' if msg_id else ""
    parts.append(f'<div class="message"{id_attr}>')

    if stable_anchor and msg_id != stable_anchor:
        # If we used a custom msg_id (like msg-0, msg-1), also provide the stable anchor
        parts.append(f'<a id="{stable_anchor}"></a>')

    # Navigation bar
    nav_links = []
    if parent_id:
        nav_links.append(f'<a href="#{parent_id}">Parent</a>')
    if prev_id:
        nav_links.append(f'<a href="#{prev_id}">Previous</a>')
    if next_id:
        nav_links.append(f'<a href="#{next_id}">Next</a>')
    if toc_id:
        nav_links.append(f'<a href="#{toc_id}">Contents</a>')

    if nav_links:
        parts.append('<div class="message-nav">')
        parts.append(" | ".join(nav_links))
        parts.append("</div>")

    def h_esc(text: str) -> str:
        return _linkify_text(
            text,
            "html",
            conf_num=message.confnum,
            search_term=search_term,
            is_regex=is_regex,
        )

    # Header
    header = message.header
    parts.append('<div class="header">')
    parts.append(
        f"<div><strong>Date:</strong> {html.escape(header.msgdate)} {html.escape(header.msgtime)}</div>"
    )
    parts.append(f"<div><strong>From:</strong> {h_esc(header.msgfrom)}</div>")
    parts.append(f"<div><strong>To:</strong> {h_esc(header.msgto)}</div>")
    parts.append(f"<div><strong>Subject:</strong> {h_esc(header.msgsubject)}</div>")

    conf_name = message.confname or f"Conference {header.confnum}"
    parts.append(
        f"<div><strong>Conference:</strong> {h_esc(conf_name)} ({header.confnum})</div>"
    )

    if message.bbs_name:
        parts.append(f"<div><strong>BBS:</strong> {h_esc(message.bbs_name)}</div>")
    if message.source_file:
        parts.append(
            f"<div><strong>Source:</strong> {h_esc(message.source_file)}</div>"
        )

    if header.msgnum is not None:
        parts.append(f"<div><strong>Number:</strong> {header.msgnum}</div>")

    if message.attachments:
        links = []
        for filename in message.attachments:
            if attachment_prefix:
                links.append(
                    f'<a href="{attachment_prefix}{html.escape(filename)}">{html.escape(filename)}</a>'
                )
            else:
                links.append(html.escape(filename))
        parts.append(f"<div><strong>Attachments:</strong> {', '.join(links)}</div>")

    if embed_attachments:
        text_to_scan = message.original_text or message.text
        found_binaries = extract_binaries(text_to_scan) if text_to_scan else []
        for filename, data in found_binaries:
            ext = os.path.splitext(filename.lower())[1]
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                mime_type = {
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }.get(ext, "image/jpeg")

                b64_data = base64.b64encode(data).decode("ascii")
                parts.append(
                    f'<div><img src="data:{mime_type};base64,{b64_data}" '
                    f'alt="{html.escape(filename)}" '
                    'style="max-width: 100%; height: auto; margin-top: 1em; border: 1px solid #ddd;" /></div>'
                )

    parts.append("</div>")

    # Body
    parts.append('<pre class="body">')

    body_text = message.text.replace("\r\n", "\n")
    body_lines = body_text.split("\n")
    processed_lines = []

    for line in body_lines:
        is_quote = bool(RE_QUOTE_PATTERN.match(line))
        highlighted_line = h_esc(line)
        if is_quote:
            processed_lines.append(f'<span class="quote">{highlighted_line}</span>')
        else:
            processed_lines.append(highlighted_line)

    parts.append("\n".join(processed_lines))
    parts.append("</pre>")
    parts.append("</div>")

    return parts


def _serialize_message_html(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
    embed_attachments: bool = False,
) -> str:
    """Convert a single message to an HTML string."""
    title = f"Search Results for '{search_term}'" if search_term else "QWK Message"
    html_parts = _get_html_header(title)
    html_parts.extend(
        _render_single_message_html(
            message,
            attachment_prefix=attachment_prefix,
            search_term=search_term,
            is_regex=is_regex,
            embed_attachments=embed_attachments,
        )
    )
    html_parts.extend(_get_html_footer())

    return "\n".join(html_parts)


def _escape_markdown(text: Any) -> str:
    """Escape special characters for Markdown tables and links."""
    return (
        str(text or "")
        .replace("|", "\\|")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _render_stats_markdown(stats: dict[str, Any]) -> list[str]:
    """Render a statistics summary as a Markdown fragment."""
    parts = []
    parts.append("### Archive Summary\n")

    parts.append(
        f"- **Messages:** {stats['matching_messages']} matching / {stats['total_messages']} total"
    )
    if stats["dates"]["earliest"]:
        earliest = datetime.datetime.fromisoformat(stats["dates"]["earliest"]).strftime(
            "%Y-%m-%d"
        )
        latest = datetime.datetime.fromisoformat(stats["dates"]["latest"]).strftime(
            "%Y-%m-%d"
        )
        parts.append(f"- **Date Range:** {earliest} to {latest}")
    parts.append(f"- **Reply Rate:** {stats['reply_rate']}%")
    parts.append(
        f"- **Avg Length:** {int(stats.get('avg_message_length', 0))} characters"
    )
    parts.append(f"- **Avg Words:** {stats.get('avg_word_count', 0)}")

    if stats.get("conversation"):
        conv = stats["conversation"]
        parts.append(
            f"- **Conversation:** {conv['thread_count']} threads / {conv['avg_thread_length']:.1f} avg length"
        )
        if conv["avg_response_time"] > 0:
            parts.append(
                f"- **Response Time:** {format_duration(conv['avg_response_time'])} avg / {format_duration(conv['min_response_time'])} fastest"
            )
    parts.append("")

    def render_md_bar_chart(title, items, label_key, count_key):
        if not items:
            return
        parts.append(f"#### {title}\n")
        parts.append(f"| {label_key.capitalize()} | Count | |")
        parts.append("|---|---|---|")
        max_count = max(item[count_key] for item in items)
        for item in items[:5]:
            bar_len = int(item[count_key] * 20 / max_count) if max_count > 0 else 0
            bar = "#" * bar_len
            label = _escape_markdown(item[label_key])
            parts.append(f"| {label} | {item[count_key]} | `{bar}` |")
        parts.append("")

    dist = _get_stats_distributions(stats)

    render_md_bar_chart("Top Authors", stats.get("authors"), "name", "count")
    render_md_bar_chart("Top Recipients", stats.get("recipients"), "name", "count")
    render_md_bar_chart("Top BBSes", stats.get("bbses"), "name", "count")
    render_md_bar_chart("Top Conferences", dist.get("conferences"), "name", "count")

    render_md_bar_chart("Top Subjects", stats.get("subjects"), "subject", "count")
    render_md_bar_chart("Top Keywords", stats.get("keywords"), "word", "count")
    render_md_bar_chart("Top Links", stats.get("links"), "url", "count")
    render_md_bar_chart("Top Emails", stats.get("emails"), "email", "count")
    render_md_bar_chart("Top Phones", stats.get("phones"), "phone", "count")
    render_md_bar_chart(
        "Top Attachments", stats.get("top_attachments"), "name", "count"
    )
    render_md_bar_chart(
        "Top Attachment Types", stats.get("top_attachment_types"), "extension", "count"
    )

    if stats.get("conversation") and stats["conversation"].get("top_responders"):
        items = stats["conversation"]["top_responders"]
        parts.append("#### Fastest Responders\n")
        parts.append("| Name | Replies | Avg Speed | |")
        parts.append("|---|---|---|---|")
        max_count = max(item["count"] for item in items)

        for item in items[:5]:
            bar_len = int(item["count"] * 20 / max_count) if max_count > 0 else 0
            bar = "#" * bar_len
            name = _escape_markdown(item["name"])
            speed = format_duration(item["avg_speed"])
            parts.append(f"| {name} | {item['count']} | {speed} | `{bar}` |")
        parts.append("")

    # Activity Distributions
    render_md_bar_chart("Yearly Activity", dist.get("years"), "label", "count")
    render_md_bar_chart("Monthly Activity", dist.get("months"), "label", "count")
    render_md_bar_chart("Day of Week Distribution", dist.get("days"), "label", "count")
    render_md_bar_chart("Hourly Distribution", dist.get("hours"), "label", "count")

    parts.append("---\n")
    return parts


def _render_single_message_markdown(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
    msg_id: str | None = None,
    prev_id: str | None = None,
    next_id: str | None = None,
    parent_id: str | None = None,
    toc_id: str | None = None,
) -> list[str]:
    """Render a single message into Markdown with blockquote standardization."""
    header = message.header
    parts = []

    def md_high(text: str) -> str:
        return _linkify_text(
            text,
            "markdown",
            conf_num=message.confnum,
            search_term=search_term,
            is_regex=is_regex,
        )

    msg_anchor = ""
    if msg_id:
        msg_anchor += f' <a name="{msg_id}"></a>'
    if header.msgnum is not None:
        msg_anchor += f' <a name="msg-{message.confnum}-{header.msgnum}"></a>'

    parts.append(f"## {md_high(header.msgsubject)}{msg_anchor}")
    parts.append(f"- **Date:** {header.msgdate} {header.msgtime}")
    parts.append(f"- **From:** {md_high(header.msgfrom)}")
    parts.append(f"- **To:** {md_high(header.msgto)}")

    conf_name = message.confname or f"Conference {header.confnum}"
    parts.append(f"- **Conference:** {md_high(conf_name)} ({header.confnum})")

    if message.bbs_name:
        parts.append(f"- **BBS:** {md_high(message.bbs_name)}")
    if message.source_file:
        parts.append(f"- **Source:** {md_high(message.source_file)}")

    if header.msgnum is not None:
        parts.append(f"- **Number:** {header.msgnum}")

    # Navigation bar
    nav_links = []
    if parent_id:
        nav_links.append(f"[Parent](#{parent_id})")
    if prev_id:
        nav_links.append(f"[Previous](#{prev_id})")
    if next_id:
        nav_links.append(f"[Next](#{next_id})")
    if toc_id:
        nav_links.append(f"[Contents](#{toc_id})")

    if nav_links:
        parts.append(" | ".join(nav_links))

    if message.attachments:
        links = []
        for filename in message.attachments:
            if attachment_prefix:
                # Markdown link format [label](url)
                links.append(f"[{filename}]({attachment_prefix}{filename})")
            else:
                links.append(filename)
        parts.append(f"- **Attachments:** {', '.join(links)}")

    parts.append("")

    body_text = message.text.replace("\r\n", "\n")
    body_lines = body_text.split("\n")
    processed_lines = []

    for line in body_lines:
        is_quote = bool(RE_QUOTE_PATTERN.match(line))
        highlighted_line = md_high(line)
        if is_quote:
            # Standardize to use '> ' for blockquotes if it's not already starting with it
            if not highlighted_line.startswith(">"):
                processed_lines.append(f"> {highlighted_line}")
            else:
                processed_lines.append(highlighted_line)
        else:
            processed_lines.append(highlighted_line)

    parts.append("\n".join(processed_lines))
    parts.append("")
    parts.append("---")
    return parts


def _serialize_message_markdown(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> str:
    """Convert a single message to a Markdown string."""
    title = f"Search Results for '{search_term}'" if search_term else "QWK Message"
    md_parts = [f"# {title}\n"]
    md_parts.extend(
        _render_single_message_markdown(
            message,
            attachment_prefix=attachment_prefix,
            search_term=search_term,
            is_regex=is_regex,
        )
    )
    return "\n".join(md_parts)


def _write_html(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    title = "QWK Messages"
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Archive"

    if settings and settings.search_term:
        title = f"Search Results for '{settings.search_term}' - {title}"

    search_term = settings.search_term if settings else None
    is_regex = settings.regex if settings else False

    html_parts = _get_html_header(title)
    attachment_prefix = (
        "attachments/" if settings and settings.extract_attachments else None
    )

    if settings and settings.include_toc:
        html_parts.append(f'<h1 id="top">{html.escape(title)}</h1>')

        # Add Statistics Summary
        stats = _compute_stats_from_messages(iter(messages))
        html_parts.extend(_render_stats_html(stats))

        if bbs_info:
            html_parts.append('<div class="bbs-info">')
            if bbs_info.sysop:
                html_parts.append(
                    f"<div><strong>SysOp:</strong> {html.escape(bbs_info.sysop)}</div>"
                )
            if bbs_info.location:
                html_parts.append(
                    f"<div><strong>Location:</strong> {html.escape(bbs_info.location)}</div>"
                )
            if bbs_info.packet_at:
                html_parts.append(
                    f"<div><strong>Packet Date:</strong> {html.escape(bbs_info.packet_at)}</div>"
                )
            user_name_to_show = (settings.my_name if settings else None) or bbs_info.user_name
            if user_name_to_show:
                html_parts.append(
                    f"<div><strong>User Name:</strong> {html.escape(user_name_to_show)}</div>"
                )
            html_parts.append(
                f"<div><strong>Total Messages:</strong> {len(messages)}</div>"
            )
            html_parts.append("</div>")

        html_parts.append("<h2>Conferences</h2>")
        html_parts.append("<ul>")
        seen_confs = set()
        for i, msg in enumerate(messages):
            if msg.confnum not in seen_confs:
                conf_name = msg.confname or f"Conference {msg.confnum}"
                html_parts.append(
                    f'<li><a href="#conf-{msg.confnum}">{html.escape(conf_name)} (Conf {msg.confnum})</a></li>'
                )
                seen_confs.add(msg.confnum)
        html_parts.append("</ul>")
        html_parts.append("<hr>")

    current_depth = 0
    last_confnum = None

    for i, message in enumerate(messages):
        if settings and settings.include_toc and message.confnum != last_confnum:
            conf_name = message.confname or f"Conference {message.confnum}"
            html_parts.append(
                f'<h2 id="conf-{message.confnum}">{html.escape(conf_name)}</h2>'
            )
            last_confnum = message.confnum

        while current_depth < message.depth:
            html_parts.append('<div class="reply">')
            current_depth += 1
        while current_depth > message.depth:
            html_parts.append("</div>")
            current_depth -= 1

        msg_id = f"msg-{i}"
        prev_id = f"msg-{i-1}" if i > 0 else None
        next_id = f"msg-{i+1}" if i < len(messages) - 1 else None
        toc_id = "top" if settings and settings.include_toc else None
        parent_id = f"msg-{message.confnum}-{message.parent_msgnum}" if message.parent_msgnum else None

        html_parts.extend(
            _render_single_message_html(
                message,
                msg_id=msg_id,
                attachment_prefix=attachment_prefix,
                search_term=search_term,
                is_regex=is_regex,
                prev_id=prev_id,
                next_id=next_id,
                parent_id=parent_id,
                toc_id=toc_id,
                embed_attachments=settings.embed_attachments if settings else False,
            )
        )

    while current_depth > 0:
        html_parts.append("</div>")
        current_depth -= 1

    html_parts.extend(_get_html_footer())

    _write_text_output("\n".join(html_parts), output_path, encoding="utf-8")


def _write_markdown(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    title = "QWK Messages"
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Archive"

    if settings and settings.search_term:
        title = f"Search Results for '{settings.search_term}' - {title}"

    search_term = settings.search_term if settings else None
    is_regex = settings.regex if settings else False

    md_parts = [f'# {title} <a name="top"></a>\n']
    attachment_prefix = (
        "attachments/" if settings and settings.extract_attachments else None
    )

    if settings and settings.include_toc:
        # Add Statistics Summary
        stats = _compute_stats_from_messages(iter(messages))
        md_parts.extend(_render_stats_markdown(stats))

        if bbs_info:
            if bbs_info.sysop:
                md_parts.append(f"- **SysOp:** {bbs_info.sysop}")
            if bbs_info.location:
                md_parts.append(f"- **Location:** {bbs_info.location}")
            if bbs_info.packet_at:
                md_parts.append(f"- **Packet Date:** {bbs_info.packet_at}")
            user_name_to_show = (settings.my_name if settings else None) or bbs_info.user_name
            if user_name_to_show:
                md_parts.append(f"- **User Name:** {user_name_to_show}")
            md_parts.append(f"- **Total Messages:** {len(messages)}")
            md_parts.append("")

        md_parts.append("## Table of Contents\n")
        seen_confs = set()
        for msg in messages:
            if msg.confnum not in seen_confs:
                conf_name = msg.confname or f"Conference {msg.confnum}"
                # Create a markdown-friendly anchor name
                anchor = f"conf-{msg.confnum}"
                md_parts.append(f"- [{conf_name}](#{anchor})")
                seen_confs.add(msg.confnum)
        md_parts.append("\n---\n")

    last_confnum = None
    for i, message in enumerate(messages):
        if settings and settings.include_toc and message.confnum != last_confnum:
            conf_name = message.confname or f"Conference {message.confnum}"
            md_parts.append(f'## {conf_name} <a name="conf-{message.confnum}"></a>\n')
            last_confnum = message.confnum

        msg_id = f"msg-{i}"
        prev_id = f"msg-{i-1}" if i > 0 else None
        next_id = f"msg-{i+1}" if i < len(messages) - 1 else None
        toc_id = "top" if settings and settings.include_toc else None
        parent_id = f"msg-{message.confnum}-{message.parent_msgnum}" if message.parent_msgnum else None

        single_md = _render_single_message_markdown(
            message,
            attachment_prefix=attachment_prefix,
            search_term=search_term,
            is_regex=is_regex,
            msg_id=msg_id,
            prev_id=prev_id,
            next_id=next_id,
            parent_id=parent_id,
            toc_id=toc_id,
        )
        if message.depth > 0:
            prefix = "> " * message.depth
            indented_md = []
            for line in single_md:
                indented_md.append(f"{prefix}{line}".rstrip())
            md_parts.extend(indented_md)
        else:
            md_parts.extend(single_md)
        md_parts.append("")

    _write_text_output("\n".join(md_parts), output_path, encoding="utf-8")


def _parse_qwk_date(msgdate: str, msgtime: str) -> datetime.datetime:
    """Convert a QWK date and time into a standard Python datetime object.

    If the date is invalid, it returns a default date of 1970-01-01.
    """
    try:
        # Handle ISO 8601 format (used in SQLite exports)
        if "T" in msgdate:
            return datetime.datetime.fromisoformat(msgdate)

        # Normalize date separators
        msgdate = msgdate.replace("/", "-")
        date_parts = msgdate.split("-")

        if len(date_parts[0]) == 4:
            # ISO format: YYYY-MM-DD
            year, month, day = map(int, date_parts)
        else:
            # Traditional format: MM-DD-YY
            month, day, year = map(int, date_parts)

            # Handle Year 2000 problem using a sliding window.
            # BBS activity peaked in the 1980s and 1990s. We use 80 as a cutoff:
            # years 80-99 are 1980-1999, while 00-79 are 2000-2079.
            if year < 100:
                if year < 80:
                    year += 2000
                else:
                    year += 1900

        time_parts = list(map(int, msgtime.split(":")))
        hour = time_parts[0]
        minute = time_parts[1]
        second = time_parts[2] if len(time_parts) > 2 else 0

        return datetime.datetime(year, month, day, hour, minute, second)
    except (ValueError, IndexError):
        # Fallback for invalid dates
        return datetime.datetime(1970, 1, 1, 0, 0)


def _serialize_rfc822(
    message: ProcessedMessage, include_mbox_header: bool = True
) -> str:
    """Convert a message to RFC 822 (Email) format with optional MBOX header.

    Includes standard email headers for conversations (Message-ID, In-Reply-To, References)
    and custom X-QWK headers for conference names, message numbers, and statuses.
    Attachments found in the text are converted into proper MIME parts.
    """
    from email.message import EmailMessage

    header = message.header
    dt = _parse_qwk_date(header.msgdate, header.msgtime)
    rfc_date = email.utils.format_datetime(dt)

    # 1. Identify and extract attachments from the body
    # We remove them from the text part so the email looks modern
    text_to_scan = message.original_text or message.text
    found_binaries = extract_binaries(text_to_scan) if text_to_scan else []

    # Process body lines: remove binaries and escape "From " for mbox compatibility
    body_lines = (message.text or "").splitlines()
    new_body_lines = []
    in_y = in_u = in_b = False
    prev_line = None

    for line in body_lines:
        if found_binaries:
            # Re-use the logic from process_message for binaries removal
            should_skip, in_y, in_u, in_b = _is_binary_line(
                line, prev_line, in_y, in_u, in_b
            )
            if should_skip:
                prev_line = line
                continue

        # Escape "From " lines in body for mbox compatibility
        if line.startswith("From "):
            new_body_lines.append(">" + line)
        else:
            new_body_lines.append(line)
        prev_line = line

    clean_body = "\n".join(new_body_lines)

    # 2. Build the EmailMessage
    msg = EmailMessage()

    msg["From"] = header.msgfrom
    msg["To"] = header.msgto
    msg["Subject"] = header.msgsubject
    msg["Date"] = rfc_date

    msg_id = f"<{header.confnum}.{header.msgnum if header.msgnum is not None else 'x'}@qwk>"
    msg["Message-ID"] = msg_id

    if message.parent_msgnum is not None:
        parent_id = f"<{header.confnum}.{message.parent_msgnum}@qwk>"
        msg["In-Reply-To"] = parent_id
        msg["References"] = parent_id

    # QWK Information headers
    msg["X-QWK-Conference"] = str(header.confnum)
    if message.confname:
        msg["X-QWK-Conference-Name"] = message.confname
    if message.bbs_name:
        msg["X-QWK-BBS-Name"] = message.bbs_name
    if message.bbs_id:
        msg["X-QWK-BBS-ID"] = message.bbs_id
    if message.source_file:
        msg["X-QWK-Source-File"] = message.source_file
    if header.msgnum is not None:
        msg["X-QWK-Message-Number"] = str(header.msgnum)
    if header.status.strip():
        msg["X-QWK-Status"] = header.status
    if header.msgflag.strip():
        msg["X-QWK-Flags"] = header.msgflag
    if header.refnum is not None:
        msg["X-QWK-Reference"] = str(header.refnum)
    if message.attachments:
        msg["X-QWK-Attachments"] = ";".join(message.attachments)
    if message.depth > 0:
        msg["X-QWK-Depth"] = str(message.depth)
    if message.thread_id:
        msg["X-QWK-Thread-ID"] = message.thread_id
    if message.parent_msgnum is not None:
        msg["X-QWK-Parent-Msgnum"] = str(message.parent_msgnum)

    msg.set_content(clean_body)

    # 3. Add MIME attachments
    for filename, data in found_binaries:
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=filename or "attachment.bin",
        )

    # 4. Handle mbox "From " line if needed
    output = msg.as_string()
    if include_mbox_header:
        from_line_date = dt.ctime()
        sender_addr = header.msgfrom
        if "@" not in sender_addr:
            safe_name = re.sub(r"[^A-Za-z0-9]", ".", sender_addr).strip(".")
            sender_addr = f"{safe_name}@example.com"
        output = f"From {sender_addr} {from_line_date}\n" + output

    return output


def _write_mbox(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to an mbox file."""
    parts = [_serialize_rfc822(msg, include_mbox_header=True) for msg in messages]
    _write_text_output("\n".join(parts), output_path, encoding=encoding)


def _write_eml(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages as EML.

    If multiple messages are provided and no individual files are requested,
    they are aggregated with double newlines, effectively becoming a text-based collection.
    """
    parts = [_serialize_rfc822(msg, include_mbox_header=False) for msg in messages]
    _write_text_output("\n\n".join(parts), output_path, encoding=encoding)


def _write_maildir(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to a Maildir."""
    if output_path is None:
        raise ValueError("Output path is required for Maildir export.")

    mdir = mailbox.Maildir(output_path, create=True)
    for message in messages:
        rfc822_content = _serialize_rfc822(message, include_mbox_header=False)
        mdir.add(rfc822_content.encode(encoding))
    mdir.close()


def _serialize_control_dat(
    bbs_info: BBSInfo | None,
    board_dict: Mapping[int, str] | None,
    encoding: str = "cp437",
    my_name: str | None = None,
) -> list[bytes]:
    """Convert BBS information and conference list into CONTROL.DAT format."""
    lines = [b""] * 11
    if bbs_info:
        lines[0] = bbs_info.name.encode(encoding)
        lines[1] = bbs_info.location.encode(encoding)
        lines[2] = bbs_info.phone.encode(encoding)
        lines[3] = bbs_info.sysop.encode(encoding)

        id_line = f"{bbs_info.serial_number},{bbs_info.bbs_id}"
        lines[4] = id_line.encode(encoding)

        lines[5] = bbs_info.packet_at.encode(encoding)
        user_name_val = my_name or bbs_info.user_name
        lines[6] = user_name_val.encode(encoding)

    if board_dict:
        # Line 11 (index 10) is number of conferences - 1
        lines[10] = str(len(board_dict) - 1).encode(encoding)
        for conf_num, conf_name in sorted(board_dict.items()):
            lines.append(str(conf_num).encode(encoding))
            lines.append(conf_name.encode(encoding))
    else:
        lines[10] = b"-1"

    return lines


def _text_to_qwk_blocks(text: str, encoding: str = "cp437") -> bytes:
    """Convert message text into 128-byte QWK blocks with \xe3 newlines."""
    # QWK uses \xe3 (227) as a newline character
    qwk_text = text.replace("\r\n", "\xe3").replace("\n", "\xe3")
    encoded = qwk_text.encode(encoding, errors="replace")

    # Pad to 128-byte boundary
    padding_len = (BLOCK_SIZE - (len(encoded) % BLOCK_SIZE)) % BLOCK_SIZE
    return encoded + (b" " * padding_len)


def _write_text(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to text format with indentation for conversations."""
    parts = []

    use_colors = (
        not output_path and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    )

    if settings and settings.oneline and not settings.oneline_pattern:
        msgnum_hdr = f"{'Num':<6} " if settings.verbose else ""
        conf_hdr = f"{'Conference':<12}"
        date_hdr = f"{'Date':<14}"
        from_hdr = f"{'From':<15}"
        to_hdr = f"{'To':<15}"
        # "Flg" header for the new 3-character flags column
        subj_hdr = "Flg Subject"

        BOLD = "1"
        header_line = (
            f"{_colorize(msgnum_hdr, BOLD, enabled=use_colors)}"
            f"{_colorize(conf_hdr, BOLD, enabled=use_colors)} "
            f"{_colorize(date_hdr, BOLD, enabled=use_colors)} "
            f"{_colorize(from_hdr, BOLD, enabled=use_colors)} "
            f"{_colorize(to_hdr, BOLD, enabled=use_colors)} "
            f"{_colorize(subj_hdr, BOLD, enabled=use_colors)}\r\n"
        )
        parts.append(header_line)
        # Calculate separator length from the plain text header
        plain_header = (
            f"{msgnum_hdr}{conf_hdr} {date_hdr} {from_hdr} {to_hdr} {subj_hdr}"
        )
        separator_line = "-" * len(plain_header) + "\r\n"
        parts.append(_colorize(separator_line, "90", enabled=use_colors))

    if settings and settings.include_toc:
        title = "QWK Message Archive"
        if bbs_info and bbs_info.name:
            title = f"{bbs_info.name} Archive"

        parts.append("=" * 80 + "\r\n")
        parts.append(f"{title}\r\n")
        parts.append("=" * 80 + "\r\n")
        if bbs_info:
            if bbs_info.sysop:
                parts.append(f"SysOp:    {bbs_info.sysop}\r\n")
            if bbs_info.location:
                parts.append(f"Location: {bbs_info.location}\r\n")
            if bbs_info.packet_at:
                parts.append(f"Date:     {bbs_info.packet_at}\r\n")
            user_name_to_show = (settings.my_name if settings else None) or bbs_info.user_name
            if user_name_to_show:
                parts.append(f"User:     {user_name_to_show}\r\n")
        parts.append(f"Messages: {len(messages)}\r\n\r\n")

        parts.append("Conferences:\r\n")
        seen_confs = set()
        conf_counts = Counter(m.confnum for m in messages)
        for msg in messages:
            if msg.confnum not in seen_confs:
                conf_name = msg.confname or f"Conference {msg.confnum}"
                count = conf_counts[msg.confnum]
                parts.append(f"  {msg.confnum:3}: {conf_name} ({count} messages)\r\n")
                seen_confs.add(msg.confnum)
        separator_line = "-" * 80 + "\r\n\r\n"
        parts.append(_colorize(separator_line, "90", enabled=use_colors))

    for i, message in enumerate(messages):
        if settings and settings.oneline:
            user_name_to_pass = (
                settings.my_name
                if settings
                else (bbs_info.user_name if bbs_info else None)
            )
            text = _render_message_oneline(
                message,
                settings,
                i + 1,
                use_colors,
                {},
                user_name_to_pass,
            )
        else:
            text = message.text

            # Apply quote highlighting for terminal output
            text = _highlight_quotes(text, use_colors)

            # Apply indentation for conversations
            if message.depth > 0:
                indent = "  " * message.depth
                lines = text.splitlines(keepends=True)
                indented_lines = [indent + line for line in lines]
                text = "".join(indented_lines)
        parts.append(text)

    _write_text_output("".join(parts), output_path, encoding=encoding)


def _write_csv(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    output = io.StringIO()

    header_fields = [f.name for f in fields(MessageHeader)]
    fieldnames = header_fields + [
        "conference_name",
        "bbs_name",
        "bbs_id",
        "source_file",
        "text",
        "depth",
        "thread_id",
        "parent_msgnum",
        "attachments",
    ]

    writer = csv.DictWriter(
        output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar="\\"
    )
    writer.writeheader()

    for message in messages:
        row = message.header.as_dict
        row["conference_name"] = message.confname
        row["bbs_name"] = message.bbs_name
        row["bbs_id"] = message.bbs_id
        row["source_file"] = message.source_file
        row["text"] = message.text
        row["depth"] = message.depth
        row["thread_id"] = message.thread_id
        row["parent_msgnum"] = message.parent_msgnum
        row["attachments"] = ";".join(message.attachments or [])
        writer.writerow(row)

    _write_text_output(output.getvalue(), output_path, encoding=encoding)


def _write_qwk(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "cp437",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Export messages to a QWK/REP archive (ZIP file)."""
    if output_path is None:
        raise ValueError("Output path is required for QWK/REP export.")

    is_rep = output_path.lower().endswith(".rep")

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        content = bytearray()
        if is_rep:
            # First block is BBS ID
            bbs_id = (bbs_info.bbs_id if bbs_info else "") or "QWK"
            header_block = bbs_id.ljust(BLOCK_SIZE)
        else:
            # First block is "Produced by pyqwk"
            header_block = "Produced by pyqwk".ljust(BLOCK_SIZE)

        content.extend(header_block.encode(encoding)[:BLOCK_SIZE])

        for msg in messages:
            body_blocks = _text_to_qwk_blocks(msg.text, encoding)
            num_blocks = (len(body_blocks) // BLOCK_SIZE) + 1
            header = replace(msg.header, numblocks=num_blocks)
            content.extend(header.to_bytes(encoding))
            content.extend(body_blocks)

        if is_rep:
            zf.writestr(REPLY_FILENAME, content)
        else:
            zf.writestr(MESSAGES_FILENAME, content)

            # CONTROL.DAT
            control_lines = _serialize_control_dat(
                bbs_info,
                board_dict,
                encoding,
                my_name=settings.my_name if settings else None,
            )
            zf.writestr(CONTROL_FILENAME, b"\r\n".join(control_lines) + b"\r\n")


def _write_sqlite(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = "utf-8",
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    if output_path is None:
        raise ValueError("Output path is required for SQLite export.")

    conn = sqlite3.connect(output_path)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS bbs_info (
            name TEXT,
            location TEXT,
            phone TEXT,
            sysop TEXT,
            serial_number TEXT,
            bbs_id TEXT,
            user_name TEXT,
            packet_at TEXT,
            total_messages INTEGER,
            num_conferences INTEGER
        )
    """)

    if bbs_info:
        c.execute(
            """
            INSERT INTO bbs_info (
                name, location, phone, sysop, serial_number, bbs_id,
                user_name, packet_at, total_messages, num_conferences
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                bbs_info.name,
                bbs_info.location,
                bbs_info.phone,
                bbs_info.sysop,
                bbs_info.serial_number,
                bbs_info.bbs_id,
                bbs_info.user_name,
                bbs_info.packet_at,
                bbs_info.total_messages,
                bbs_info.num_conferences,
            ),
        )

    c.execute("""
        CREATE TABLE IF NOT EXISTS conferences (
            number INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    if board_dict:
        for conf_num, conf_name in board_dict.items():
            c.execute(
                """
                INSERT OR REPLACE INTO conferences (number, name)
                VALUES (?, ?)
            """,
                (conf_num, conf_name),
            )

    for msg in messages:
        header = msg.header
        dt = _parse_qwk_date(header.msgdate, header.msgtime)
        iso_date = dt.isoformat()

        c.execute(
            """
            INSERT INTO messages (
                conference_number, message_number, date, author, recipient,
                subject, status, text, reference_number, thread_id, depth,
                parent_message_number, conference_name, bbs_name, bbs_id, source_file,
                attachments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                header.confnum,
                header.msgnum,
                iso_date,
                header.msgfrom,
                header.msgto,
                header.msgsubject,
                header.status,
                msg.text,
                header.refnum,
                msg.thread_id,
                msg.depth,
                msg.parent_msgnum,
                msg.confname,
                msg.bbs_name,
                msg.bbs_id,
                msg.source_file,
                ";".join(msg.attachments or []),
            ),
        )

    conn.commit()
    conn.close()


def write_messages(
    messages: list[ProcessedMessage],
    output_path: str | None,
    settings: ProcessingSettings,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Save a list of messages to a file or print them to the screen.

    This function selects the appropriate writer based on the settings and
    handles the text encoding for the output.
    """
    writers: dict[
        str,
        Callable[
            [
                list[ProcessedMessage],
                str | None,
                str,
                ProcessingSettings,
                BBSInfo | None,
                Mapping[int, str] | None,
            ],
            None,
        ],
    ] = {
        "json": _write_json,
        "jsonl": _write_jsonl,
        "xml": _write_xml,
        "rss": _write_rss,
        "html": _write_html,
        "markdown": _write_markdown,
        "text": _write_text,
        "csv": _write_csv,
        "mbox": _write_mbox,
        "eml": _write_eml,
        "maildir": _write_maildir,
        "sqlite": _write_sqlite,
        "qwk": _write_qwk,
        "rep": _write_qwk,
    }

    writer = writers.get(settings.format, _write_text)
    output_encoding = "utf-8"
    if settings.format == "text":
        output_encoding = settings.encoding

    writer(messages, output_path, output_encoding, settings, bbs_info, board_dict)


def _write_index(
    collected_info: list[dict[str, Any]],
    output_dir: str | None,
    settings: ProcessingSettings,
    bbs_info: BBSInfo | None = None,
    stats: dict[str, Any] | None = None,
) -> None:
    """Generate a browsable index (HTML or Markdown) for individual message files."""
    if not output_dir or not collected_info:
        return

    # Group by conference
    by_conf = defaultdict(list)
    for info in collected_info:
        by_conf[(info["conf_num"], info["conf_name"])].append(info)

    title = "Message Archive"
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Message Archive"

    if settings.format == "html":
        _write_html_index(by_conf, title, output_dir, stats=stats)
    elif settings.format == "markdown":
        _write_markdown_index(by_conf, title, output_dir, stats=stats)


def _write_html_index(
    by_conf: Mapping[tuple[int, str], list[dict[str, Any]]],
    title: str,
    output_dir: str,
    stats: dict[str, Any] | None = None,
) -> None:
    html_parts = _get_html_header(title)
    html_parts.append(f"<h1>{html.escape(title)}</h1>")

    if stats:
        html_parts.extend(_render_stats_html(stats))

    for (conf_num, conf_name), messages in sorted(by_conf.items()):
        html_parts.append(f"<h2>{html.escape(conf_name)} (Conference {conf_num})</h2>")
        html_parts.append("<table>")
        html_parts.append(
            "<thead><tr><th>#</th><th>Date</th><th>From</th><th>To</th><th>Subject</th><th>Attach</th></tr></thead>"
        )
        html_parts.append("<tbody>")
        for msg in messages:
            html_parts.append("<tr>")
            html_parts.append(f"<td>{msg['msgnum'] or ''}</td>")
            html_parts.append(f"<td>{html.escape(msg['date'])}</td>")
            html_parts.append(f"<td>{html.escape(msg['from'])}</td>")
            html_parts.append(f"<td>{html.escape(msg['to'])}</td>")

            indent = ""
            depth = msg.get("depth", 0)
            if depth > 0:
                indent = "&nbsp;&nbsp;" * (depth - 1) + "└&nbsp;"

            html_parts.append(
                f'<td>{indent}<a href="{html.escape(msg["path"])}">{html.escape(msg["subject"] or "(no subject)")}</a></td>'
            )
            attach_count = len(msg["attachments"]) if msg.get("attachments") else 0
            html_parts.append(f"<td>{attach_count if attach_count > 0 else ''}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")

    html_parts.extend(_get_html_footer())
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))


def _write_markdown_index(
    by_conf: Mapping[tuple[int, str], list[dict[str, Any]]],
    title: str,
    output_dir: str,
    stats: dict[str, Any] | None = None,
) -> None:
    md_parts = [f"# {title}\n"]

    if stats:
        md_parts.extend(_render_stats_markdown(stats))

    for (conf_num, conf_name), messages in sorted(by_conf.items()):
        md_parts.append(f"## {conf_name} (Conference {conf_num})\n")
        md_parts.append("| # | Date | From | To | Subject | Attach |")
        md_parts.append("|---|---|---|---|---|---|")
        for msg in messages:
            subj = _escape_markdown(msg["subject"] or "(no subject)")
            from_name = _escape_markdown(msg["from"])
            to_name = _escape_markdown(msg["to"])

            indent = ""
            depth = msg.get("depth", 0)
            if depth > 0:
                indent = "&nbsp;&nbsp;" * (depth - 1) + "└&nbsp;"

            attach_count = len(msg["attachments"]) if msg.get("attachments") else 0
            attach_str = str(attach_count) if attach_count > 0 else ""
            md_parts.append(
                f"| {msg['msgnum'] or ''} | {msg['date']} | {from_name} | {to_name} | {indent}[{subj}]({msg['path']}) | {attach_str} |"
            )
        md_parts.append("")

    index_path = os.path.join(output_dir, "README.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_parts))


def _write_text_output(
    content: str, output_path: str | None, *, encoding: str = "latin1"
) -> None:
    if output_path is None:
        if not content.endswith("\n"):
            content += "\n"
        sys.stdout.write(content)
    else:
        with open(output_path, "w", encoding=encoding) as f:
            f.write(content)


def _colorize(text: Any, *attributes: str, enabled: bool | None = None) -> str:
    """Apply ANSI color codes if the output is a terminal or explicitly enabled."""
    if enabled is True or (
        enabled is None and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    ):
        return f"\033[{';'.join(attributes)}m{text}\033[0m"
    return str(text)


def _highlight_quotes(text: str, use_colors: bool) -> str:
    """Apply green coloring to quoted lines in text for terminal output."""
    if not use_colors:
        return text

    lines = text.splitlines(keepends=True)
    highlighted_lines = []
    for line in lines:
        if RE_QUOTE_PATTERN.match(line):
            # Strip trailing newlines to place the reset code before them.
            content = line.rstrip("\r\n")
            ending = line[len(content) :]
            # ANSI Green (32)
            highlighted_lines.append(_colorize(content, "32", enabled=True) + ending)
        else:
            highlighted_lines.append(line)
    return "".join(highlighted_lines)


def _discover_entities(
    text: str, search_term: str | None = None, is_regex: bool = False
) -> list[tuple[int, int, str, str]]:
    """Find links, email addresses, phone numbers, and search matches in text.

    This function ensures that if a piece of text matches multiple patterns,
    only the most relevant one is used.

    Returns:
        A list of information about each match, including its start position,
        end position, type (like 'url' or 'email'), and the original text.
    """
    entities: list[tuple[int, int, str, str]] = []

    # 1. Search Matches
    if search_term:
        flags = re.IGNORECASE
        pattern_str = search_term if is_regex else re.escape(search_term)
        try:
            pattern = re.compile(pattern_str, flags)
            for match in pattern.finditer(text):
                entities.append((match.start(), match.end(), "search", match.group(0)))
        except re.error:
            pass

    # 2. Standard Entities
    for match in RE_URL_PATTERN.finditer(text):
        entities.append((match.start(), match.end(), "url", match.group(0)))
    for match in RE_EMAIL_PATTERN.finditer(text):
        entities.append((match.start(), match.end(), "email", match.group(0)))
    for match in RE_PHONE_PATTERN.finditer(text):
        entities.append((match.start(), match.end(), "phone", match.group(0)))
    for match in RE_MSG_LINK_PATTERN.finditer(text):
        entities.append((match.start(), match.end(), "msg_link", match.group(0)))

    # Sort entities: primary sort by start position (ascending),
    # secondary sort by end position (descending) to prefer longer matches.
    entities.sort(key=lambda x: (x[0], -x[1]))

    # Filter out overlaps
    filtered_entities: list[tuple[int, int, str, str]] = []
    last_end = 0
    for start, end, etype, evalue in entities:
        if start >= last_end:
            filtered_entities.append((start, end, etype, evalue))
            last_end = end

    return filtered_entities


def _linkify_text(
    text: str,
    output_format: str,
    conf_num: int | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
    use_colors: bool = False,
) -> str:
    """Turn links, email addresses, and phone numbers into clickable links or highlighted text.

    Args:
        text: The message text to process.
        output_format: The type of output to create ('html', 'markdown', or 'ansi' for terminal).
        conf_num: The conference number used to create links between messages.
        search_term: A keyword or pattern to highlight in the results.
        is_regex: Set to True if the search_term is a regular expression.
        use_colors: Set to True to use colors when printing to the terminal.
    """
    entities = _discover_entities(text, search_term, is_regex)

    if not entities:
        if output_format == "html":
            return html.escape(text)
        return text

    result = []
    last_end = 0

    def escape(t):
        if output_format == "html":
            return html.escape(t)
        return t

    for start, end, etype, evalue in entities:
        # Non-matching part
        result.append(escape(text[last_end:start]))

        # Matching part
        val_esc = escape(evalue)

        if etype == "search":
            if output_format == "html":
                result.append(f"<mark>{val_esc}</mark>")
            elif output_format == "markdown":
                result.append(f"**{val_esc}**")
            elif output_format == "ansi" and use_colors:
                result.append(_colorize(val_esc, "7", enabled=True))
            else:
                result.append(val_esc)
        elif etype == "url":
            uri = evalue if "://" in evalue.lower() else f"http://{evalue}"
            if output_format == "html":
                result.append(f'<a href="{html.escape(uri)}">{val_esc}</a>')
            elif output_format == "markdown":
                result.append(f"[{val_esc}]({uri})")
            elif output_format == "ansi" and use_colors:
                result.append(_colorize(val_esc, "4", "90", enabled=True))
            else:
                result.append(val_esc)
        elif etype == "email":
            uri = f"mailto:{evalue}"
            if output_format == "html":
                result.append(f'<a href="{html.escape(uri)}">{val_esc}</a>')
            elif output_format == "markdown":
                result.append(f"[{val_esc}]({uri})")
            elif output_format == "ansi" and use_colors:
                result.append(_colorize(val_esc, "4", "90", enabled=True))
            else:
                result.append(val_esc)
        elif etype == "phone":
            if output_format == "ansi" and use_colors:
                result.append(_colorize(val_esc, "90", enabled=True))
            else:
                result.append(val_esc)
        elif etype == "msg_link":
            msg_num_match = RE_MSG_LINK_PATTERN.search(evalue)
            msg_num = msg_num_match.group(1) if msg_num_match else None
            if msg_num:
                if output_format == "html":
                    anchor = (
                        f"msg-{conf_num}-{msg_num}"
                        if conf_num is not None
                        else f"msg-{msg_num}"
                    )
                    result.append(f'<a href="#{anchor}">{val_esc}</a>')
                elif output_format == "markdown":
                    anchor = (
                        f"msg-{conf_num}-{msg_num}"
                        if conf_num is not None
                        else f"msg-{msg_num}"
                    )
                    result.append(f"[{val_esc}](#{anchor})")
                elif output_format == "ansi" and use_colors:
                    result.append(_colorize(val_esc, "36", enabled=True))
                else:
                    result.append(val_esc)
            else:
                result.append(val_esc)
        else:
            result.append(val_esc)

        last_end = end

    result.append(escape(text[last_end:]))
    return "".join(result)




def _render_stats_bar_chart(
    title: str,
    items: list[tuple[Any, int]],
    use_colors: bool = False,
    bold: str = "1",
    cyan: str = "36",
    dim: str = "90",
) -> list[str]:
    """Render a color-coded ASCII bar chart for statistics.

    Args:
        title: The section title.
        items: List of (label, count) pairs.
        use_colors: Whether to apply ANSI colors.
        bold: ANSI code for bold text.
        cyan: ANSI code for cyan color.
        dim: ANSI code for dim text.

    Returns:
        A list of formatted strings representing the bar chart.
    """
    if not items:
        return []

    parts = []
    parts.append(f"\n  {_colorize(title, bold, enabled=use_colors)}")

    max_count = max(count for _, count in items)
    for label, count in items:
        # Consistent 25-character label alignment with truncation
        label_str = str(label)
        truncated_label = f"{label_str[:25]:<25}"
        count_str = f"{count:4}"
        # Scale bars to a maximum of 40 characters
        bar_len = int(count * 40 / max_count) if max_count > 0 else 0

        # Use solid block for bar if colors (and thus terminal features) are enabled
        bar_char = "█" if use_colors else "#"
        bar = bar_char * bar_len

        # Consistent coloring: Dim labels, Bold counts, Cyan bars
        parts.append(
            f"    {_colorize(truncated_label, dim, enabled=use_colors)} : {_colorize(count_str, bold, enabled=use_colors)} {_colorize(bar, cyan, enabled=use_colors)}"
        )

    return parts


def render_info_as_text(all_info: list[dict[str, Any]], use_colors: bool = False) -> str:
    """Render archive information into a human-readable text report."""
    BOLD = "1"
    CYAN = "36"

    parts = []
    for info in all_info:
        parts.append(f"File: {_colorize(info['file'], CYAN, enabled=use_colors)}")
        if info.get("error"):
            parts.append(f"  {info['error']}")
            parts.append("")
            continue

        bbs = info.get("bbs_info")
        if bbs:
            if bbs.get("name"):
                parts.append(f"  {_colorize('BBS Name:', BOLD, enabled=use_colors)} {bbs['name']}")
            if bbs.get("sysop"):
                parts.append(f"  {_colorize('SysOp:', BOLD, enabled=use_colors)}    {bbs['sysop']}")
            if bbs.get("location"):
                parts.append(f"  {_colorize('Location:', BOLD, enabled=use_colors)} {bbs['location']}")
            if bbs.get("bbs_id"):
                parts.append(f"  {_colorize('BBS ID:', BOLD, enabled=use_colors)}   {bbs['bbs_id']}")
            if bbs.get("packet_at"):
                parts.append(f"  {_colorize('Packet At:', BOLD, enabled=use_colors)} {bbs['packet_at']}")
            if bbs.get("user_name"):
                parts.append(f"  {_colorize('User Name:', BOLD, enabled=use_colors)} {bbs['user_name']}")

        parts.append(f"  {_colorize('Total Messages:', BOLD, enabled=use_colors)} {info['total_messages']}")
        parts.append(f"  {_colorize('Conferences:', BOLD, enabled=use_colors)}")

        for conf in info["conferences"]:
            count_str = _colorize(conf["message_count"], BOLD, enabled=use_colors)
            parts.append(
                f"    {conf['number']}: {conf['name']} ({count_str} messages)"
            )
        parts.append("")
    return "\n".join(parts)


def _render_info_html(all_info: list[dict[str, Any]]) -> list[str]:
    """Render archive information as an HTML fragment."""
    parts = []
    for info in all_info:
        parts.append('<div class="stats-container">')
        parts.append(f"<h2>File: {html.escape(info['file'])}</h2>")

        if info.get("error"):
            parts.append(f"<p>{html.escape(info['error'])}</p>")
            parts.append("</div>")
            continue

        bbs = info.get("bbs_info")
        if bbs:
            parts.append('<div class="stats-summary-info">')
            if bbs.get("name"):
                parts.append(
                    f"<div><strong>BBS Name:</strong> {html.escape(bbs['name'])}</div>"
                )
            if bbs.get("sysop"):
                parts.append(
                    f"<div><strong>SysOp:</strong> {html.escape(bbs['sysop'])}</div>"
                )
            if bbs.get("location"):
                parts.append(
                    f"<div><strong>Location:</strong> {html.escape(bbs['location'])}</div>"
                )
            if bbs.get("bbs_id"):
                parts.append(
                    f"<div><strong>BBS ID:</strong> {html.escape(bbs['bbs_id'])}</div>"
                )
            if bbs.get("packet_at"):
                parts.append(
                    f"<div><strong>Packet At:</strong> {html.escape(bbs['packet_at'])}</div>"
                )
            if bbs.get("user_name"):
                parts.append(
                    f"<div><strong>User Name:</strong> {html.escape(bbs['user_name'])}</div>"
                )
            parts.append("</div>")

        parts.append(
            f"<div><strong>Total Messages:</strong> {info['total_messages']}</div>"
        )

        if info["conferences"]:
            parts.append("<h3>Conferences</h3>")
            parts.append("<ul>")
            for conf in info["conferences"]:
                parts.append(
                    f"<li>{conf['number']}: {html.escape(conf['name'])} ({conf['message_count']} messages)</li>"
                )
            parts.append("</ul>")
        parts.append("</div>")
    return parts


def _render_info_markdown(all_info: list[dict[str, Any]]) -> list[str]:
    """Render archive information as a Markdown fragment."""
    parts = []
    for info in all_info:
        parts.append(f"## File: {info['file']}\n")

        if info.get("error"):
            parts.append(f"{info['error']}\n")
            continue

        bbs = info.get("bbs_info")
        if bbs:
            if bbs.get("name"):
                parts.append(f"- **BBS Name:** {bbs['name']}")
            if bbs.get("sysop"):
                parts.append(f"- **SysOp:** {bbs['sysop']}")
            if bbs.get("location"):
                parts.append(f"- **Location:** {bbs['location']}")
            if bbs.get("bbs_id"):
                parts.append(f"- **BBS ID:** {bbs['bbs_id']}")
            if bbs.get("packet_at"):
                parts.append(f"- **Packet At:** {bbs['packet_at']}")
            if bbs.get("user_name"):
                parts.append(f"- **User Name:** {bbs['user_name']}")

        parts.append(f"- **Total Messages:** {info['total_messages']}")

        if info["conferences"]:
            parts.append("\n### Conferences\n")
            parts.append("| # | Name | Messages |")
            parts.append("|---|---|---|")
            for conf in info["conferences"]:
                parts.append(
                    f"| {conf['number']} | {conf['name']} | {conf['message_count']} |"
                )
            parts.append("")
    return parts


def show_info(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Show a summary of the QWK packet contents."""
    all_info = []

    for input_path in input_paths:
        info_entry = {
            "file": input_path,
            "bbs_info": None,
            "total_messages": 0,
            "conferences": [],
        }
        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)

            bbs_info = getattr(board_dict, "bbs_info", None)
            if bbs_info:
                if settings.my_name:
                    bbs_info.user_name = settings.my_name
                info_entry["bbs_info"] = asdict(bbs_info)

            if isinstance(file_data, list):
                messages_to_process = file_data
            else:
                if len(file_data) < BLOCK_SIZE:
                    info_entry["error"] = "Invalid or empty file."
                    all_info.append(info_entry)
                    continue
                messages_to_process = parse_messages(
                    file_data, None, settings.encoding, headers_only=True
                )

            total_messages = 0
            conference_counts = defaultdict(int)

            try:
                for message in messages_to_process:
                    total_messages += 1
                    conference_counts[message.confnum] += 1
            except MessagesDatFormatError as e:
                logger.warning(f"File {input_path} appears truncated or malformed: {e}")

            info_entry["total_messages"] = total_messages
            if bbs_info:
                bbs_info.total_messages = total_messages
                info_entry["bbs_info"] = asdict(bbs_info)

            sorted_confs = sorted(conference_counts.items())
            for conf_num, count in sorted_confs:
                conf_name = board_dict.get(conf_num, f"Conference {conf_num}")
                info_entry["conferences"].append(
                    {"number": conf_num, "name": conf_name, "message_count": count}
                )

            all_info.append(info_entry)

        except PROCESSING_EXCEPTIONS as e:
            logger.error(f"Error reading info for {input_path}: {e}")

    if not all_info:
        return

    output = ""
    if settings.format == "json":
        output = json.dumps(all_info, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        title = "Archive Information"
        html_parts = _get_html_header(title)
        html_parts.append(f"<h1>{title}</h1>")
        html_parts.extend(_render_info_html(all_info))
        html_parts.extend(_get_html_footer())
        output = "\n".join(html_parts)
    elif settings.format == "markdown":
        title = "Archive Information"
        md_parts = [f"# {title}\n"]
        md_parts.extend(_render_info_markdown(all_info))
        output = "\n".join(md_parts)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        output = render_info_as_text(all_info, use_colors=use_colors)

    _write_text_output(output, settings.output_path, encoding="utf-8")


def _compute_stats_from_messages(
    messages: Iterator[ParsedMessage],
    file_label: str = "Archive",
) -> dict[str, Any]:
    """Aggregate statistics from an iterator of messages."""
    stats_entry: dict[str, Any] = {
        "file": file_label,
        "total_messages": 0,
        "matching_messages": 0,
        "dates": {"earliest": None, "latest": None},
        "authors": [],
        "recipients": [],
        "conferences": [],
        "bbses": [],
        "subjects": [],
        "keywords": [],
        "links": [],
        "emails": [],
        "phones": [],
        "top_attachments": [],
        "top_attachment_types": [],
        "attachments_count": 0,
        "day_of_week": {},
        "hour_of_day": {},
        "year_distribution": {},
        "month_distribution": {},
        "private_count": 0,
        "reply_count": 0,
        "reply_rate": 0.0,
        "avg_message_length": 0.0,
        "avg_word_count": 0.0,
        "conversation": {
            "avg_response_time": 0,
            "min_response_time": 0,
            "max_response_time": 0,
            "thread_count": 0,
            "avg_thread_length": 0,
            "max_thread_length": 0,
            "top_responders": [],
        },
    }

    author_counter: Counter = Counter()
    recipient_counter: Counter = Counter()
    conf_counter: Counter = Counter()
    bbs_counter: Counter = Counter()
    conf_names: dict[int, str] = {}
    subject_counter: Counter = Counter()
    keyword_counter: Counter = Counter()
    link_counter: Counter = Counter()
    email_counter: Counter = Counter()
    phone_counter: Counter = Counter()
    attachment_counter: Counter = Counter()
    attachment_type_counter: Counter = Counter()
    dow_counter: Counter = Counter()
    hour_counter: Counter = Counter()
    year_counter: Counter = Counter()
    month_counter: Counter = Counter()

    earliest_dt = None
    latest_dt = None
    private_count = 0
    attachments_count = 0
    processed_count = 0
    reply_count = 0
    total_chars = 0
    total_words = 0

    msg_timestamps = {}
    response_deltas = []
    author_deltas = defaultdict(list)
    parent_to_children = defaultdict(list)
    all_msg_keys = set()
    has_parent = set()

    for message in messages:
        processed_count += 1

        # Date/Time
        dt = _parse_qwk_date(message.header.msgdate, message.header.msgtime)
        if earliest_dt is None or dt < earliest_dt:
            earliest_dt = dt
        if latest_dt is None or dt > latest_dt:
            latest_dt = dt

        author_counter[message.header.msgfrom.strip()] += 1
        recipient_counter[message.header.msgto.strip()] += 1
        conf_counter[message.confnum] += 1
        if message.confname:
            conf_names[message.confnum] = message.confname

        bbs_display = message.bbs_name or message.bbs_id or "Unknown BBS"
        bbs_counter[bbs_display] += 1

        subject_counter[_normalize_subject(message.header.msgsubject)] += 1

        dow_counter[dt.strftime("%A")] += 1
        hour_counter[dt.hour] += 1
        year_counter[dt.year] += 1
        month_counter[dt.strftime("%Y-%m")] += 1

        if message.header.is_private:
            private_count += 1

        # Detect if it's a reply
        msg_key = (message.confnum, message.header.msgnum)
        if message.header.msgnum is not None:
            msg_timestamps[msg_key] = dt
            all_msg_keys.add(msg_key)

        is_reply = (
            message.header.refnum is not None and message.header.refnum != 0
        ) or RE_SUBJECT_PREFIX_PATTERN.match(message.header.msgsubject)

        if is_reply:
            reply_count += 1
            if message.header.refnum:
                parent_key = (message.confnum, message.header.refnum)
                if parent_key in msg_timestamps:
                    delta = (dt - msg_timestamps[parent_key]).total_seconds()
                    if delta >= 0:
                        response_deltas.append(delta)
                        author_deltas[message.header.msgfrom.strip()].append(delta)

                parent_to_children[parent_key].append(msg_key)
                has_parent.add(msg_key)

        # Check for attachments in the full message
        if message.text:
            total_chars += len(message.text)
            total_words += len(message.text.split())

            # Use cached attachments if available to avoid re-scanning
            current_attachments = message.discover_attachments()

            if current_attachments:
                attachments_count += len(current_attachments)
                for filename in current_attachments:
                    attachment_counter[filename] += 1
                    _, ext = os.path.splitext(filename.lower())
                    if ext:
                        attachment_type_counter[ext] += 1
                    else:
                        attachment_type_counter["(no extension)"] += 1

            # Keyword analysis
            words = re.findall(r"\b\w{3,}\b", message.text.lower())
            for word in words:
                if word not in DEFAULT_STOP_WORDS and not word.isdigit():
                    keyword_counter[word] += 1

            # URL analysis
            urls = RE_URL_PATTERN.findall(message.text)
            for url in urls:
                link_counter[url.lower()] += 1

            # Email analysis
            emails = RE_EMAIL_PATTERN.findall(message.text)
            for email_addr in emails:
                email_counter[email_addr.lower()] += 1

            # Phone analysis
            phones = RE_PHONE_PATTERN.findall(message.text)
            for phone in phones:
                phone_counter[phone.strip()] += 1

    stats_entry["total_messages"] = processed_count
    stats_entry["matching_messages"] = processed_count
    stats_entry["private_count"] = private_count
    stats_entry["attachments_count"] = attachments_count
    stats_entry["reply_count"] = reply_count
    stats_entry["reply_rate"] = (
        round(reply_count / processed_count * 100, 1) if processed_count > 0 else 0.0
    )
    stats_entry["avg_message_length"] = (
        round(total_chars / processed_count, 1) if processed_count > 0 else 0.0
    )
    stats_entry["avg_word_count"] = (
        round(total_words / processed_count, 1) if processed_count > 0 else 0.0
    )

    if earliest_dt:
        stats_entry["dates"]["earliest"] = earliest_dt.isoformat()
        stats_entry["dates"]["latest"] = latest_dt.isoformat()

    # Top 10
    stats_entry["authors"] = [
        {"name": n, "count": c} for n, c in author_counter.most_common(10)
    ]
    stats_entry["recipients"] = [
        {"name": n, "count": c} for n, c in recipient_counter.most_common(10)
    ]
    stats_entry["conferences"] = [
        {"number": n, "name": conf_names.get(n, str(n)), "count": c}
        for n, c in conf_counter.most_common(10)
    ]
    stats_entry["bbses"] = [
        {"name": n, "count": c} for n, c in bbs_counter.most_common(10)
    ]
    stats_entry["subjects"] = [
        {"subject": s, "count": c} for s, c in subject_counter.most_common(10)
    ]
    stats_entry["keywords"] = [
        {"word": w, "count": c} for w, c in keyword_counter.most_common(10)
    ]
    stats_entry["links"] = [
        {"url": u, "count": c} for u, c in link_counter.most_common(10)
    ]
    stats_entry["emails"] = [
        {"email": e, "count": c} for e, c in email_counter.most_common(10)
    ]
    stats_entry["phones"] = [
        {"phone": p, "count": c} for p, c in phone_counter.most_common(10)
    ]
    stats_entry["top_attachments"] = [
        {"name": n, "count": c} for n, c in attachment_counter.most_common(10)
    ]
    stats_entry["top_attachment_types"] = [
        {"extension": e, "count": c} for e, c in attachment_type_counter.most_common(10)
    ]
    stats_entry["day_of_week"] = dict(dow_counter)
    stats_entry["hour_of_day"] = {str(k): v for k, v in hour_counter.items()}
    stats_entry["year_distribution"] = {
        str(k): v for k, v in sorted(year_counter.items())
    }
    stats_entry["month_distribution"] = dict(sorted(month_counter.items()))

    # Conversation Analysis
    if response_deltas:
        stats_entry["conversation"]["avg_response_time"] = sum(response_deltas) / len(
            response_deltas
        )
        stats_entry["conversation"]["min_response_time"] = min(response_deltas)
        stats_entry["conversation"]["max_response_time"] = max(response_deltas)

    avg_author_deltas = []
    for author, deltas in author_deltas.items():
        if deltas:
            avg_author_deltas.append((author, sum(deltas) / len(deltas), len(deltas)))
    avg_author_deltas.sort(key=lambda x: x[1])
    stats_entry["conversation"]["top_responders"] = [
        {"name": a, "avg_speed": s, "count": c}
        for a, s, c in avg_author_deltas
        if c >= 2
    ][:10]

    roots = all_msg_keys - has_parent
    thread_lengths = []
    for root in roots:
        size = 0
        stack = [root]
        while stack:
            curr = stack.pop()
            size += 1
            if curr in parent_to_children:
                stack.extend(parent_to_children[curr])
        thread_lengths.append(size)

    if thread_lengths:
        stats_entry["conversation"]["thread_count"] = len(thread_lengths)
        stats_entry["conversation"]["avg_thread_length"] = sum(thread_lengths) / len(
            thread_lengths
        )
        stats_entry["conversation"]["max_thread_length"] = max(thread_lengths)

    return stats_entry


def calculate_archive_stats(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> dict[str, Any]:
    """Calculate detailed statistics for one or more archives."""
    total_count = 0
    matching_count = 0
    processed_count = 0
    conf_processed_counts = defaultdict(int)
    author_processed_counts = defaultdict(int)
    to_processed_counts = defaultdict(int)
    subject_processed_counts = defaultdict(int)
    bbs_processed_counts = defaultdict(int)

    # If engagement filters are active, we must non-streamingly process all messages
    # to calculate threading metrics before calculating statistics.
    use_deferred_stats = any(
        v is not None
        for v in (
            settings.min_replies,
            settings.max_replies,
            settings.min_thread_size,
            settings.max_thread_size,
        )
    ) or bool(settings.thread_id_filters)

    initial_filtering_settings = settings
    if settings.threaded or settings.thread_id_filters or any(
        v is not None
        for v in (
            settings.min_replies,
            settings.max_replies,
            settings.min_thread_size,
            settings.max_thread_size,
        )
    ):
        initial_filtering_settings = replace(
            settings,
            min_depth=None,
            max_depth=None,
            min_replies=None,
            max_replies=None,
            min_thread_size=None,
            max_thread_size=None,
            thread_id_filters=None,
        )

    def filtered_messages_gen():
        nonlocal total_count, matching_count, processed_count
        all_candidate_messages = []

        for input_path in input_paths:
            if settings.limit is not None and processed_count >= settings.limit:
                break
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)
            user_name = settings.my_name or (bbs_info.user_name if bbs_info else None)
            allowed_conferences = get_allowed_conferences(
                settings.conferences, board_dict
            )
            allowed_exclude_conferences = get_allowed_conferences(
                settings.exclude_conferences, board_dict
            )

            desc = f"Analyzing {os.path.basename(input_path)}"
            is_structured = isinstance(file_data, list)
            total_progress = len(file_data)

            with _create_progress_bar(
                total_progress, settings.quiet, desc=desc
            ) as progress_bar:
                if is_structured:
                    messages_to_process = file_data
                    if progress_bar is not None:
                        progress_bar.unit = "msg"
                        progress_bar.unit_scale = False
                else:
                    messages_to_process = parse_messages(
                        file_data, progress_bar, settings.encoding, headers_only=False
                    )

                for message in messages_to_process:
                    if is_structured and progress_bar is not None:
                        progress_bar.update(1)
                    total_count += 1

                    message = replace(
                        message,
                        confname=message.confname or board_dict.get(message.confnum),
                        bbs_name=message.bbs_name
                        or (bbs_info.name if bbs_info else None),
                        bbs_id=message.bbs_id
                        or (bbs_info.bbs_id if bbs_info else None),
                        source_file=message.source_file or os.path.basename(input_path),
                    )

                    if not matches_filters(
                        message,
                        initial_filtering_settings,
                        allowed_conferences,
                        user_name,
                        allowed_exclude_conferences,
                    ):
                        continue

                    matching_count += 1
                    if settings.skip is not None and matching_count <= settings.skip:
                        continue

                    if settings.limit_per_conf is not None:
                        if conf_processed_counts[message.confnum] >= settings.limit_per_conf:
                            continue

                    if settings.limit_per_author is not None:
                        author_key = message.header.msgfrom.strip().lower()
                        if author_processed_counts[author_key] >= settings.limit_per_author:
                            continue

                    if settings.limit_per_to is not None:
                        to_key = message.header.msgto.strip().lower()
                        if to_processed_counts[to_key] >= settings.limit_per_to:
                            continue

                    if settings.limit_per_subject is not None:
                        subject_key = _normalize_subject(message.header.msgsubject)
                        if subject_processed_counts[subject_key] >= settings.limit_per_subject:
                            continue

                    if settings.limit_per_bbs is not None:
                        bbs_key = (message.bbs_name or message.bbs_id or "").strip().lower()
                        if bbs_processed_counts[bbs_key] >= settings.limit_per_bbs:
                            continue

                    if settings.limit is not None and processed_count >= settings.limit:
                        break

                    conf_processed_counts[message.confnum] += 1
                    author_key = message.header.msgfrom.strip().lower()
                    author_processed_counts[author_key] += 1
                    to_key = message.header.msgto.strip().lower()
                    to_processed_counts[to_key] += 1
                    subject_key = _normalize_subject(message.header.msgsubject)
                    subject_processed_counts[subject_key] += 1
                    bbs_key = (message.bbs_name or message.bbs_id or "").strip().lower()
                    bbs_processed_counts[bbs_key] += 1
                    if use_deferred_stats:
                        all_candidate_messages.append(message)
                    else:
                        processed_count += 1
                        yield message

        if use_deferred_stats:
            threaded_msgs = _order_messages_by_thread(all_candidate_messages)
            for message in threaded_msgs:
                if (
                    (
                        settings.min_replies is None
                        or message.reply_count >= settings.min_replies
                    )
                    and (
                        settings.max_replies is None
                        or message.reply_count <= settings.max_replies
                    )
                    and (
                        settings.min_thread_size is None
                        or message.thread_size >= settings.min_thread_size
                    )
                    and (
                        settings.max_thread_size is None
                        or message.thread_size <= settings.max_thread_size
                    )
                    and (
                        settings.thread_id_filters is None
                        or (
                            message.thread_id is not None
                            and (
                                _safe_to_int(message.thread_id) in settings.thread_id_filters
                                if _safe_to_int(message.thread_id) is not None
                                else message.thread_id in {str(f) for f in settings.thread_id_filters}
                            )
                        )
                    )
                ):
                    processed_count += 1
                    yield message

    file_label = input_paths[0] if len(input_paths) == 1 else "Multiple Archives"
    stats_entry = _compute_stats_from_messages(
        filtered_messages_gen(), file_label=file_label
    )

    # Override counts with actual values tracked during filtering
    stats_entry["total_messages"] = total_count
    stats_entry["matching_messages"] = processed_count

    return stats_entry


def render_stats_as_text(stats: dict[str, Any], use_colors: bool = False) -> str:
    """Render a statistics entry into a human-readable text report."""
    # ANSI Attribute codes
    BOLD = "1"
    CYAN = "36"

    parts = []
    parts.append(f"Statistics for: {_colorize(stats['file'], CYAN, enabled=use_colors)}")
    parts.append(
        f"  {_colorize('Messages:', BOLD, enabled=use_colors)} {stats['matching_messages']} matching / {stats['total_messages']} total"
    )

    if stats["attachments_count"] > 0:
        parts.append(
            f"  {_colorize('Attachments:', BOLD, enabled=use_colors)} {stats['attachments_count']} files detected"
        )

    if stats["dates"]["earliest"]:
        earliest = datetime.datetime.fromisoformat(stats["dates"]["earliest"]).strftime(
            "%Y-%m-%d"
        )
        latest = datetime.datetime.fromisoformat(stats["dates"]["latest"]).strftime(
            "%Y-%m-%d"
        )
        parts.append(f"  {_colorize('Date Range:', BOLD, enabled=use_colors)} {earliest} to {latest}")

    parts.append(f"  {_colorize('Private:', BOLD, enabled=use_colors)}    {stats['private_count']} messages")

    parts.append(f"\n  {_colorize('Activity & Content:', BOLD, enabled=use_colors)}")
    parts.append(
        f"    Reply Rate:    {stats['reply_rate']}% ({stats['reply_count']} replies)"
    )
    parts.append(f"    Avg Length:    {int(stats['avg_message_length'])} characters")
    parts.append(f"    Avg Words:     {stats.get('avg_word_count', 0.0)}")

    if stats.get("conversation"):
        conv = stats["conversation"]
        parts.append(
            f"\n  {_colorize('Conversation Analysis:', BOLD, enabled=use_colors)}"
        )
        parts.append(f"    Threads:       {conv['thread_count']}")
        parts.append(f"    Avg Thread:    {conv['avg_thread_length']:.1f} messages")
        parts.append(f"    Longest Thread: {conv['max_thread_length']} messages")

        if conv["avg_response_time"] > 0:
            parts.append(
                f"    Response Time: Avg {format_duration(conv['avg_response_time'])}, Min {format_duration(conv['min_response_time'])}, Max {format_duration(conv['max_response_time'])}"
            )

        if conv.get("top_responders"):
            items = [(r["name"], r["count"]) for r in conv["top_responders"]]
            # Custom label for speed display
            speed_map = {
                r["name"]: format_duration(r["avg_speed"])
                for r in conv["top_responders"]
            }
            parts.append(
                f"\n  {_colorize('Fastest Responders (min 2 replies):', BOLD, enabled=use_colors)}"
            )
            max_count = max(c for _, c in items)
            for name, count in items:
                truncated_label = f"{name[:25]:<25}"
                count_str = f"{count:4}"
                bar_len = int(count * 40 / max_count) if max_count > 0 else 0
                bar = "#" * bar_len
                speed = speed_map[name]
                parts.append(
                    f"    {_colorize(truncated_label, '90', enabled=use_colors)} : {_colorize(count_str, BOLD, enabled=use_colors)} {_colorize(bar, '36', enabled=use_colors)} ({speed} avg)"
                )

    if stats["year_distribution"]:
        items = [(y, c) for y, c in sorted(stats["year_distribution"].items())]
        parts.extend(
            _render_stats_bar_chart("Yearly Activity:", items, use_colors=use_colors)
        )

    if stats["month_distribution"] and len(stats["month_distribution"]) <= 24:
        items = [(m, c) for m, c in sorted(stats["month_distribution"].items())]
        parts.extend(
            _render_stats_bar_chart("Monthly Activity:", items, use_colors=use_colors)
        )

    parts.extend(
        _render_stats_bar_chart(
            "Top Authors:",
            [(a["name"], a["count"]) for a in stats["authors"]],
            use_colors=use_colors,
        )
    )
    parts.extend(
        _render_stats_bar_chart(
            "Top Recipients:",
            [(r["name"], r["count"]) for r in stats["recipients"]],
            use_colors=use_colors,
        )
    )

    if stats.get("bbses"):
        parts.extend(
            _render_stats_bar_chart(
                "Top BBSes:",
                [(b["name"], b["count"]) for b in stats["bbses"]],
                use_colors=use_colors,
            )
        )

    if stats["conferences"]:
        items = [
            (f"{c['number']:3} {c['name']}", c["count"]) for c in stats["conferences"]
        ]
        parts.extend(
            _render_stats_bar_chart("Top Conferences:", items, use_colors=use_colors)
        )

    parts.extend(
        _render_stats_bar_chart(
            "Top Subjects:",
            [(s["subject"], s["count"]) for s in stats["subjects"]],
            use_colors=use_colors,
        )
    )
    parts.extend(
        _render_stats_bar_chart(
            "Top Keywords:",
            [(k["word"], k["count"]) for k in stats["keywords"]],
            use_colors=use_colors,
        )
    )

    if stats.get("links"):
        parts.extend(
            _render_stats_bar_chart(
                "Top Links:",
                [(link["url"], link["count"]) for link in stats["links"]],
                use_colors=use_colors,
            )
        )

    if stats.get("emails"):
        parts.extend(
            _render_stats_bar_chart(
                "Top Emails:",
                [(e["email"], e["count"]) for e in stats["emails"]],
                use_colors=use_colors,
            )
        )

    if stats.get("phones"):
        parts.extend(
            _render_stats_bar_chart(
                "Top Phone Numbers:",
                [(p["phone"], p["count"]) for p in stats["phones"]],
                use_colors=use_colors,
            )
        )

    if stats.get("top_attachments"):
        parts.extend(
            _render_stats_bar_chart(
                "Top Attachments:",
                [(a["name"], a["count"]) for a in stats["top_attachments"]],
                use_colors=use_colors,
            )
        )

    if stats.get("top_attachment_types"):
        parts.extend(
            _render_stats_bar_chart(
                "Top Attachment Types:",
                [(t["extension"], t["count"]) for t in stats["top_attachment_types"]],
                use_colors=use_colors,
            )
        )

    if stats["day_of_week"]:
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        items = [(d, stats["day_of_week"].get(d, 0)) for d in days]
        parts.extend(
            _render_stats_bar_chart(
                "Day of Week Distribution:", items, use_colors=use_colors
            )
        )

    if stats["hour_of_day"]:
        items = [(f"{h:02}:00", stats["hour_of_day"].get(str(h), 0)) for h in range(24)]
        parts.extend(
            _render_stats_bar_chart(
                "Hourly Distribution:", items, use_colors=use_colors
            )
        )

    return "\n".join(parts) + "\n"


def show_stats(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Show detailed statistics about the messages in the QWK archives."""
    all_stats = []

    if settings.merge_stats:
        try:
            stats_entry = calculate_archive_stats(input_paths, settings, logger)
            all_stats.append(stats_entry)
        except PROCESSING_EXCEPTIONS as e:
            logger.error(f"Error calculating merged stats: {e}")
    else:
        for input_path in input_paths:
            try:
                stats_entry = calculate_archive_stats([input_path], settings, logger)
                all_stats.append(stats_entry)
            except PROCESSING_EXCEPTIONS as e:
                logger.error(f"Error calculating stats for {input_path}: {e}")

    if not all_stats:
        return

    output = ""
    if settings.format == "json":
        output = json.dumps(all_stats, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        title = "Archive Statistics"
        html_parts = _get_html_header(title)
        html_parts.append(f"<h1>{title}</h1>")
        for stats in all_stats:
            html_parts.extend(_render_stats_html(stats))
        html_parts.extend(_get_html_footer())
        output = "\n".join(html_parts)
    elif settings.format == "markdown":
        title = "Archive Statistics"
        md_parts = [f"# {title}\n"]
        for stats in all_stats:
            md_parts.extend(_render_stats_markdown(stats))
        output = "\n".join(md_parts)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        parts = []
        for stats in all_stats:
            parts.append(render_stats_as_text(stats, use_colors=use_colors))
        output = "\n".join(parts)

    _write_text_output(output, settings.output_path, encoding="utf-8")


def process_multiple_files(
    input_paths: list[str],
    output_dir: str,
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> bool:
    if not settings.dry_run:
        os.makedirs(output_dir, exist_ok=True)
    had_errors = False
    for input_path in input_paths:
        try:
            output_filename = os.path.splitext(os.path.basename(input_path))[0]
            ext = FORMAT_EXTENSIONS.get(settings.format, ".txt")
            output_filename += ext
            output_path = os.path.join(output_dir, output_filename)
            per_file_settings = replace(
                settings,
                output_mode="file",
                output_path=output_path,
            )
            process_merged_files([input_path], per_file_settings, logger)
        except PROCESSING_EXCEPTIONS as error:
            logger.error("Error processing file %s: %s", input_path, error)
            had_errors = True
    return had_errors


def _normalize_subject(subject: str, lowercase: bool = True) -> str:
    """Normalize subject line for conversation grouping by removing prefixes."""
    s = subject.strip()
    while True:
        new_s = RE_SUBJECT_PREFIX_PATTERN.sub("", s)
        if new_s == s:
            break
        s = new_s
    s = s.strip()
    return s.lower() if lowercase else s


def _order_messages_by_thread(
    messages: list[ProcessedMessage],
) -> list[ProcessedMessage]:
    """Order processed messages so that conversations are grouped together.

    Messages are rearranged so that original posts appear before replies and
    warnings are emitted for loops.

    Args:
        messages: Messages that have already been processed and may contain
            reference links to other messages in the same conference.

    Returns:
        Messages ordered to reflect reply relationships while preserving
        unattached messages.
    """
    if not messages:
        return []

    logger = logging.getLogger(__name__)
    index_by_key: dict[tuple[int, int], int] = {}
    index_by_subject: dict[tuple[int, str], list[int]] = defaultdict(list)
    normalized_subjects: list[str] = []
    replies: dict[int, list[int]] = defaultdict(list)
    roots: list[int] = []

    # Build lookup tables to efficiently match replies by message number and subject
    for index, message in enumerate(messages):
        if message.msgnum is not None:
            index_by_key[(message.confnum, message.msgnum)] = index

        subj = _normalize_subject(message.header.msgsubject)
        normalized_subjects.append(subj)
        if subj:
            index_by_subject[(message.confnum, subj)].append(index)

    # Link replies to their original posts using message numbers or subjects
    parent_map: dict[int, int] = {}

    for index, message in enumerate(messages):
        parent_index: int | None = None

        # Try explicit refnum
        if message.refnum:
            parent_index = index_by_key.get((message.confnum, message.refnum))

            if parent_index is None:
                logger.debug(
                    "Message %s references missing or external message %s (conf %s).",
                    message.msgnum,
                    message.refnum,
                    message.confnum,
                )

        # Fallback: Subject matching
        if parent_index is None:
            subj = normalized_subjects[index]
            if subj:
                candidates = index_by_subject.get((message.confnum, subj), [])
                # Prefer candidates that appear before this message
                preceding = [i for i in candidates if i < index]
                if preceding:
                    parent_index = preceding[-1]

        if parent_index is not None and parent_index != index:
            # Check for immediate loop (referenced post is already a reply to this message)
            if index in replies and parent_index in replies[index]:
                child_msg = messages[index]
                logger.warning(
                    "Conversation loop detected (conf %s, msgnum %s) - skipping link assignment.",
                    child_msg.confnum,
                    child_msg.msgnum,
                )
                roots.append(index)
            else:
                replies[parent_index].append(index)
                parent_map[index] = parent_index
        else:
            roots.append(index)

    # Calculate thread sizes
    thread_sizes = {}
    for i in range(len(messages)):
        if i in thread_sizes:
            continue
        # Find root of this component
        root = i
        path = {root}
        while root in parent_map:
            p = parent_map[root]
            if p in path:
                break
            root = p
            path.add(root)
        # Traverse to find all nodes in this thread
        nodes = set()
        stack = [root]
        while stack:
            curr = stack.pop()
            if curr in nodes:
                continue
            nodes.add(curr)
            stack.extend(replies.get(curr, []))
        size = len(nodes)
        for n in nodes:
            thread_sizes[n] = size

    # Group messages into conversations while handling loops and deep nests
    ordered_messages: list[ProcessedMessage] = []
    visited: set[int] = set()
    cycle_reported: set[int] = set()

    def visit_iterative(start_idx: int) -> None:
        if start_idx in visited:
            return

        # Determine thread_id for this tree
        start_msg = messages[start_idx]
        thread_root_id = (
            str(start_msg.msgnum)
            if start_msg.msgnum is not None
            else f"idx_{start_idx}"
        )

        # Stack: (idx, depth, thread_id, replies_iterator)
        stack: list[tuple[int, int, str, Iterator[int]]] = []
        path: set[int] = set()

        def enter_node(idx: int, depth: int, thread_id: str) -> None:
            visited.add(idx)
            path.add(idx)

            original_msg = messages[idx]
            parent_msgnum = None
            if idx in parent_map:
                parent_idx = parent_map[idx]
                parent_msgnum = messages[parent_idx].msgnum

            new_msg = replace(
                original_msg,
                depth=depth,
                thread_id=thread_id,
                parent_msgnum=parent_msgnum,
                reply_count=len(replies.get(idx, [])),
                thread_size=thread_sizes.get(idx, 1),
            )
            ordered_messages.append(new_msg)
            stack.append((idx, depth, thread_id, iter(replies.get(idx, []))))

        enter_node(start_idx, 0, thread_root_id)

        while stack:
            parent_idx, depth, thread_id, replies_iter = stack[-1]

            try:
                child_idx = next(replies_iter)
            except StopIteration:
                stack.pop()
                path.remove(parent_idx)
                continue

            if child_idx in path:
                if child_idx not in cycle_reported:
                    child_msg = messages[child_idx]
                    logger.warning(
                        "Conversation loop detected (conf %s, msgnum %s).",
                        child_msg.confnum,
                        child_msg.msgnum,
                    )
                    cycle_reported.add(child_idx)
                continue

            if child_idx in visited:
                # If a node was already visited but is NOT in the current recursion path,
                # it means it was already processed as part of this or another tree.
                # We skip it to avoid duplication.
                continue

            enter_node(child_idx, depth + 1, thread_id)

    for root_idx in roots:
        visit_iterative(root_idx)

    for idx in range(len(messages)):
        if idx not in visited:
            visit_iterative(idx)

    return ordered_messages


def organize_by_bbs(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Organize archive files into directories based on their BBS name and ID."""
    supported_extensions = (
        ".qwk",
        ".rep",
        ".json",
        ".csv",
        ".xml",
        ".db",
        ".sqlite",
        ".mbox",
        ".eml",
        ".tar",
        ".tar.gz",
        ".tar.bz2",
        ".tgz",
        ".zip",
    )

    for input_path in input_paths:
        if not os.path.isfile(input_path):
            continue

        if (
            not input_path.lower().endswith(supported_extensions)
            and os.path.basename(input_path).lower() != "messages.dat"
        ):
            continue

        try:
            _, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)

            if bbs_info and (bbs_info.name or bbs_info.bbs_id):
                name_part = bbs_info.name.strip() if bbs_info.name else "Unknown BBS"
                id_part = f" ({bbs_info.bbs_id.strip()})" if bbs_info.bbs_id else ""

                folder_name = f"{name_part}{id_part}"
                safe_folder_name = "".join(
                    [
                        c
                        for c in folder_name
                        if c.isalnum() or c in (" ", ".", "_", "-", "(", ")")
                    ]
                ).strip()

                if not safe_folder_name:
                    safe_folder_name = "Unknown_BBS"

                if settings.dry_run:
                    logger.info(
                        "Dry run: Would move %s to %s/", input_path, safe_folder_name
                    )
                    continue

                if not os.path.exists(safe_folder_name):
                    os.makedirs(safe_folder_name)

                shutil.move(
                    input_path,
                    os.path.join(safe_folder_name, os.path.basename(input_path)),
                )
                logger.info("Moved %s to %s/", input_path, safe_folder_name)
            else:
                logger.warning("Could not find BBS information in %s", input_path)
        except Exception as e:
            logger.error("Error organizing %s: %s", input_path, e)


def validate_archive(
    input_path: str, logger: logging.Logger, encoding: str = "cp437"
) -> dict[str, Any]:
    """Validate the structural integrity and metadata completeness of an archive.

    This function checks if the file exists, checks block alignment for QWK/REP,
    checks schema completeness for modern formats, and scans for missing metadata.

    Args:
        input_path: Path to the archive file to validate.
        logger: Logger for warnings and information.
        encoding: Text encoding for parsing (default is 'cp437').

    Returns:
        A dictionary with validation results:
        {
            "valid": bool,
            "format": str,
            "messages_count": int,
            "errors": list[str],
            "warnings": list[str]
        }
    """
    result = {
        "valid": True,
        "format": "unknown",
        "messages_count": 0,
        "errors": [],
        "warnings": []
    }

    if not os.path.exists(input_path):
        result["valid"] = False
        result["errors"].append(f"File not found: {input_path}")
        return result

    if os.path.isdir(input_path):
        if not _is_maildir(input_path):
            result["valid"] = False
            result["errors"].append(f"Path is a directory but not a valid Maildir: {input_path}")
            return result
        result["format"] = "maildir"
    else:
        # Check if file is empty
        if os.path.getsize(input_path) == 0:
            result["valid"] = False
            result["errors"].append(f"File is empty: {input_path}")
            return result

    # Determine format
    ext = os.path.splitext(input_path)[1].lower()
    base_name = os.path.basename(input_path).lower()

    if ext == ".qwk" or ext == ".rep" or base_name == MESSAGES_FILENAME or base_name == REPLY_FILENAME:
        result["format"] = "qwk" if ext != ".rep" and base_name != REPLY_FILENAME else "rep"
    elif input_path.lower().endswith((".zip", ".tar", ".tar.gz", ".tar.bz2", ".tgz")):
        result["format"] = "compressed_archive"
    elif ext == ".json":
        result["format"] = "json"
    elif ext == ".jsonl":
        result["format"] = "jsonl"
    elif ext in (".db", ".sqlite"):
        result["format"] = "sqlite"
    elif ext == ".csv":
        result["format"] = "csv"
    elif ext in (".xml", ".rss"):
        result["format"] = "xml"
    elif ext == ".mbox":
        result["format"] = "mbox"
    elif ext == ".eml":
        result["format"] = "eml"
    elif ext in (".md", ".markdown"):
        result["format"] = "markdown"
    elif ext in (".html", ".htm"):
        result["format"] = "html"
    elif ext == ".txt":
        result["format"] = "text"
    elif _is_maildir(input_path):
        result["format"] = "maildir"

    # Now let's do format-specific validations
    fmt = result["format"]

    # 1. QWK/REP and standalone message files validation
    if fmt in ("qwk", "rep") and not os.path.isdir(input_path):
        size = os.path.getsize(input_path)
        if size < BLOCK_SIZE:
            result["valid"] = False
            result["errors"].append(f"File size ({size} bytes) is too small to contain a valid QWK/REP block (128 bytes).")
            return result
        if size % BLOCK_SIZE != 0:
            result["valid"] = False
            result["errors"].append(f"File size ({size} bytes) is not a multiple of 128 bytes. Block misalignment detected.")
            # Note: we still try to parse as much as possible

        # Read file_data and parse
        try:
            with open(input_path, "rb") as f:
                file_data = bytearray(f.read())
            # Parse messages
            messages = list(parse_messages(file_data, None, encoding, headers_only=True))
            result["messages_count"] = len(messages)
            _validate_messages_metadata(messages, result)
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Binary corruption or format error during QWK parsing: {str(e)}")

    # 2. Compressed Archives (ZIP / TAR)
    elif fmt == "compressed_archive":
        if ext == ".zip" and zipfile.is_zipfile(input_path):
            try:
                with zipfile.ZipFile(input_path) as myzip:
                    # Test zip archive integrity
                    bad_file = myzip.testzip()
                    if bad_file:
                        result["valid"] = False
                        result["errors"].append(f"ZIP file CRC check failed for: {bad_file}")

                    file_list = myzip.namelist()

                    messages_dat = next((n for n in file_list if n.lower() == MESSAGES_FILENAME), None)
                    reply_dat = next((n for n in file_list if n.lower() == REPLY_FILENAME), None)
                    control_dat = next((n for n in file_list if n.lower() == CONTROL_FILENAME), None)

                    if messages_dat or reply_dat:
                        # Standard QWK/REP archive
                        target_dat = messages_dat or reply_dat
                        # Check block alignment inside zip
                        info = myzip.getinfo(target_dat)
                        if info.file_size % BLOCK_SIZE != 0:
                            result["valid"] = False
                            result["errors"].append(f"Internal file '{target_dat}' size ({info.file_size} bytes) is not a multiple of 128 bytes.")

                        if messages_dat and not control_dat:
                            result["warnings"].append("CONTROL.DAT is missing from the QWK archive.")

                        # Try to load/parse
                        try:
                            with myzip.open(target_dat) as f:
                                file_data = bytearray(f.read())
                            messages = list(parse_messages(file_data, None, encoding, headers_only=True))
                            result["messages_count"] = len(messages)
                            _validate_messages_metadata(messages, result)
                        except Exception as e:
                            result["valid"] = False
                            result["errors"].append(f"Failed to parse messages from '{target_dat}': {str(e)}")
                    else:
                        # Multi-format batch loading zip
                        result["warnings"].append("Zip archive does not contain standard MESSAGES.DAT or REPLY.DAT. Validating internal files...")
                        _validate_batch_files(input_path, file_list, "ZIP", result, logger, encoding)
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"ZIP archive read error: {str(e)}")
        elif tarfile.is_tarfile(input_path):
            try:
                with tarfile.open(input_path) as mytar:
                    members = mytar.getmembers()
                    file_list = [m.name for m in members]

                    messages_dat = next((n for n in file_list if n.lower() == MESSAGES_FILENAME), None)
                    reply_dat = next((n for n in file_list if n.lower() == REPLY_FILENAME), None)
                    control_dat = next((n for n in file_list if n.lower() == CONTROL_FILENAME), None)

                    if messages_dat or reply_dat:
                        target_dat = messages_dat or reply_dat
                        member = mytar.getmember(target_dat)
                        if member.size % BLOCK_SIZE != 0:
                            result["valid"] = False
                            result["errors"].append(f"Internal file '{target_dat}' size ({member.size} bytes) is not a multiple of 128 bytes.")

                        if messages_dat and not control_dat:
                            result["warnings"].append("CONTROL.DAT is missing from the QWK archive.")

                        try:
                            f = mytar.extractfile(target_dat)
                            if f:
                                file_data = bytearray(f.read())
                                messages = list(parse_messages(file_data, None, encoding, headers_only=True))
                                result["messages_count"] = len(messages)
                                _validate_messages_metadata(messages, result)
                        except Exception as e:
                            result["valid"] = False
                            result["errors"].append(f"Failed to parse messages from '{target_dat}': {str(e)}")
                    else:
                        result["warnings"].append("TAR archive does not contain standard MESSAGES.DAT or REPLY.DAT. Validating internal files...")
                        _validate_batch_files(input_path, file_list, "TAR", result, logger, encoding)
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"TAR archive read error: {str(e)}")
        else:
            result["valid"] = False
            result["errors"].append("Unsupported or corrupted compressed archive format.")

    # 3. JSON Validation
    elif fmt == "json":
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Verify structured JSON schema
            if isinstance(data, dict):
                if data.get("type") == "qwk_archive":
                    if "messages" not in data:
                        result["valid"] = False
                        result["errors"].append("JSON dictionary format lacks 'messages' field.")
                        return result
                    messages_list = data["messages"]
                else:
                    messages_list = [data]
            elif isinstance(data, list):
                messages_list = data
            else:
                result["valid"] = False
                result["errors"].append("JSON data must be a list of messages or a structured dictionary.")
                return result

            result["messages_count"] = len(messages_list)
            for i, msg_data in enumerate(messages_list):
                if not isinstance(msg_data, dict):
                    result["valid"] = False
                    result["errors"].append(f"Message at index {i} is not a valid JSON object.")
                    continue
                if "header" not in msg_data:
                    result["warnings"].append(f"Message at index {i} is missing 'header' metadata.")
                else:
                    hdr = msg_data["header"]
                    if not isinstance(hdr, dict):
                        result["valid"] = False
                        result["errors"].append(f"Message at index {i} has invalid 'header' type (expected dictionary).")
                    else:
                        _validate_header_dict(hdr, f"index {i}", result)
        except json.JSONDecodeError as e:
            result["valid"] = False
            result["errors"].append(f"JSON syntax error: {str(e)}")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"JSON schema validation failed: {str(e)}")

    # 4. JSONL Validation
    elif fmt == "jsonl":
        try:
            count = 0
            with open(input_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        msg_data = json.loads(stripped)
                        if isinstance(msg_data, dict) and msg_data.get("type") == "metadata":
                            continue
                        count += 1
                        if not isinstance(msg_data, dict):
                            result["valid"] = False
                            result["errors"].append(f"JSONL line {line_idx} is not a valid object.")
                            continue
                        if "header" not in msg_data:
                            result["warnings"].append(f"JSONL line {line_idx} is missing 'header' metadata.")
                        else:
                            hdr = msg_data["header"]
                            _validate_header_dict(hdr, f"line {line_idx}", result)
                    except json.JSONDecodeError as e:
                        result["valid"] = False
                        result["errors"].append(f"JSONL syntax error on line {line_idx}: {str(e)}")
            result["messages_count"] = count
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"JSONL validation failed: {str(e)}")

    # 5. CSV Validation
    elif fmt == "csv":
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                required_cols = {"msgfrom", "msgto", "msgsubject", "text"}
                # Convert to lower to be flexible
                lower_headers = {h.lower() for h in headers}
                missing_cols = required_cols - lower_headers
                if missing_cols:
                    result["warnings"].append(f"CSV is missing recommended standard headers: {', '.join(missing_cols)}")

                count = 0
                for row_idx, row in enumerate(reader, 2):
                    count += 1
                    # Basic checks on row contents
                    from_val = row.get("msgfrom", row.get("msgfrom".upper(), "")).strip()
                    to_val = row.get("msgto", row.get("msgto".upper(), "")).strip()
                    subj_val = row.get("msgsubject", row.get("msgsubject".upper(), "")).strip()
                    if not from_val:
                        result["warnings"].append(f"CSV row {row_idx} is missing sender (msgfrom) field.")
                    if not to_val:
                        result["warnings"].append(f"CSV row {row_idx} is missing recipient (msgto) field.")
                    if not subj_val:
                        result["warnings"].append(f"CSV row {row_idx} is missing subject (msgsubject) field.")
                result["messages_count"] = count
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"CSV validation failed: {str(e)}")

    # 6. XML / RSS Validation
    elif fmt == "xml":
        try:
            tree = ET.parse(input_path)
            root = tree.getroot()
            if root.tag == "rss":
                # Validate as RSS
                channel = root.find("channel")
                if channel is None:
                    result["valid"] = False
                    result["errors"].append("RSS XML is missing the '<channel>' element.")
                else:
                    items = channel.findall("item")
                    result["messages_count"] = len(items)
                    for i, item in enumerate(items, 1):
                        title = item.findtext("title")
                        author = item.findtext("author")
                        if not title:
                            result["warnings"].append(f"RSS item {i} is missing '<title>' (subject).")
                        if not author:
                            result["warnings"].append(f"RSS item {i} is missing '<author>'.")
            else:
                # Standard XML
                entries = [root] if root.tag == "message" else root.findall("message")
                result["messages_count"] = len(entries)
                for i, entry in enumerate(entries, 1):
                    header_el = entry.find("header")
                    if header_el is None:
                        result["warnings"].append(f"XML message {i} is missing '<header>' metadata.")
                    else:
                        hdr_dict = {el.tag: (el.text or "").strip() for el in header_el}
                        _validate_header_dict(hdr_dict, f"message {i}", result)
        except ET.ParseError as e:
            result["valid"] = False
            result["errors"].append(f"XML parsing failed: {str(e)}")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"XML schema validation error: {str(e)}")

    # 7. SQLite Validation
    elif fmt == "sqlite":
        try:
            conn = sqlite3.connect(input_path)
            cursor = conn.cursor()
            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            if "messages" not in tables:
                result["valid"] = False
                result["errors"].append("SQLite database is missing the required 'messages' table.")
            else:
                # Check columns in 'messages' table
                cursor.execute("PRAGMA table_info(messages)")
                cols = {row[1].lower() for row in cursor.fetchall()}
                required_cols = {"author", "recipient", "subject", "text", "conference_number"}
                missing_cols = required_cols - cols
                if missing_cols:
                    result["valid"] = False
                    result["errors"].append(f"SQLite 'messages' table is missing required columns: {', '.join(missing_cols)}")
                else:
                    cursor.execute("SELECT COUNT(*) FROM messages")
                    result["messages_count"] = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"SQLite validation failed: {str(e)}")

    # 8. Others (mbox, EML, HTML, Maildir, Markdown, Text)
    elif fmt in ("mbox", "eml", "maildir", "html", "markdown", "text"):
        try:
            messages, _ = load_data(input_path, logger, encoding)
            if isinstance(messages, list):
                result["messages_count"] = len(messages)
                _validate_messages_metadata(messages, result)
            else:
                result["warnings"].append("Load returned byte stream instead of parsed messages; metadata validation skipped.")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Format validation failed for {fmt}: {str(e)}")

    else:
        result["warnings"].append(f"Unrecognized archive format for file '{input_path}'. Integrity checks were skipped.")

    if result["errors"]:
        result["valid"] = False

    return result


def _validate_messages_metadata(messages: list[ParsedMessage], result: dict[str, Any]) -> None:
    """Validate parsed MessageHeader objects for missing required metadata."""
    for i, msg in enumerate(messages):
        header = msg.header
        msg_id_str = f"#{header.msgnum}" if header.msgnum is not None else f"at index {i}"

        # Check standard metadata fields
        if not (header.msgfrom or "").strip():
            result["warnings"].append(f"Message {msg_id_str} is missing sender (msgfrom) field.")
        if not (header.msgto or "").strip():
            result["warnings"].append(f"Message {msg_id_str} is missing recipient (msgto) field.")
        if not (header.msgsubject or "").strip():
            result["warnings"].append(f"Message {msg_id_str} is missing subject field.")
        if header.msgnum is None:
            result["warnings"].append(f"Message {msg_id_str} is missing message number.")
        elif header.msgnum <= 0:
            result["warnings"].append(f"Message {msg_id_str} has invalid/non-positive message number: {header.msgnum}")


def _validate_header_dict(hdr: dict[str, Any], label: str, result: dict[str, Any]) -> None:
    """Validate a raw header dictionary from JSON or XML structures."""
    msgfrom = str(hdr.get("msgfrom", hdr.get("msgfrom".upper(), ""))).strip()
    msgto = str(hdr.get("msgto", hdr.get("msgto".upper(), ""))).strip()
    msgsubject = str(hdr.get("msgsubject", hdr.get("msgsubject".upper(), ""))).strip()
    msgnum = hdr.get("msgnum", hdr.get("msgnum".upper(), None))

    if not msgfrom:
        result["warnings"].append(f"Message at {label} is missing sender (msgfrom) field.")
    if not msgto:
        result["warnings"].append(f"Message at {label} is missing recipient (msgto) field.")
    if not msgsubject:
        result["warnings"].append(f"Message at {label} is missing subject field.")
    if msgnum is None:
        result["warnings"].append(f"Message at {label} is missing message number.")
    elif isinstance(msgnum, int) and msgnum <= 0:
        result["warnings"].append(f"Message at {label} has invalid/non-positive message number: {msgnum}")


def _validate_batch_files(
    archive_path: str,
    file_list: list[str],
    archive_type: str,
    result: dict[str, Any],
    logger: logging.Logger,
    encoding: str,
) -> None:
    """Helper to run validate_archive recursively for internal files extracted to a temp dir."""
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            if archive_type == "ZIP":
                with zipfile.ZipFile(archive_path) as myzip:
                    myzip.extractall(temp_dir)
            else:
                with tarfile.open(archive_path) as mytar:
                    if hasattr(tarfile, "data_filter"):
                        mytar.extractall(temp_dir, filter="data")
                    else:
                        mytar.extractall(temp_dir)

            # Find and validate all expanded paths
            candidate_paths = expand_paths([temp_dir])
            messages_count = 0
            for p in candidate_paths:
                sub_res = validate_archive(p, logger, encoding)
                messages_count += sub_res["messages_count"]
                if not sub_res["valid"]:
                    result["valid"] = False
                    for err in sub_res["errors"]:
                        # Reword path to represent the archive structure
                        rel_p = os.path.relpath(p, temp_dir)
                        result["errors"].append(f"[{rel_p}] {err}")
                for warn in sub_res["warnings"]:
                    rel_p = os.path.relpath(p, temp_dir)
                    result["warnings"].append(f"[{rel_p}] {warn}")
            result["messages_count"] = messages_count
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Failed to validate internal batch files in {archive_type}: {str(e)}")


def _render_validation_html(all_results: list[dict[str, Any]]) -> list[str]:
    """Render archive validation information as an HTML fragment."""
    parts = []
    for res in all_results:
        parts.append('<div class="stats-container">')
        status_str = "VALID" if res["valid"] else "INVALID"
        status_color = "#4e9a06" if res["valid"] else "#cc0000"

        parts.append(f"<h2>File: {html.escape(res['file'])}</h2>")
        parts.append('<div class="stats-summary-info">')
        parts.append(
            f'<div><strong>Status:</strong> <span style="color: {status_color}; font-weight: bold;">{status_str}</span></div>'
        )
        parts.append(f"<div><strong>Format:</strong> {html.escape(res['format'])}</div>")
        parts.append(f"<div><strong>Messages:</strong> {res['messages_count']}</div>")
        parts.append("</div>")

        if res.get("errors"):
            parts.append('<h3>Errors</h3>')
            parts.append('<ul style="color: #cc0000;">')
            for err in res["errors"]:
                parts.append(f"<li>{html.escape(err)}</li>")
            parts.append("</ul>")

        if res.get("warnings"):
            parts.append('<h3>Warnings</h3>')
            parts.append('<ul style="color: #c4a000;">')
            for warn in res["warnings"]:
                parts.append(f"<li>{html.escape(warn)}</li>")
            parts.append("</ul>")

        parts.append("</div>")
    return parts


def _render_validation_markdown(all_results: list[dict[str, Any]]) -> list[str]:
    """Render archive validation information as a Markdown fragment."""
    parts = []
    for res in all_results:
        status_str = "VALID" if res["valid"] else "INVALID"
        emoji = "✅" if res["valid"] else "❌"
        parts.append(f"## File: {res['file']}\n")
        parts.append(f"- **Status:** {emoji} {status_str}")
        parts.append(f"- **Format:** {res['format']}")
        parts.append(f"- **Messages:** {res['messages_count']}")

        if res.get("errors"):
            parts.append("\n### Errors\n")
            for err in res["errors"]:
                parts.append(f"- {err}")
        if res.get("warnings"):
            parts.append("\n### Warnings\n")
            for warn in res["warnings"]:
                parts.append(f"- {warn}")
        parts.append("\n---\n")
    return parts


def render_validation_as_text(all_results: list[dict[str, Any]], use_colors: bool = False) -> str:
    """Render archive validation information into a human-readable text report."""
    BOLD = "1"
    RED = "31"
    GREEN = "32"
    YELLOW = "33"

    parts = []
    for res in all_results:
        status_str = "VALID" if res["valid"] else "INVALID"
        color_code = GREEN if res["valid"] else RED
        bold_status = _colorize(status_str, BOLD, color_code, enabled=use_colors)

        parts.append(
            f"File: {res['file']} "
            f"({res['format']}, {res['messages_count']} messages) - [{bold_status}]"
        )
        for err in res.get("errors", []):
            parts.append(f"  - [{_colorize('Error', BOLD, RED, enabled=use_colors)}] {err}")
        for warn in res.get("warnings", []):
            parts.append(f"  - [{_colorize('Warning', BOLD, YELLOW, enabled=use_colors)}] {warn}")
        parts.append("")
    return "\n".join(parts)


def show_validation_report(
    input_paths: list[str],
    settings: ProcessingSettings,
    logger: logging.Logger,
    validator: Any = None,
) -> bool:
    """Validate archives, format the results, and export/print the validation report.

    Returns:
        True if all validated archives are structurally valid, False otherwise.
    """
    if validator is None:
        validator = validate_archive

    all_results = []
    valid_all = True

    for input_path in input_paths:
        try:
            res = validator(input_path, logger, settings.encoding)
            res_entry = dict(res)
            res_entry["file"] = input_path
            all_results.append(res_entry)
            if not res["valid"]:
                valid_all = False
        except Exception as e:
            logger.error(f"Error validating {input_path}: {e}")
            all_results.append({
                "file": input_path,
                "valid": False,
                "format": "unknown",
                "messages_count": 0,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": []
            })
            valid_all = False

    if not all_results:
        return valid_all

    output = ""
    if settings.format == "json":
        output = json.dumps(all_results, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        title = "Archive Validation Report"
        html_parts = _get_html_header(title)
        html_parts.append(f"<h1>{title}</h1>")
        html_parts.extend(_render_validation_html(all_results))
        html_parts.extend(_get_html_footer())
        output = "\n".join(html_parts)
    elif settings.format == "markdown":
        title = "Archive Validation Report"
        md_parts = [f"# {title}\n"]
        md_parts.extend(_render_validation_markdown(all_results))
        output = "\n".join(md_parts)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        output = render_validation_as_text(all_results, use_colors=use_colors)

    if settings.output_path:
        _write_text_output(output, settings.output_path, encoding="utf-8")
    else:
        for line in output.splitlines():
            logger.info(line)

    return valid_all


def render_threads_as_text(thread_metrics: list[dict[str, Any]], use_colors: bool = False) -> str:
    """Render a thread list into a human-readable text report."""
    BOLD = "1"
    DIM = "90"

    parts = []
    parts.append("Conversation Threads:")

    # Header
    hdr = f"  {'Thread ID':<10} | {'Root Subject':<30} | {'Starter':<20} | {'Replies':<7} | {'Max Depth':<9} | {'Last Activity':<14}"
    parts.append(_colorize(hdr, BOLD, enabled=use_colors))
    parts.append(_colorize("  " + "-" * 105, DIM, enabled=use_colors))

    for t in thread_metrics:
        tid = str(t["thread_id"])
        subj = t["root_subject"]
        if len(subj) > 30:
            subj = subj[:27] + "..."
        starter = t["starter"]
        if len(starter) > 20:
            starter = starter[:17] + "..."
        replies = str(t["reply_count"])
        depth = str(t["deepest_depth"])
        last_act = t["last_activity"]

        line = f"  {tid:<10} | {subj:<30} | {starter:<20} | {replies:<7} | {depth:<9} | {last_act:<14}"
        parts.append(line)

    return "\n".join(parts) + "\n"


def _render_threads_html(thread_metrics: list[dict[str, Any]], title: str) -> str:
    """Render conversation threads as an HTML document with basic table styles."""
    html_parts = _get_html_header(title)
    html_parts.append(f"<h1>{html.escape(title)}</h1>")

    # Simple inline styles for table in threads view
    html_parts.append("<style>")
    html_parts.append("table { border-collapse: collapse; width: 100%; margin-top: 1em; font-family: sans-serif; }")
    html_parts.append("th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }")
    html_parts.append("th { background-color: #f2f2f2; font-weight: bold; }")
    html_parts.append("tr:nth-child(even) { background-color: #f9f9f9; }")
    html_parts.append("</style>")

    html_parts.append('<div class="stats-container">')
    html_parts.append("<table>")
    html_parts.append(
        "<thead><tr>"
        "<th>Thread ID</th>"
        "<th>Root Subject</th>"
        "<th>Starter</th>"
        "<th>Replies</th>"
        "<th>Max Depth</th>"
        "<th>Last Activity</th>"
        "</tr></thead>"
    )
    html_parts.append("<tbody>")
    for t in thread_metrics:
        html_parts.append("<tr>")
        html_parts.append(f"<td>{html.escape(str(t['thread_id']))}</td>")
        html_parts.append(f"<td>{html.escape(t['root_subject'])}</td>")
        html_parts.append(f"<td>{html.escape(t['starter'])}</td>")
        html_parts.append(f"<td>{t['reply_count']}</td>")
        html_parts.append(f"<td>{t['deepest_depth']}</td>")
        html_parts.append(f"<td>{html.escape(t['last_activity'])}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    html_parts.append("</div>")
    html_parts.extend(_get_html_footer())
    return "\n".join(html_parts)


def _render_threads_markdown(thread_metrics: list[dict[str, Any]], title: str) -> str:
    """Render conversation threads as a Markdown document."""
    md_parts = [f"# {title}\n"]
    md_parts.append("| Thread ID | Root Subject | Starter | Replies | Max Depth | Last Activity |")
    md_parts.append("|---|---|---|---|---|---|")
    for t in thread_metrics:
        subj = _escape_markdown(t["root_subject"])
        starter = _escape_markdown(t["starter"])
        md_parts.append(
            f"| {t['thread_id']} | {subj} | {starter} | {t['reply_count']} | {t['deepest_depth']} | {t['last_activity']} |"
        )
    return "\n".join(md_parts) + "\n"


def _render_threads_csv(thread_metrics: list[dict[str, Any]]) -> str:
    """Render conversation threads as CSV format."""
    output = io.StringIO()
    fieldnames = ["thread_id", "root_subject", "starter", "reply_count", "deepest_depth", "last_activity"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar="\\")
    writer.writeheader()
    for t in thread_metrics:
        writer.writerow(t)
    return output.getvalue()


def show_threads(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Read archives, run thread reconstruction, and export conversation thread-listing metrics."""
    all_messages = []

    # 1. Load messages and build a unified list
    for input_path in input_paths:
        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)

            if isinstance(file_data, list):
                msgs = file_data
            else:
                if len(file_data) < BLOCK_SIZE:
                    continue
                msgs = list(parse_messages(file_data, None, settings.encoding))

            for msg in msgs:
                msg.confname = msg.confname or board_dict.get(msg.confnum)
                msg.bbs_name = msg.bbs_name or (bbs_info.name if bbs_info else None)
                msg.bbs_id = msg.bbs_id or (bbs_info.bbs_id if bbs_info else None)
                msg.source_file = msg.source_file or os.path.basename(input_path)
            all_messages.extend(msgs)
        except Exception as e:
            logger.error("Failed to load archive %s: %s", input_path, e)

    if not all_messages:
        logger.warning("No messages loaded. Thread-listing aborted.")
        return

    # 2. Gather filters criteria
    allowed_conferences = set()
    allowed_exclude_conferences = set()
    user_name = settings.my_name

    for input_path in input_paths:
        try:
            _, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)
            if not user_name and bbs_info:
                user_name = bbs_info.user_name
            allowed_conferences.update(get_allowed_conferences(settings.conferences, board_dict))
            allowed_exclude_conferences.update(get_allowed_conferences(settings.exclude_conferences, board_dict))
        except Exception:
            pass

    # 3. Apply settings filters to select matching messages
    matching_messages = []
    for msg in all_messages:
        if matches_filters(msg, settings, allowed_conferences, user_name, allowed_exclude_conferences):
            matching_messages.append(msg)

    # 4. Thread reconstruction
    threaded_messages = _order_messages_by_thread(matching_messages)

    # 5. Group by thread ID
    threads_map = defaultdict(list)
    for msg in threaded_messages:
        if msg.thread_id is not None:
            threads_map[msg.thread_id].append(msg)

    # 6. Map thread metrics
    thread_metrics = []
    for tid, msgs_in_thread in threads_map.items():
        root_msg = next((m for m in msgs_in_thread if m.depth == 0), None)
        if not root_msg:
            root_msg = msgs_in_thread[0]

        root_subject = root_msg.header.msgsubject.strip()
        starter = root_msg.header.msgfrom.strip()
        reply_count = len(msgs_in_thread) - 1
        deepest_depth = max(m.depth for m in msgs_in_thread)

        newest_msg = max(
            msgs_in_thread,
            key=lambda m: _parse_qwk_date(m.header.msgdate, m.header.msgtime)
        )
        last_activity = f"{newest_msg.header.msgdate} {newest_msg.header.msgtime}"

        thread_metrics.append({
            "thread_id": tid,
            "root_subject": root_subject,
            "starter": starter,
            "reply_count": reply_count,
            "deepest_depth": deepest_depth,
            "last_activity": last_activity
        })

    # 7. Sort threads by thread ID numerically or string fallback
    def thread_sort_key(t):
        try:
            return (0, int(t["thread_id"]))
        except ValueError:
            return (1, t["thread_id"])
    thread_metrics.sort(key=thread_sort_key)

    # 8. Render output format
    output = ""
    title = "Conversation Threads"
    if settings.format == "json":
        output = json.dumps(thread_metrics, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        output = _render_threads_html(thread_metrics, title)
    elif settings.format == "markdown":
        output = _render_threads_markdown(thread_metrics, title)
    elif settings.format == "csv":
        output = _render_threads_csv(thread_metrics)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        output = render_threads_as_text(thread_metrics, use_colors=use_colors)

    # 9. Write or print report
    _write_text_output(output, settings.output_path, encoding="utf-8")


def render_attachments_as_text(attachment_records: list[dict[str, Any]], use_colors: bool = False) -> str:
    """Render a list of attachment records into a human-readable text report."""
    if not attachment_records:
        return "No attachments found in the specified archive(s).\n"

    BOLD = "1"
    DIM = "90"

    parts = []
    parts.append("Archive Attachments:")

    hdr = f"  {'Filename':<30} | {'Msg #':<7} | {'Author':<20} | {'Conference':<20} | {'BBS':<15} | {'Source File':<15}"
    parts.append(_colorize(hdr, BOLD, enabled=use_colors))
    parts.append(_colorize("  " + "-" * 118, DIM, enabled=use_colors))

    for item in attachment_records:
        fname = item["filename"]
        if len(fname) > 30:
            fname = fname[:27] + "..."
        msgnum = str(item["msgnum"])
        author = item["author"]
        if len(author) > 20:
            author = author[:17] + "..."
        conf = item["conference"]
        if len(conf) > 20:
            conf = conf[:17] + "..."
        bbs = item["bbs_name"]
        if len(bbs) > 15:
            bbs = bbs[:12] + "..."
        source = item["source_file"]
        if len(source) > 15:
            source = source[:12] + "..."

        line = f"  {fname:<30} | {msgnum:<7} | {author:<20} | {conf:<20} | {bbs:<15} | {source:<15}"
        parts.append(line)

    return "\n".join(parts) + "\n"


def _render_attachments_html(attachment_records: list[dict[str, Any]], title: str) -> str:
    """Render attachment records as an HTML document with styled table."""
    html_parts = _get_html_header(title)
    html_parts.append(f"<h1>{html.escape(title)}</h1>")

    html_parts.append("<style>")
    html_parts.append("table { border-collapse: collapse; width: 100%; margin-top: 1em; font-family: sans-serif; }")
    html_parts.append("th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }")
    html_parts.append("th { background-color: #f2f2f2; font-weight: bold; }")
    html_parts.append("tr:nth-child(even) { background-color: #f9f9f9; }")
    html_parts.append("</style>")

    html_parts.append('<div class="stats-container">')
    html_parts.append("<table>")
    html_parts.append(
        "<thead><tr>"
        "<th>Filename</th>"
        "<th>Msg #</th>"
        "<th>Author</th>"
        "<th>Conference</th>"
        "<th>BBS</th>"
        "<th>Source File</th>"
        "</tr></thead>"
    )
    html_parts.append("<tbody>")
    for item in attachment_records:
        html_parts.append("<tr>")
        html_parts.append(f"<td>{html.escape(str(item['filename']))}</td>")
        html_parts.append(f"<td>{item['msgnum']}</td>")
        html_parts.append(f"<td>{html.escape(str(item['author']))}</td>")
        html_parts.append(f"<td>{html.escape(str(item['conference']))}</td>")
        html_parts.append(f"<td>{html.escape(str(item['bbs_name']))}</td>")
        html_parts.append(f"<td>{html.escape(str(item['source_file']))}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    html_parts.append("</div>")
    html_parts.extend(_get_html_footer())
    return "\n".join(html_parts)


def _render_attachments_markdown(attachment_records: list[dict[str, Any]], title: str) -> str:
    """Render attachment records as a Markdown document."""
    md_parts = [f"# {title}\n"]
    md_parts.append("| Filename | Msg # | Author | Conference | BBS | Source File |")
    md_parts.append("|---|---|---|---|---|---|")
    for item in attachment_records:
        fname = _escape_markdown(item["filename"])
        author = _escape_markdown(item["author"])
        conf = _escape_markdown(item["conference"])
        bbs = _escape_markdown(item["bbs_name"])
        source = _escape_markdown(item["source_file"])
        md_parts.append(
            f"| {fname} | {item['msgnum']} | {author} | {conf} | {bbs} | {source} |"
        )
    return "\n".join(md_parts) + "\n"


def _render_attachments_csv(attachment_records: list[dict[str, Any]]) -> str:
    """Render attachment records in CSV format."""
    output = io.StringIO()
    fieldnames = ["filename", "msgnum", "author", "conference", "bbs_name", "source_file"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar="\\")
    writer.writeheader()
    for item in attachment_records:
        writer.writerow(item)
    return output.getvalue()


def show_attachments(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Read archives, discover attachments across matching messages, and export structured attachment records."""
    all_messages = []

    # 1. Load messages from all input paths
    for input_path in input_paths:
        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)

            if isinstance(file_data, list):
                msgs = file_data
            else:
                if len(file_data) < BLOCK_SIZE:
                    continue
                msgs = list(parse_messages(file_data, None, settings.encoding))

            for msg in msgs:
                msg.confname = msg.confname or board_dict.get(msg.confnum)
                msg.bbs_name = msg.bbs_name or (bbs_info.name if bbs_info else None)
                msg.bbs_id = msg.bbs_id or (bbs_info.bbs_id if bbs_info else None)
                msg.source_file = msg.source_file or os.path.basename(input_path)
            all_messages.extend(msgs)
        except Exception as e:
            logger.error("Failed to load archive %s: %s", input_path, e)

    # 2. Gather filter criteria
    allowed_conferences = set()
    allowed_exclude_conferences = set()
    user_name = settings.my_name

    for input_path in input_paths:
        try:
            _, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)
            if not user_name and bbs_info:
                user_name = bbs_info.user_name
            allowed_conferences.update(get_allowed_conferences(settings.conferences, board_dict))
            allowed_exclude_conferences.update(get_allowed_conferences(settings.exclude_conferences, board_dict))
        except Exception:
            pass

    # 3. Apply settings filters and discover attachments
    attachment_records = []
    for msg in all_messages:
        if matches_filters(msg, settings, allowed_conferences, user_name, allowed_exclude_conferences):
            attachments = msg.discover_attachments()
            if attachments:
                for filename in attachments:
                    attachment_records.append({
                        "filename": filename,
                        "msgnum": msg.header.msgnum,
                        "author": (msg.header.msgfrom or "").strip(),
                        "conference": msg.confname or f"Conf #{msg.confnum}",
                        "bbs_name": (msg.bbs_name or msg.bbs_id or "").strip(),
                        "source_file": msg.source_file or "",
                    })

    # 4. Sort records by filename then msgnum
    attachment_records.sort(key=lambda x: (x["filename"].lower(), x["msgnum"]))

    # 5. Render output format
    output = ""
    title = "Archive Attachments"
    if settings.format == "json":
        output = json.dumps(attachment_records, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        output = _render_attachments_html(attachment_records, title)
    elif settings.format == "markdown":
        output = _render_attachments_markdown(attachment_records, title)
    elif settings.format == "csv":
        output = _render_attachments_csv(attachment_records)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        output = render_attachments_as_text(attachment_records, use_colors=use_colors)

    # 6. Write or print report
    _write_text_output(output, settings.output_path, encoding="utf-8")


def render_conferences_as_text(conf_list: list[dict[str, Any]], use_colors: bool = True) -> str:
    """Render a list of conference entries into a formatted text string."""
    lines = []
    header_str = "Conference Areas"
    if use_colors:
        lines.append(_colorize(header_str, "bold", "cyan"))
    else:
        lines.append(header_str)

    sep = "-" * 80
    if use_colors:
        lines.append(_colorize(sep, "dim"))
    else:
        lines.append(sep)

    col_hdr = f"  {'#':<5} {'Conference Name':<32} {'Messages':<10} {'BBS Name':<25}"
    if use_colors:
        lines.append(_colorize(col_hdr, "bold"))
    else:
        lines.append(col_hdr)

    if use_colors:
        lines.append(_colorize(sep, "dim"))
    else:
        lines.append(sep)

    for conf in conf_list:
        cnum = str(conf["number"])
        cname = str(conf["name"])
        if len(cname) > 30:
            cname = cname[:27] + "..."
        count = str(conf["message_count"])
        bbs = str(conf["bbs_name"])
        if len(bbs) > 23:
            bbs = bbs[:20] + "..."

        row_str = f"  {cnum:<5} {cname:<32} {count:<10} {bbs:<25}"
        lines.append(row_str)

    if use_colors:
        lines.append(_colorize(sep, "dim"))
    else:
        lines.append(sep)

    summary_str = f"Total Conferences: {len(conf_list)}"
    if use_colors:
        lines.append(_colorize(summary_str, "bold", "green"))
    else:
        lines.append(summary_str)

    return "\n".join(lines)


def _render_conferences_html(conf_list: list[dict[str, Any]], title: str) -> str:
    html_parts = _get_html_header(title)
    html_parts.append(f"<h1>{title}</h1>")
    html_parts.append("<table class='stats-table'>")
    html_parts.append("<thead><tr><th>#</th><th>Conference Name</th><th>Messages</th><th>BBS Name</th></tr></thead>")
    html_parts.append("<tbody>")
    for conf in conf_list:
        html_parts.append(
            f"<tr><td>{conf['number']}</td><td>{html.escape(str(conf['name']))}</td>"
            f"<td>{conf['message_count']}</td><td>{html.escape(str(conf['bbs_name']))}</td></tr>"
        )
    html_parts.append("</tbody></table>")
    html_parts.extend(_get_html_footer())
    return "\n".join(html_parts)


def _render_conferences_markdown(conf_list: list[dict[str, Any]], title: str) -> str:
    md_parts = [f"# {title}\n"]
    md_parts.append("| # | Conference Name | Messages | BBS Name |")
    md_parts.append("|---|-----------------|----------|----------|")
    for conf in conf_list:
        md_parts.append(f"| {conf['number']} | {conf['name']} | {conf['message_count']} | {conf['bbs_name']} |")
    return "\n".join(md_parts)


def _render_conferences_csv(conf_list: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["number", "name", "message_count", "bbs_name"])
    writer.writeheader()
    writer.writerows(conf_list)
    return output.getvalue()


def show_list_conferences(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Read archives and export a list of conference areas."""
    conferences_map = {}

    for input_path in input_paths:
        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)
            bbs_name = (bbs_info.name if bbs_info and bbs_info.name else None) or "Unknown"

            if isinstance(file_data, list):
                msgs = file_data
            else:
                if len(file_data) < BLOCK_SIZE:
                    msgs = []
                else:
                    msgs = list(parse_messages(file_data, None, settings.encoding, headers_only=True))

            counts = defaultdict(int)
            for msg in msgs:
                counts[msg.confnum] += 1

            all_conf_nums = sorted(set(board_dict.keys()) | set(counts.keys()))
            for cnum in all_conf_nums:
                cname = board_dict.get(cnum) or f"Conference {cnum}"
                key = (cnum, cname, bbs_name)
                conferences_map[key] = conferences_map.get(key, 0) + counts.get(cnum, 0)

        except Exception as e:
            logger.error("Failed to load archive %s: %s", input_path, e)

    conf_list = []
    for (cnum, cname, bbs_name), count in sorted(conferences_map.items(), key=lambda x: (x[0][2], x[0][0])):
        conf_list.append({
            "number": cnum,
            "name": cname,
            "message_count": count,
            "bbs_name": bbs_name,
        })

    if not conf_list:
        logger.warning("No conferences found.")
        return

    output = ""
    title = "Conference Areas"
    if settings.format == "json":
        output = json.dumps(conf_list, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        output = _render_conferences_html(conf_list, title)
    elif settings.format == "markdown":
        output = _render_conferences_markdown(conf_list, title)
    elif settings.format == "csv":
        output = _render_conferences_csv(conf_list)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        output = render_conferences_as_text(conf_list, use_colors=use_colors)

    _write_text_output(output, settings.output_path, encoding="utf-8")


def render_authors_as_text(author_list: list[dict[str, Any]], use_colors: bool = True) -> str:
    """Render a list of author entries into a formatted text string."""
    lines = []
    header_str = "Message Authors"
    if use_colors:
        lines.append(_colorize(header_str, "bold", "cyan"))
    else:
        lines.append(header_str)

    sep = "-" * 80
    if use_colors:
        lines.append(_colorize(sep, "dim"))
    else:
        lines.append(sep)

    col_hdr = f"  {'Author':<30} {'Messages':<10} {'First Active':<12} {'Last Active':<12} {'BBS Name':<15}"
    if use_colors:
        lines.append(_colorize(col_hdr, "bold"))
    else:
        lines.append(col_hdr)

    if use_colors:
        lines.append(_colorize(sep, "dim"))
    else:
        lines.append(sep)

    for author_info in author_list:
        author = str(author_info["author"])
        if len(author) > 28:
            author = author[:25] + "..."
        count = str(author_info["message_count"])
        first_act = str(author_info["first_active"] or "N/A")
        last_act = str(author_info["last_active"] or "N/A")
        bbs = str(author_info["bbs_name"] or "Unknown")
        if len(bbs) > 13:
            bbs = bbs[:10] + "..."

        row_str = f"  {author:<30} {count:<10} {first_act:<12} {last_act:<12} {bbs:<15}"
        lines.append(row_str)

    if use_colors:
        lines.append(_colorize(sep, "dim"))
    else:
        lines.append(sep)

    summary_str = f"Total Authors: {len(author_list)}"
    if use_colors:
        lines.append(_colorize(summary_str, "bold", "green"))
    else:
        lines.append(summary_str)

    return "\n".join(lines)


def _render_authors_html(author_list: list[dict[str, Any]], title: str) -> str:
    html_parts = _get_html_header(title)
    html_parts.append(f"<h1>{title}</h1>")
    html_parts.append("<table class='stats-table'>")
    html_parts.append("<thead><tr><th>Author</th><th>Messages</th><th>First Active</th><th>Last Active</th><th>BBS Name</th></tr></thead>")
    html_parts.append("<tbody>")
    for item in author_list:
        html_parts.append(
            f"<tr><td>{html.escape(str(item['author']))}</td>"
            f"<td>{item['message_count']}</td>"
            f"<td>{html.escape(str(item['first_active'] or 'N/A'))}</td>"
            f"<td>{html.escape(str(item['last_active'] or 'N/A'))}</td>"
            f"<td>{html.escape(str(item['bbs_name'] or 'Unknown'))}</td></tr>"
        )
    html_parts.append("</tbody></table>")
    html_parts.extend(_get_html_footer())
    return "\n".join(html_parts)


def _render_authors_markdown(author_list: list[dict[str, Any]], title: str) -> str:
    md_parts = [f"# {title}\n"]
    md_parts.append("| Author | Messages | First Active | Last Active | BBS Name |")
    md_parts.append("|--------|----------|--------------|-------------|----------|")
    for item in author_list:
        md_parts.append(
            f"| {item['author']} | {item['message_count']} | {item['first_active'] or 'N/A'} | {item['last_active'] or 'N/A'} | {item['bbs_name'] or 'Unknown'} |"
        )
    return "\n".join(md_parts)


def _render_authors_csv(author_list: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["author", "message_count", "first_active", "last_active", "bbs_name"])
    writer.writeheader()
    writer.writerows(author_list)
    return output.getvalue()


def show_list_authors(
    input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger
) -> None:
    """Read archives and export a summary list of message authors."""
    all_messages = []
    allowed_conferences = set()
    allowed_exclude_conferences = set()
    user_name = settings.my_name

    # 1. Load messages from all input paths and gather filter criteria
    for input_path in input_paths:
        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, "bbs_info", None)
            if not user_name and bbs_info:
                user_name = bbs_info.user_name
            allowed_conferences.update(get_allowed_conferences(settings.conferences, board_dict))
            allowed_exclude_conferences.update(get_allowed_conferences(settings.exclude_conferences, board_dict))

            if isinstance(file_data, list):
                msgs = file_data
            else:
                if len(file_data) < BLOCK_SIZE:
                    continue
                msgs = list(parse_messages(file_data, None, settings.encoding))

            for msg in msgs:
                msg.confname = msg.confname or board_dict.get(msg.confnum)
                msg.bbs_name = msg.bbs_name or (bbs_info.name if bbs_info else None)
                msg.bbs_id = msg.bbs_id or (bbs_info.bbs_id if bbs_info else None)
                msg.source_file = msg.source_file or os.path.basename(input_path)
            all_messages.extend(msgs)
        except Exception as e:
            logger.error("Failed to load archive %s: %s", input_path, e)

    # 2. Apply settings filters and group by author
    author_stats = defaultdict(lambda: {
        "count": 0,
        "first_dt": None,
        "last_dt": None,
        "bbs_names": set(),
    })

    for msg in all_messages:
        if matches_filters(msg, settings, allowed_conferences, user_name, allowed_exclude_conferences):
            author_name = (msg.header.msgfrom or "").strip() or "Unknown"
            stats = author_stats[author_name]
            stats["count"] += 1
            if msg.datetime:
                if stats["first_dt"] is None or msg.datetime < stats["first_dt"]:
                    stats["first_dt"] = msg.datetime
                if stats["last_dt"] is None or msg.datetime > stats["last_dt"]:
                    stats["last_dt"] = msg.datetime
            bbs_name = (msg.bbs_name or msg.bbs_id or "").strip()
            if bbs_name:
                stats["bbs_names"].add(bbs_name)

    # 4. Build author list sorted by count descending, then author name ascending
    author_list = []
    for author, stats in sorted(author_stats.items(), key=lambda x: (-x[1]["count"], x[0].lower())):
        first_active_str = stats["first_dt"].strftime("%Y-%m-%d") if stats["first_dt"] else None
        last_active_str = stats["last_dt"].strftime("%Y-%m-%d") if stats["last_dt"] else None
        bbs_str = ", ".join(sorted(stats["bbs_names"])) if stats["bbs_names"] else "Unknown"

        author_list.append({
            "author": author,
            "message_count": stats["count"],
            "first_active": first_active_str,
            "last_active": last_active_str,
            "bbs_name": bbs_str,
        })

    if not author_list:
        logger.warning("No message authors found.")
        return

    output = ""
    title = "Message Authors"
    if settings.format == "json":
        output = json.dumps(author_list, indent=4, ensure_ascii=False)
    elif settings.format == "html":
        output = _render_authors_html(author_list, title)
    elif settings.format == "markdown":
        output = _render_authors_markdown(author_list, title)
    elif settings.format == "csv":
        output = _render_authors_csv(author_list)
    else:
        use_colors = (
            not settings.output_path
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )
        output = render_authors_as_text(author_list, use_colors=use_colors)

    _write_text_output(output, settings.output_path, encoding="utf-8")
