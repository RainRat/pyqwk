import sys
import zipfile
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
from dataclasses import asdict, dataclass, field, fields, replace
import mailbox
import email
from contextlib import contextmanager, nullcontext
from typing import Any, Callable, Protocol
import datetime
import email.utils
import sqlite3
import binascii
import base64

__version__ = "0.1.0"

BLOCK_SIZE = 128
MESSAGES_FILENAME = 'messages.dat'
REPLY_FILENAME = 'reply.dat'
CONTROL_FILENAME = 'control.dat'

FORMAT_EXTENSIONS = {
    'text': '.txt',
    'json': '.json',
    'xml': '.xml',
    'html': '.html',
    'markdown': '.md',
    'mbox': '.mbox',
    'csv': '.csv',
    'sqlite': '.db',
    'eml': '.eml',
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
        output_mode: Whether the output is going to a 'file' or 'stdout'.

    Returns:
        The resolved format name (e.g., 'text', 'json', 'html').
    """
    if output_format is None:
        if output_path and output_mode == 'file':
            ext = os.path.splitext(output_path)[1].lower()
            if ext == '.json':
                return 'json'
            if ext == '.xml':
                return 'xml'
            if ext == '.html':
                return 'html'
            if ext == '.csv':
                return 'csv'
            if ext == '.mbox':
                return 'mbox'
            if ext == '.eml':
                return 'eml'
            if ext in ('.md', '.markdown'):
                return 'markdown'
            if ext in ('.sqlite', '.db'):
                return 'sqlite'
        return 'text'
    return output_format

RE_QUOTE_PATTERN = re.compile(r'^\s*[A-Za-z\-\=]{0,4}\s?(>|\xb3|\||\}|│)')
RE_UUE_PATTERN = re.compile(r'^begin\s\d{3}\s')
RE_UUE_DATA_PATTERN = re.compile(r'^M[\x21-\x60]{60}$')
RE_UUE_LOOSE_PATTERN = re.compile(r'[\x21-\x4c][\x21-\x60]{4,60}$')
RE_BASE64_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{60,}$')
RE_YENC_PATTERN = re.compile(r'^=y(begin|part|end)')
RE_BASE64_LOOSE_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{4,}$')
RE_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
RE_PHONE_PATTERN = re.compile(
    r'(?<!\w)'
    r'(?!(?:19|20)\d{2}[-./]\d{2}[-./]\d{2}\b)'
    r'(?=(?:\D*\d){7,})'
    r'(?:'
    r'(?:\+\d{1,3}[-\.\s]?)?'
    r'(?:\(\d{1,4}\)|\d{1,4})'
    r'[-\.\s]?\d{3,4}(?:[-\.\s]?\d{3,4})+'
    r'|'
    r'\d{3}[-\.\s]?\d{4}'
    r')'
    r'\b'
)

RE_SUBJECT_PREFIX_PATTERN = re.compile(
    r'^\s*(?:re|fw|fwd)(?:\[\d+\])?[:\s-]+\s*', re.IGNORECASE
)

RE_ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

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

    Returns a group of four values:
    - A boolean that is True if the line should be hidden.
    - Three booleans representing if we are currently inside a specific type of attachment (yEnc, UUE, or Base64).
    """
    stripped_line = line.strip()
    if in_base64_block:
        if RE_BASE64_LOOSE_PATTERN.match(stripped_line):
            return True, in_yenc_block, in_uue_block, True
        in_base64_block = False

    is_yenc_marker = RE_YENC_PATTERN.match(stripped_line)

    if is_yenc_marker:
        return True, not stripped_line.startswith('=yend'), in_uue_block, in_base64_block

    if in_yenc_block:
        return True, True, in_uue_block, in_base64_block

    if in_uue_block:
        if stripped_line == 'end':
            return True, in_yenc_block, False, in_base64_block
        return True, in_yenc_block, True, in_base64_block

    if RE_BASE64_PATTERN.match(stripped_line):
        return True, in_yenc_block, in_uue_block, True
    elif RE_UUE_DATA_PATTERN.match(stripped_line) or RE_UUE_PATTERN.match(stripped_line):
        return True, in_yenc_block, True, in_base64_block
    elif RE_UUE_LOOSE_PATTERN.match(stripped_line):
        if previous_line and (
            RE_UUE_DATA_PATTERN.match(previous_line)
            or RE_UUE_PATTERN.match(previous_line)
        ):
            return True, in_yenc_block, True, in_base64_block

    return False, in_yenc_block, False, in_base64_block


def _decode_uue(data: list[str]) -> bytes:
    """Helper to decode UUE data blocks."""
    decoded = b""
    for line in data:
        if not line:
            continue
        try:
            # binascii.a2b_uu expects the length character at the start
            decoded += binascii.a2b_uu(line)
        except (binascii.Error, ValueError):
            continue
    return decoded


def _decode_base64(data: list[str]) -> bytes:
    """Helper to decode Base64 data blocks."""
    try:
        return base64.b64decode("".join(data))
    except (binascii.Error, ValueError, TypeError):
        return b""


def _decode_yenc(data: list[str]) -> bytes:
    """Helper to decode yEnc data blocks."""
    try:
        encoded_str = "".join(data)
        decoded_bytes = bytearray()
        escaped = False
        for char in encoded_str:
            if char == '=' and not escaped:
                escaped = True
                continue
            val = ord(char)
            if escaped:
                val = (val - 64) % 256
                escaped = False
            decoded_bytes.append((val - 42) % 256)
        return bytes(decoded_bytes)
    except Exception:
        return b""


def extract_binaries(text: str) -> list[tuple[str, bytes]]:
    """Scan text for attachment blocks (UUE, yEnc, Base64) and decode them.

    Returns:
        A list of (filename, data) tuples.
    """
    lines = text.splitlines()
    binaries: list[tuple[str, bytes]] = []

    in_uue = False
    in_base64 = False
    in_yenc = False

    current_filename = ""
    current_data: list[str] = []

    uue_begin_re = re.compile(r'^begin\s+\d{3}\s+(.+)$')
    yenc_begin_re = re.compile(r'^=ybegin.*name=(.+)$')

    def _flush_binary():
        nonlocal in_uue, in_base64, in_yenc
        decoded = b""
        if in_uue:
            decoded = _decode_uue(current_data)
        elif in_base64:
            decoded = _decode_base64(current_data)
        elif in_yenc:
            decoded = _decode_yenc(current_data)

        if decoded:
            binaries.append((current_filename, decoded))
        in_uue = in_base64 = in_yenc = False

    for line in lines:
        clean_line = line.strip()

        if in_uue:
            if clean_line == 'end' or clean_line == '`':
                _flush_binary()
                continue
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
            if clean_line.startswith('=yend'):
                _flush_binary()
                continue
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


class ProgressBar(Protocol):
    def update(self, __n: int, /) -> None:
        """Advance the progress by ``__n`` units."""


@dataclass
class ProcessingSettings:
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
    regex: bool = False
    dry_run: bool = False
    strip_ansi: bool = False
    quiet: bool = False
    headers_only: bool = False
    merge: bool = False
    unique: bool = False
    organize: bool = False
    organize_by_bbs: bool = False
    include_toc: bool = False
    extract_attachments: bool = False
    msgnum_filters: set[int] | None = None
    conferences: list[str] | None = None
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


@dataclass
class BBSInfo:
    """Information about the BBS that generated the QWK packet."""
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
    source_file: str | None = None
    attachments: list[str] | None = None



# Aliases for backward compatibility
ProcessedMessage = ParsedMessage


@dataclass
class MessageHeader:
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
        return self.status not in (' ', '-')

    @property
    def is_password(self) -> bool:
        """Return True if the message is protected by a password."""
        return self.status in ('%', '^', '!', '#', '$')

    @property
    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            result[field.name] = "" if value is None else value
        return result

    @classmethod
    def from_bytes(cls, record: bytes, encoding: str = 'cp437') -> "MessageHeader":
        try:
            header_data = struct.unpack('<c7s8s5s25s25s25s12s8s6scHHc', record)
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
                s = b.decode(encoding).split('\x00')[0]
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

        valid_status_chars = {'+', '*', '~', '`', '%', '^', '!', '#', '$', ' ', '-'}
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
            if name in ('msgnum', 'refnum', 'numblocks', 'confnum', 'lognum'):
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
    ) -> str:
        """Render a message header into readable text.

        Args:
            board_dict: Mapping of conference numbers to human-readable names.
            verbose: Whether to include extra information such as message numbers and reference numbers.
            include_separator: Whether to prepend the message separator line.
            use_colors: Whether to use ANSI colors for terminal output.
            highlight_term: Optional term to highlight in the header values.
            is_regex: Whether the highlight_term is a regular expression.

        Returns:
            The formatted header text with DOS-style newlines appended.
        """
        not_found_flag = False
        try:
            conf_name = board_dict[self.confnum]
        except KeyError:
            conf_name = str(self.confnum)
            not_found_flag = True

        def fmt_val(val: str) -> str:
            return _highlight_text(val, highlight_term, is_regex, use_colors)

        def fmt_line(label: str, value: str, newline: bool = True, pad: int = 16) -> str:
            suffix = "\r\n" if newline else ""
            label_fmt = f"{label:<{pad}}"
            if use_colors:
                # Use Dim (90) for labels to create better visual hierarchy
                return f"\x1b[90m{label_fmt}\x1b[0m{fmt_val(value)}{suffix}"
            return f"{label_fmt}{value}{suffix}"

        header_parts: list[str] = []
        if include_separator:
            # Match terminal width up to 80 chars for a polished look
            try:
                width = shutil.get_terminal_size().columns
            except (AttributeError, ValueError):  # pragma: no cover
                width = 80
            width = min(80, width)

            sep = ("-" * width) + "\r\n"
            if use_colors:
                sep = f"\x1b[90m{sep}\x1b[0m"
            header_parts.append(sep)

        if verbose or not not_found_flag:
            header_parts.append(fmt_line("Conference:", str(conf_name)))

        if verbose:
            message_number = str(self.msgnum) if self.msgnum is not None else ""
            # Message number and Date share a line in verbose mode for better information density
            header_parts.append(fmt_line("Message #:", message_number, newline=False, pad=16))
            header_parts.append("    ")  # Spacer between columns
            header_parts.append(fmt_line("Date:", self.msgdate + " " + self.msgtime, pad=12))
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
    ) -> str:
        """Render a message header as a single line summary."""
        if conf_name is None:
            conf_name = board_dict.get(self.confnum, str(self.confnum))
        date_str = f"{self.msgdate} {self.msgtime}"
        from_name = self.msgfrom.strip()
        to_name = self.msgto.strip()
        subject = self.msgsubject.strip()

        def prepare_field(text: str, width: int, highlight: bool = True) -> str:
            truncated = text[:width]
            display_len = len(truncated)
            if highlight:
                truncated = _highlight_text(truncated, highlight_term, is_regex, use_colors)
            return truncated + (" " * (width - display_len))

        conf_part = prepare_field(conf_name, 12)
        from_part = prepare_field(from_name, 15)
        to_part = prepare_field(to_name, 15)

        # Apply threading indent to subject
        if depth > 0:
            indent = "  " * (depth - 1)
            subject = f"{indent}└ {subject}"
        subject_part = _highlight_text(subject, highlight_term, is_regex, use_colors)

        msgnum_part = ""
        if verbose:
            msgnum_part = f"{(self.msgnum or ''):<6} "

        return f"{msgnum_part}{conf_part} {date_str:<14} {from_part} {to_part} {subject_part}\r\n"


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


def _parse_sqlite_messages(db_path: str) -> list[ParsedMessage]:
    """Import messages from a pyqwk SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM messages")
    except sqlite3.OperationalError as e:
        conn.close()
        raise ValueError(f"SQLite database is missing the 'messages' table: {e}")

    messages = []
    for row in cursor.fetchall():
        # Reconstruct header dict
        header_dict = {
            'confnum': row['conference_number'],
            'msgnum': row['message_number'],
            'msgdate': row['date'],
            'msgtime': "", # ISO date in SQLite includes time
            'msgfrom': row['author'],
            'msgto': row['recipient'],
            'msgsubject': row['subject'],
            'status': row['status'],
            'refnum': row['reference_number']
        }

        # Add remaining fields with defaults
        for f in fields(MessageHeader):
            if f.name not in header_dict:
                header_dict[f.name] = ""

        header = MessageHeader.from_dict(header_dict)

        attachments = row['attachments'].split(';') if row['attachments'] else []

        msg = ParsedMessage(
            text=row['text'],
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=row['depth'],
            thread_id=row['thread_id'],
            parent_msgnum=row['parent_message_number'],
            confname=row['conference_name'],
            bbs_name=row['bbs_name'],
            source_file=row['source_file'],
            attachments=attachments,
        )
        messages.append(msg)

    conn.close()
    return messages


def _parse_json_messages(data: list[dict[str, Any]]) -> list[ParsedMessage]:
    """Convert a list of dictionaries into ParsedMessage objects."""
    messages = []
    for entry in data:
        header_dict = entry.get('header', {})
        header = MessageHeader.from_dict(header_dict)

        msg = ParsedMessage(
            text=entry.get('text', ""),
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=entry.get('depth', 0),
            thread_id=entry.get('thread_id'),
            parent_msgnum=entry.get('parent_msgnum'),
            confname=entry.get('conference'),
            bbs_name=entry.get('bbs_name'),
            source_file=entry.get('source_file'),
            attachments=entry.get('attachments'),
        )
        messages.append(msg)
    return messages


def _safe_to_int(v: Any) -> int | None:
    """Safely convert a value to an integer, returning None on failure."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _parse_xml_messages(root: ET.Element) -> list[ParsedMessage]:
    """Convert an XML tree into ParsedMessage objects."""
    messages = []
    header_fields = {f.name for f in fields(MessageHeader)}

    for entry in root.findall('message'):
        header_el = entry.find('header')
        header_dict = {}
        if header_el is not None:
            for field_el in header_el:
                if field_el.tag in header_fields:
                    header_dict[field_el.tag] = field_el.text

        header = MessageHeader.from_dict(header_dict)

        attachments_el = entry.find('attachments')
        attachments = []
        if attachments_el is not None:
            for attach_el in attachments_el.findall('attachment'):
                if attach_el.text:
                    attachments.append(attach_el.text)

        def get_text(tag):
            el = entry.find(tag)
            return el.text if el is not None and el.text is not None else ""

        msg = ParsedMessage(
            text=get_text('text'),
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=_safe_to_int(get_text('depth') or 0) or 0,
            thread_id=get_text('thread_id') or None,
            parent_msgnum=_safe_to_int(get_text('parent_msgnum')),
            confname=get_text('conference_name') or get_text('conference'),
            bbs_name=get_text('bbs_name'),
            source_file=get_text('source_file'),
            attachments=attachments or None,
        )
        messages.append(msg)
    return messages


def _parse_csv_messages(data: Iterator[dict[str, Any]]) -> list[ParsedMessage]:
    """Convert CSV rows into ParsedMessage objects."""
    messages = []
    header_fields = {f.name for f in fields(MessageHeader)}

    for row in data:
        header_dict = {k: v for k, v in row.items() if k in header_fields}
        header = MessageHeader.from_dict(header_dict)

        attachments = row.get('attachments', "").split(';') if row.get('attachments') else []

        msg = ParsedMessage(
            text=row.get('text', ""),
            msgnum=header.msgnum,
            refnum=header.refnum,
            confnum=header.confnum,
            header=header,
            depth=_safe_to_int(row.get('depth', 0)) or 0,
            thread_id=row.get('thread_id'),
            parent_msgnum=_safe_to_int(row.get('parent_msgnum')),
            confname=row.get('conference_name') or row.get('conference'),
            bbs_name=row.get('bbs_name'),
            source_file=row.get('source_file'),
            attachments=attachments,
        )
        messages.append(msg)
    return messages


def _message_from_email(msg_obj: Any) -> ParsedMessage:
    """Convert an email message object to a ParsedMessage."""
    # Extract headers
    def get_hdr(name: str) -> str:
        return str(msg_obj.get(name, ""))

    # QWK specific headers (if they exist)
    conf_num = _safe_to_int(get_hdr('X-QWK-Conference')) or 0
    msg_num = _safe_to_int(get_hdr('X-QWK-Message-Number'))
    ref_num = _safe_to_int(get_hdr('X-QWK-Reference'))
    status = get_hdr('X-QWK-Status') or " "
    msg_flag = get_hdr('X-QWK-Flags') or " "
    conf_name = get_hdr('X-QWK-Conference-Name')
    bbs_name = get_hdr('X-QWK-BBS-Name')
    source_file = get_hdr('X-QWK-Source-File')

    # Attachments
    attachments = None
    attach_hdr = get_hdr('X-QWK-Attachments')
    if attach_hdr:
        attachments = [a.strip() for a in attach_hdr.split(';') if a.strip()]

    # Standard Email headers
    msg_to = get_hdr('To')
    msg_from = get_hdr('From')
    msg_subject = get_hdr('Subject')

    # Date/Time
    date_hdr = get_hdr('Date')
    if date_hdr:
        try:
            dt = email.utils.parsedate_to_datetime(date_hdr)
            msg_date = dt.strftime('%m-%d-%y')
            msg_time = dt.strftime('%H:%M')
        except (ValueError, TypeError):
            msg_date = "01-01-70"
            msg_time = "00:00"
    else:
        msg_date = "01-01-70"
        msg_time = "00:00"

    # Message body
    body = ""
    if msg_obj.is_multipart():
        for part in msg_obj.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='replace')
                break
    else:
        payload = msg_obj.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='replace')

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
        depth=_safe_to_int(get_hdr('X-QWK-Depth') or 0) or 0,
        thread_id=get_hdr('X-QWK-Thread-ID') or None,
        parent_msgnum=_safe_to_int(get_hdr('X-QWK-Parent-Msgnum')),
        confname=conf_name or None,
        bbs_name=bbs_name or None,
        source_file=source_file or None,
        attachments=attachments,
    )


def _parse_mbox_messages(path: str) -> list[ParsedMessage]:
    """Import messages from an mbox file."""
    messages = []
    mbox = mailbox.mbox(path)
    for msg_obj in mbox:
        messages.append(_message_from_email(msg_obj))
    return messages


def _parse_eml_messages(path: str) -> list[ParsedMessage]:
    """Import messages from an EML file."""
    with open(path, 'rb') as f:
        msg_obj = email.message_from_binary_file(f)
    return [_message_from_email(msg_obj)]


def load_data(
    input_path: str, logger: logging.Logger, encoding: str = 'cp437'
) -> tuple[bytearray | list[ParsedMessage], dict[int, str]]:
    """Load message and conference information from a QWK packet or raw file.

    Args:
        input_path: Path to either a ``messages.dat`` file or a QWK archive.
        logger: Logger used to report warnings when optional information is missing.
        encoding: The text format to use when reading information.

    Returns:
        A tuple ``(file_data, board_dict)`` where ``file_data`` contains the
        contents of ``messages.dat`` and ``board_dict`` maps conference numbers
        to their names. If conference names are not found, the names will just
        be the conference numbers.

        Note: If you provide a path to a raw ``MESSAGES.DAT`` file, this function
        will also look for an accompanying ``CONTROL.DAT`` file in the same directory
        to automatically load conference information.
    """
    board_dict: dict[int, str] = {}

    if input_path.lower().endswith(('.db', '.sqlite')):
        try:
            messages = _parse_sqlite_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load SQLite archive: {e}")

        # Reconstruct board_dict and bbs_info
        board_dict = ConferenceMap()
        bbs_info = BBSInfo()
        for msg in messages:
            if msg.confnum is not None:
                if msg.confnum not in board_dict or (not board_dict[msg.confnum] and msg.confname):
                    board_dict[msg.confnum] = msg.confname or f"Conference {msg.confnum}"
            if msg.bbs_name:
                bbs_info.name = msg.bbs_name

        board_dict.bbs_info = bbs_info
        return messages, board_dict

    if input_path.lower().endswith('.json'):
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON archive must be a list of messages.")
            messages = _parse_json_messages(data)

            # Reconstruct board_dict and bbs_info if possible
            board_dict = ConferenceMap()
            bbs_info = BBSInfo()
            for msg in messages:
                if msg.confnum is not None and msg.confname:
                    board_dict[msg.confnum] = msg.confname
                if msg.bbs_name:
                    bbs_info.name = msg.bbs_name

            board_dict.bbs_info = bbs_info
            return messages, board_dict

    if input_path.lower().endswith('.mbox'):
        try:
            messages = _parse_mbox_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load mbox archive: {e}")

        # Reconstruct board_dict and bbs_info if possible
        board_dict = ConferenceMap()
        bbs_info = BBSInfo()
        for msg in messages:
            if msg.confnum is not None and msg.confname:
                board_dict[msg.confnum] = msg.confname
            if msg.bbs_name:
                bbs_info.name = msg.bbs_name

        board_dict.bbs_info = bbs_info
        return messages, board_dict

    if input_path.lower().endswith('.eml'):
        try:
            messages = _parse_eml_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load EML file: {e}")

        # Reconstruct board_dict and bbs_info if possible
        board_dict = ConferenceMap()
        bbs_info = BBSInfo()
        for msg in messages:
            if msg.confnum is not None and msg.confname:
                board_dict[msg.confnum] = msg.confname
            if msg.bbs_name:
                bbs_info.name = msg.bbs_name

        board_dict.bbs_info = bbs_info
        return messages, board_dict

    if input_path.lower().endswith('.xml'):
        try:
            tree = ET.parse(input_path)
            root = tree.getroot()
            messages = _parse_xml_messages(root)
        except Exception as e:
            raise ValueError(f"Failed to load XML archive: {e}")

        # Reconstruct board_dict and bbs_info if possible
        board_dict = ConferenceMap()
        bbs_info = BBSInfo()
        for msg in messages:
            if msg.confnum is not None and msg.confname:
                board_dict[msg.confnum] = msg.confname
            if msg.bbs_name:
                bbs_info.name = msg.bbs_name

        board_dict.bbs_info = bbs_info
        return messages, board_dict

    if input_path.lower().endswith('.csv'):
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            messages = _parse_csv_messages(reader)

            # Reconstruct board_dict and bbs_info if possible
            board_dict = ConferenceMap()
            bbs_info = BBSInfo()
            for msg in messages:
                if msg.confnum is not None and msg.confname:
                    board_dict[msg.confnum] = msg.confname
                if msg.bbs_name:
                    bbs_info.name = msg.bbs_name

            board_dict.bbs_info = bbs_info
            return messages, board_dict

    if zipfile.is_zipfile(input_path):
        messages_name = ''
        reply_name = ''
        control_name = ''

        # First try using Python's built-in zipfile
        try:
            with zipfile.ZipFile(input_path) as myzip:
                file_list = myzip.namelist()
                for file_name in file_list:
                    lower_name = file_name.lower()
                    if lower_name == MESSAGES_FILENAME:
                        messages_name = file_name
                    elif lower_name == REPLY_FILENAME:
                        reply_name = file_name
                    if lower_name == CONTROL_FILENAME:
                        control_name = file_name

                # Prioritize MESSAGES.DAT, then REPLY.DAT
                actual_messages_name = messages_name or reply_name

                if not actual_messages_name:
                    raise FileNotFoundError(
                        f"Error: Neither '{MESSAGES_FILENAME}' nor '{REPLY_FILENAME}' found in the zip archive {input_path}."
                    )
                
                # Check if we can actually read the messages file
                with myzip.open(actual_messages_name) as f:
                    file_data = bytearray(f.read())
                
                if control_name:
                    with myzip.open(control_name) as f:
                        control_data = f.read().splitlines()
                    board_dict = _parse_control_dat(control_data, logger, encoding)
                else:
                    logger.warning("CONTROL.DAT not found, conference names will not be available.")
                    
        except (RuntimeError, NotImplementedError, zipfile.BadZipFile) as e:
            # Fallback to system 'unzip' if built-in zipfile fails (e.g., unsupported compression)
            logger.info("Built-in zipfile failed (%s); attempting fallback to system 'unzip'.", str(e))
            
            abs_input_path = os.path.abspath(input_path)
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Extract everything to temp_dir to handle case sensitivity and unsupported methods
                    cmd = ['unzip', '-o', '-j', abs_input_path]
                    
                    # We allow exit code 1 (warnings) and 11 (some files not matched - though we don't specify any here)
                    # But status 0 is preferred. unzip -j extracts all files into the current dir.
                    result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)
                    
                    if result.returncode not in (0, 1):
                         raise RuntimeError(f"unzip failed with return code {result.returncode}: {result.stderr}")
                    
                    # Find extracted files (case-insensitive search in temp_dir)
                    extracted_files = os.listdir(temp_dir)
                    extracted_messages = None
                    extracted_reply = None
                    extracted_control = None

                    for f_name in extracted_files:
                        lower_f = f_name.lower()
                        if lower_f == MESSAGES_FILENAME:
                            extracted_messages = os.path.join(temp_dir, f_name)
                        elif lower_f == REPLY_FILENAME:
                            extracted_reply = os.path.join(temp_dir, f_name)
                        if lower_f == CONTROL_FILENAME:
                            extracted_control = os.path.join(temp_dir, f_name)

                    actual_extracted = extracted_messages or extracted_reply

                    if not actual_extracted or not os.path.exists(actual_extracted):
                        raise FileNotFoundError(f"Could not extract {MESSAGES_FILENAME} or {REPLY_FILENAME} from {input_path}")

                    with open(actual_extracted, 'rb') as f:
                        file_data = bytearray(f.read())
                        
                    if extracted_control and os.path.exists(extracted_control):
                        with open(extracted_control, 'rb') as f:
                            control_data = f.read().splitlines()
                        board_dict = _parse_control_dat(control_data, logger, encoding)
                    else:
                        logger.warning("CONTROL.DAT not found in the zip archive.")
                        
                except subprocess.CalledProcessError as sub_e:
                    raise RuntimeError(f"Failed to extract older ZIP archive using 'unzip': {sub_e.stderr}") from sub_e
                except Exception as final_e:
                    raise RuntimeError(f"An error occurred while handling older ZIP archive: {str(final_e)}") from final_e
    else:
        with open(input_path, 'rb') as f:
            file_data = bytearray(f.read())

        # If the file is MESSAGES.DAT, look for an accompanying CONTROL.DAT in the same folder
        if os.path.basename(input_path).lower() == MESSAGES_FILENAME:
            parent_dir = os.path.dirname(input_path)
            control_path = os.path.join(parent_dir, CONTROL_FILENAME)

            # Check for case-insensitive CONTROL.DAT
            if not os.path.exists(control_path):
                # Try all files in the directory to find a match
                if os.path.isdir(parent_dir or '.'):
                    for filename in os.listdir(parent_dir or '.'):
                        if filename.lower() == CONTROL_FILENAME:
                            control_path = os.path.join(parent_dir, filename)
                            break

            if os.path.exists(control_path) and not os.path.isdir(control_path):
                try:
                    with open(control_path, 'rb') as f:
                        control_data = f.read().splitlines()
                    board_dict = _parse_control_dat(control_data, logger, encoding)
                    logger.info("Found accompanying %s; loaded conference names.", os.path.basename(control_path))
                except Exception as e:
                    logger.warning("Found accompanying CONTROL.DAT but failed to parse it: %s", str(e))

    return file_data, board_dict


def _parse_control_dat(
    control_data: list[bytes],
    logger: logging.Logger | None = None,
    encoding: str = 'cp437',
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
            return b.decode('latin1').strip()

    bbs_info.name = dec(control_data[0])
    bbs_info.location = dec(control_data[1])
    bbs_info.phone = dec(control_data[2])
    bbs_info.sysop = dec(control_data[3])

    line5 = dec(control_data[4]).split(',', 1)
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
    encoding: str = 'cp437',
    headers_only: bool = False,
) -> Iterator[ParsedMessage]:
    """Convert the raw data from a QWK message file into a list of messages.

    Args:
        file_data: Raw bytes from a messages.dat file.
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
    message_buffer = ''
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
        record = file_data[i:i + BLOCK_SIZE]
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

            message_buffer = ''
            if header.numblocks is None or header.numblocks < 1:
                logging.warning(
                    "Invalid block count '%s' in message header at offset %s; skipping message.",
                    getattr(header, '_numblocks_raw', header.numblocks),
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
                temp_record = record.replace(b'\xe3', b'\r\n').decode(encoding)
                if blocks_remaining == 1:
                    temp_record = temp_record.rstrip() + '\r\n'
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


def process_message(
    message_buffer: str,
    truncate_signatures: bool,
    cut_quoting: bool,
    binaries_removal: bool,
    redact_pii: bool,
    strip_ansi: bool = False,
) -> str:
    """Clean up and format a raw message body.

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
    message_buffer = message_buffer.lstrip('\r\n').rstrip()
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
            elif j > 0 and j < (len(lines) - 1) \
                and RE_QUOTE_PATTERN.match(lines[j - 1]) \
                and RE_QUOTE_PATTERN.match(lines[j + 1]):
                continue
        if binaries_removal:
            should_skip, in_yenc_block, in_uue_block, in_base64_block = _is_binary_line(
                line, previous_line, in_yenc_block, in_uue_block, in_base64_block
            )
            if should_skip:
                previous_line = line
                continue

        if redact_pii:
            line = RE_EMAIL_PATTERN.sub('[EMAIL]', line)
            line = RE_PHONE_PATTERN.sub('[PHONE]', line)
        if strip_ansi:
            line = RE_ANSI_ESCAPE_PATTERN.sub('', line)
        new_lines.append(line)
        previous_line = line

    return '\r\n'.join(new_lines) + '\r\n'


def _create_progress_bar(total: int, quiet: bool, desc: str = 'Processing messages') -> Any:
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
            unit='B',
            unit_scale=True,
            desc=desc,
        )
    except ImportError:  # pragma: no cover - tqdm is optional
        if not getattr(_create_progress_bar, "_logged_missing_tqdm", False):
            logging.getLogger(__name__).info('Install tqdm to enable progress reporting.')
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
) -> bool:
    """Check if a message satisfies all configured processing filters.

    Args:
        message: The message to evaluate.
        settings: Processing settings containing filter criteria.
        allowed_conferences: Pre-computed set of allowed conference numbers.
        user_name: The user's name to use for the "mine" filter.

    Returns:
        True if the message matches all filters, False otherwise.
    """
    # 1. Private/Password Check
    if (not settings.private and message.header.is_private) or message.header.is_password:
        return False

    # 2. Conference Filter
    if settings.conferences and message.confnum not in allowed_conferences:
        return False

    # 2b. Mine Filter
    if settings.mine and user_name:
        is_from_me = user_name.lower() in message.header.msgfrom.lower()
        is_to_me = user_name.lower() in message.header.msgto.lower()
        if not (is_from_me or is_to_me):
            return False

    # 3. Message Number Filter
    if settings.msgnum_filters and message.msgnum is not None:
        if message.msgnum not in settings.msgnum_filters:
            return False

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
        return any(check_str_match(p, text) for p in patterns)

    # 4. Author Filter
    if settings.authors and not any_match(settings.authors, message.header.msgfrom):
        return False

    # 5. Recipient Filter
    if settings.recipients and not any_match(settings.recipients, message.header.msgto):
        return False

    # 6. Subject Filter
    if settings.subjects and not any_match(settings.subjects, message.header.msgsubject):
        return False

    # 7. Full-Text Search
    if settings.search_term:
        found = (
            check_str_match(settings.search_term, message.header.msgfrom)
            or check_str_match(settings.search_term, message.header.msgto)
            or check_str_match(settings.search_term, message.header.msgsubject)
            or check_str_match(settings.search_term, message.text)
        )
        if not found:
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
    if settings.has_attachments or settings.extract_attachments:
        if message.text and message.attachments is None:
            found = extract_binaries(message.text)
            message.attachments = [name for name, data in found]

        if settings.has_attachments and not message.attachments:
            return False

    return True


def _slugify(text: str, default: str) -> str:
    """Create a safe name for a file or folder by removing special characters."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()[:30]
    return slug if slug else default


def _generate_safe_filename(message: ParsedMessage, output_format: str, count: int) -> str:
    """Generate a human-readable filename for an individual message."""
    ext = FORMAT_EXTENSIONS.get(output_format, '.txt')

    msg_num = message.msgnum if message.msgnum is not None else count
    slug = _slugify(message.header.msgsubject, "message")

    return f"{message.confnum:03d}-{msg_num:05d}-{slug}{ext}"


def _get_message_text_for_format(
    settings: ProcessingSettings,
    processed_buffer: str,
    cleaned_body: str,
) -> str:
    """Determine the appropriate text content for a message based on the output format."""
    if settings.format in ('json', 'xml', 'csv', 'sqlite', 'mbox', 'eml'):
        if settings.headers_only:
            return ""

    if settings.format in ('json', 'xml', 'csv', 'sqlite', 'mbox', 'eml', 'html', 'markdown'):
        return cleaned_body if settings.oneline else processed_buffer

    return processed_buffer


def process_merged_files(
    input_paths: list[str],
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:
    """Read multiple archives, filter and clean the messages, and save the results.

    This function handles the main workflow of finding messages, applying filters,
    cleaning the text, and writing the output to files or the screen.
    """
    output_mode = settings.output_mode
    resolved_output_path = settings.output_path

    if output_mode == 'stdout' and resolved_output_path is not None:
        raise ValueError('Output path cannot be provided when output mode is stdout.')
    if (
        not settings.individual_files
        and output_mode == 'file'
        and resolved_output_path is None
    ):
        raise ValueError('An output path is required when output mode is file.')

    output_dir: str | None = None
    if settings.individual_files:
        if resolved_output_path is None:
            raise ValueError('An output path is required when using individual files.')
        output_dir = resolved_output_path
        if os.path.exists(output_dir) and not os.path.isdir(output_dir):
            raise ValueError('The output path must be a folder when using individual files.')
        os.makedirs(output_dir, exist_ok=True)

    collected_messages: list[ParsedMessage] = []
    seen_ids: set[tuple[str, int, int | str]] = set()

    separator_mode = settings.separator
    if separator_mode == 'auto':
        if settings.individual_files or settings.format in (
            'json', 'xml', 'html', 'csv', 'markdown', 'sqlite', 'mbox', 'eml'
        ):
            separator_mode = 'none'
        else:
            separator_mode = 'dashes'
    separator_str = ""
    if separator_mode == 'dashes':
        separator_str = ("-" * 80) + "\r\n"
    elif separator_mode == 'blank':
        separator_str = "\r\n"

    total_matching = 0
    processed_count = 0
    estimated_bytes = 0
    potential_files = 0
    use_streaming = not (settings.sort or settings.reverse)
    sort_buffer: list[tuple[ParsedMessage, dict[int, str]]] = []
    collected_for_index: list[dict[str, Any]] = []
    bbs_info_to_use = None
    total_attachments = 0

    use_colors = (
        output_mode == 'stdout'
        and hasattr(sys.stdout, 'isatty')
        and sys.stdout.isatty()
    )
    include_header = not settings.no_header and settings.format == 'text'
    target_encoding = 'utf-8'
    if settings.individual_files and settings.format == 'text':
        target_encoding = settings.encoding

    def handle_output(parsed_message: ParsedMessage, board_dict: dict[int, str]) -> bool:
        """Process and output a single message. Returns True if processing should stop."""
        nonlocal total_matching, processed_count, estimated_bytes, potential_files, collected_for_index

        total_matching += 1
        if settings.skip is not None and total_matching <= settings.skip:
            return False

        if settings.limit is not None and processed_count >= settings.limit:
            return True
        processed_count += 1

        if settings.extract_attachments and parsed_message.text:
            # Re-scan to get binary data for extraction
            found_attachments = extract_binaries(parsed_message.text)

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

                if not settings.dry_run:
                    os.makedirs(attach_dir, exist_ok=True)
                    for filename, data in found_attachments:
                        # Sanitize filename to prevent path traversal
                        filename = os.path.basename(filename)
                        if not filename:
                            filename = "attachment.bin"

                        total_attachments += 1
                        base, ext = os.path.splitext(filename)
                        target_path = os.path.join(attach_dir, filename)
                        counter = 1
                        while os.path.exists(target_path):
                            target_path = os.path.join(attach_dir, f"{base}_{counter}{ext}")
                            counter += 1
                        with open(target_path, 'wb') as f:
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

            # Apply search highlighting to body for terminal output
            cleaned_body = _highlight_text(
                cleaned_body,
                settings.search_term,
                settings.regex,
                use_colors=use_colors
            )

        if settings.oneline:
            processed_buffer = parsed_message.header.format_oneline(
                board_dict,
                use_colors=use_colors,
                highlight_term=settings.search_term,
                is_regex=settings.regex,
                verbose=settings.verbose,
                depth=parsed_message.depth,
                conf_name=parsed_message.confname,
            )
        else:
            processed_buffer = cleaned_body

            if include_header:
                leading_newlines = 0
                text_prefix = parsed_message.text
                while text_prefix.startswith('\r\n'):
                    leading_newlines += 1
                    text_prefix = text_prefix[2:]
                if leading_newlines and not processed_buffer.startswith('\r\n'):
                    processed_buffer = ('\r\n' * leading_newlines) + processed_buffer

                header_text = parsed_message.header.format_text(
                    board_dict,
                    settings.verbose,
                    include_separator=False,
                    use_colors=use_colors,
                    highlight_term=settings.search_term,
                    is_regex=settings.regex,
                    attachments=parsed_message.attachments,
                )
                processed_buffer = header_text + processed_buffer

            # Add separator for text format, or if headers are enabled (legacy behavior for non-text formats)
            if settings.format == 'text' or include_header:
                processed_buffer = separator_str + processed_buffer

        # Determine appropriate text content for structured formats
        text_content = _get_message_text_for_format(settings, processed_buffer, cleaned_body)
        temp_msg = replace(parsed_message, text=text_content)

        if settings.individual_files:
            assert output_dir is not None

            target_dir = output_dir
            conf_dir = ""
            if settings.organize:
                conf_name = parsed_message.confname or "unknown"
                conf_slug = _slugify(conf_name, "conference")
                conf_dir = f"{parsed_message.confnum:03d}-{conf_slug}"
                target_dir = os.path.join(output_dir, conf_dir)
                os.makedirs(target_dir, exist_ok=True)

            attachment_prefix = None
            if settings.extract_attachments:
                attachment_prefix = "../attachments/" if settings.organize else "attachments/"

            if settings.format == 'text':
                encoded_buffer = processed_buffer.encode(target_encoding)
            elif settings.format == 'json':
                encoded_buffer = json.dumps(
                    _message_to_dict(temp_msg), indent=4, ensure_ascii=False
                ).encode(target_encoding)
            elif settings.format == 'xml':
                encoded_buffer = _xml_element_to_str(_message_to_xml_element(temp_msg)).encode(target_encoding)
            elif settings.format == 'html':
                encoded_buffer = _serialize_message_html(
                    temp_msg,
                    attachment_prefix=attachment_prefix,
                    search_term=settings.search_term,
                    is_regex=settings.regex,
                ).encode(target_encoding)
            elif settings.format == 'markdown':
                encoded_buffer = _serialize_message_markdown(
                    temp_msg,
                    attachment_prefix=attachment_prefix,
                    search_term=settings.search_term,
                    is_regex=settings.regex,
                ).encode(target_encoding)
            elif settings.format == 'mbox':
                encoded_buffer = _serialize_message_mbox(temp_msg).encode(target_encoding)
            elif settings.format == 'eml':
                encoded_buffer = _serialize_message_eml(temp_msg).encode(target_encoding)
            else:
                encoded_buffer = processed_buffer.encode(target_encoding)

            filename = _generate_safe_filename(parsed_message, settings.format, processed_count)
            full_path = os.path.join(target_dir, filename)

            # Collision avoidance
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

            if settings.format in ('html', 'markdown'):
                rel_path = os.path.join(conf_dir if settings.organize else "", filename)
                collected_for_index.append({
                    'path': rel_path,
                    'subject': parsed_message.header.msgsubject.strip(),
                    'from': parsed_message.header.msgfrom.strip(),
                    'to': parsed_message.header.msgto.strip(),
                    'date': f"{parsed_message.header.msgdate} {parsed_message.header.msgtime}",
                    'conf_num': parsed_message.confnum,
                    'conf_name': parsed_message.confname or f"Conference {parsed_message.confnum}",
                    'msgnum': parsed_message.header.msgnum,
                    'attachments': parsed_message.attachments,
                })

            if not settings.dry_run:
                with open(full_path, 'wb') as f:
                    f.write(encoded_buffer)
        else:
            estimated_bytes += len(processed_buffer.encode('utf-8'))
            if not settings.dry_run:
                collected_messages.append(temp_msg)
        return False

    for input_path in input_paths:
        file_data, board_dict = load_data(input_path, logger, settings.encoding)
        bbs_info = getattr(board_dict, 'bbs_info', None)
        user_name = bbs_info.user_name if bbs_info else None
        if bbs_info and not bbs_info_to_use:
            bbs_info_to_use = bbs_info
        bbs_key = f"{bbs_info.name}|{bbs_info.bbs_id}" if bbs_info else ""

        allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)

        desc = f"Processing {os.path.basename(input_path)}"

        if isinstance(file_data, list):
            # For pre-parsed messages (JSON), we iterate directly
            messages_to_process = file_data
            total_progress = len(file_data)
            progress_unit = 'msg'
        else:
            # For raw data, we use parse_messages
            messages_to_process = parse_messages(
                file_data,
                None, # Will be set below
                settings.encoding,
                settings.headers_only,
            )
            total_progress = len(file_data)
            progress_unit = 'B'

        with _create_progress_bar(total_progress, settings.quiet, desc=desc) as progress_bar:
            if progress_bar is not None:
                if progress_unit == 'msg':
                    # tqdm settings for message count
                    progress_bar.unit = 'msg'
                    progress_bar.unit_scale = False
                else:
                    # If it's a bytearray and we're using parse_messages,
                    # we need to pass the progress bar to it.
                    messages_to_process = parse_messages(
                        file_data,
                        progress_bar,
                        settings.encoding,
                        settings.headers_only,
                    )

            for parsed_message in messages_to_process:
                if isinstance(file_data, list) and progress_bar is not None:
                    progress_bar.update(1)

                parsed_message = replace(
                    parsed_message,
                    confname=board_dict.get(parsed_message.confnum),
                    bbs_name=bbs_info.name if bbs_info else None,
                    source_file=os.path.basename(input_path),
                )
                if not matches_filters(parsed_message, settings, allowed_conferences, user_name):
                    continue

                if settings.unique:
                    msg_id: tuple[str, int, int | str]
                    if parsed_message.msgnum is not None:
                        msg_id = (bbs_key, parsed_message.confnum, parsed_message.msgnum)
                    else:
                        content_hash = hashlib.sha1(
                            parsed_message.text.encode(settings.encoding, errors='replace')
                        ).hexdigest()
                        msg_id = (bbs_key, parsed_message.confnum, content_hash)

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
        if settings.sort:
            if settings.sort == 'date':
                sort_buffer.sort(key=lambda x: _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime))
            elif settings.sort == 'author':
                sort_buffer.sort(key=lambda x: x[0].header.msgfrom.lower())
            elif settings.sort == 'to':
                sort_buffer.sort(key=lambda x: x[0].header.msgto.lower())
            elif settings.sort == 'subject':
                sort_buffer.sort(key=lambda x: x[0].header.msgsubject.lower())
            elif settings.sort == 'num':
                sort_buffer.sort(key=lambda x: (x[0].confnum, x[0].msgnum or 0))
            elif settings.sort == 'conference':
                sort_buffer.sort(key=lambda x: (x[0].confnum, _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime)))

        if settings.reverse:
            sort_buffer.reverse()

        for parsed_message, board_dict in sort_buffer:
            if handle_output(parsed_message, board_dict):
                break

    if settings.individual_files:
        if not settings.dry_run and collected_for_index:
            _write_index(collected_for_index, resolved_output_path, settings, bbs_info_to_use)
    else:
        if not settings.dry_run:
            ordered_messages = (
                _order_messages_by_thread(collected_messages)
                if settings.threaded
                else collected_messages
            )
            write_messages(
                ordered_messages, resolved_output_path, settings, bbs_info_to_use
            )
        else:
            potential_files = 1

    if not settings.dry_run and not settings.quiet:
        BOLD = "1"
        GREEN = "32"

        count_label = "message" if processed_count == 1 else "messages"
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
        if use_colors:
            print(f"\n\033[{BOLD};{GREEN}m{msg}\033[0m")
        else:
            print(f"\n{msg}")

    if settings.dry_run:
        CYAN = "36"
        BOLD = "1"
        print(f"\n{_colorize('--- Dry Run Summary ---', BOLD, CYAN)}")
        print(f"Archives processed: {len(input_paths)}")
        print(f"Matching messages:  {processed_count}")
        if total_attachments > 0:
            print(f"Attachments:        {total_attachments}")
        if settings.individual_files:
            print(f"Files to create:    {potential_files}")
        else:
            print(f"Files to create:    1 (merged)")

        size_str = f"{estimated_bytes / 1024:.1f} KB" if estimated_bytes < 1024 * 1024 else f"{estimated_bytes / (1024 * 1024):.1f} MB"
        print(f"Estimated size:     {size_str}")
        print(f"{_colorize('No changes were made to the disk.', BOLD)}")


def process_file(
    input_path: str,
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:
    process_merged_files([input_path], settings, logger)


def _message_to_dict(message: ProcessedMessage) -> dict[str, Any]:
    return {
        'header': message.header.as_dict,
        'conference': message.confname,
        'bbs_name': message.bbs_name,
        'source_file': message.source_file,
        'text': message.text,
        'depth': message.depth,
        'thread_id': message.thread_id,
        'parent_msgnum': message.parent_msgnum,
        'attachments': message.attachments or [],
    }


def _write_json(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    output_data = [_message_to_dict(msg) for msg in messages]
    output_json = json.dumps(output_data, indent=4, ensure_ascii=False)
    _write_text_output(output_json, output_path, encoding='utf-8')


XML_INVALID_CHAR_PATTERN = re.compile(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]')


def _message_to_xml_element(message: ProcessedMessage) -> ET.Element:
    """Convert a message to an XML Element."""
    msg_element = ET.Element('message')

    if message.depth > 0:
        ET.SubElement(msg_element, 'depth').text = str(message.depth)
    if message.thread_id:
        ET.SubElement(msg_element, 'thread_id').text = str(message.thread_id)
    if message.parent_msgnum is not None:
        ET.SubElement(msg_element, 'parent_msgnum').text = str(message.parent_msgnum)

    if message.confname:
        ET.SubElement(msg_element, 'conference_name').text = message.confname
    if message.bbs_name:
        ET.SubElement(msg_element, 'bbs_name').text = message.bbs_name
    if message.source_file:
        ET.SubElement(msg_element, 'source_file').text = message.source_file

    header_element = ET.SubElement(msg_element, 'header')
    header_data = message.header.as_dict
    for key, value in header_data.items():
        child = ET.SubElement(header_element, key)
        child.text = XML_INVALID_CHAR_PATTERN.sub('', str(value))

    text_element = ET.SubElement(msg_element, 'text')
    text_element.text = XML_INVALID_CHAR_PATTERN.sub('', message.text)

    if message.attachments:
        attachments_element = ET.SubElement(msg_element, 'attachments')
        for filename in message.attachments:
            ET.SubElement(attachments_element, 'attachment').text = filename

    return msg_element


def _xml_element_to_str(element: ET.Element) -> str:
    """Helper to indent and serialize an XML element to a string."""
    ET.indent(element, space='  ')
    return ET.tostring(element, encoding='unicode')



def _write_xml(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    root = ET.Element('messages')
    for message in messages:
        msg_element = _message_to_xml_element(message)
        root.append(msg_element)

    xml_text = _xml_element_to_str(root)
    _write_text_output(xml_text, output_path, encoding='utf-8')


def _get_html_header(title: str) -> list[str]:
    return [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="utf-8" />',
        f'<title>{html.escape(title)}</title>',
        '<style>',
        '.reply { margin-left: 2em; border-left: 2px solid #ccc; padding-left: 1em; }',
        '.message { margin-bottom: 1em; border: 1px solid #eee; padding: 1em; }',
        '.header { background-color: #f9f9f9; padding: 0.5em; margin-bottom: 0.5em; }',
        '.body { white-space: pre-wrap; font-family: monospace; }',
        '</style>',
        '</head>',
        '<body>',
    ]


def _get_html_footer() -> list[str]:
    return [
        '</body>',
        '</html>',
    ]


def _render_single_message_html(
    message: ProcessedMessage,
    msg_id: str | None = None,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> list[str]:
    parts = []
    id_attr = f' id="{msg_id}"' if msg_id else ""
    parts.append(f'<div class="message"{id_attr}>')

    def h_esc(text: str) -> str:
        return _apply_highlighting(
            text, search_term, is_regex, "<mark>", "</mark>", escape_func=html.escape
        )

    # Header
    header = message.header
    parts.append('<div class="header">')
    parts.append(f'<div><strong>Date:</strong> {html.escape(header.msgdate)} {html.escape(header.msgtime)}</div>')
    parts.append(f'<div><strong>From:</strong> {h_esc(header.msgfrom)}</div>')
    parts.append(f'<div><strong>To:</strong> {h_esc(header.msgto)}</div>')
    parts.append(f'<div><strong>Subject:</strong> {h_esc(header.msgsubject)}</div>')

    conf_name = message.confname or f"Conference {header.confnum}"
    parts.append(f'<div><strong>Conference:</strong> {h_esc(conf_name)} ({header.confnum})</div>')

    if message.bbs_name:
        parts.append(f'<div><strong>BBS:</strong> {h_esc(message.bbs_name)}</div>')
    if message.source_file:
        parts.append(f'<div><strong>Source:</strong> {h_esc(message.source_file)}</div>')

    if header.msgnum is not None:
        parts.append(f'<div><strong>Number:</strong> {header.msgnum}</div>')

    if message.attachments:
        links = []
        for filename in message.attachments:
            if attachment_prefix:
                links.append(f'<a href="{attachment_prefix}{html.escape(filename)}">{html.escape(filename)}</a>')
            else:
                links.append(html.escape(filename))
        parts.append(f'<div><strong>Attachments:</strong> {", ".join(links)}</div>')

    parts.append('</div>')

    # Body
    escaped_text = h_esc(message.text.replace('\r\n', '\n'))
    parts.append('<pre class="body">')
    parts.append(escaped_text)
    parts.append('</pre>')
    parts.append('</div>')

    return parts


def _serialize_message_html(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> str:
    title = f"Search Results for '{search_term}'" if search_term else 'QWK Message'
    html_parts = _get_html_header(title)
    html_parts.extend(
        _render_single_message_html(
            message,
            attachment_prefix=attachment_prefix,
            search_term=search_term,
            is_regex=is_regex,
        )
    )
    html_parts.extend(_get_html_footer())

    return '\n'.join(html_parts)


def _render_single_message_markdown(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> list[str]:
    header = message.header
    parts = []

    def md_high(text: str) -> str:
        return _apply_highlighting(
            text, search_term, is_regex, "**", "**"
        )

    parts.append(f"## {md_high(header.msgsubject)}")
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
    parts.append(md_high(message.text.replace('\r\n', '\n')))
    parts.append("")
    parts.append("---")
    return parts


def _serialize_message_markdown(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> str:
    title = f"Search Results for '{search_term}'" if search_term else 'QWK Message'
    md_parts = [f"# {title}\n"]
    md_parts.extend(
        _render_single_message_markdown(
            message,
            attachment_prefix=attachment_prefix,
            search_term=search_term,
            is_regex=is_regex,
        )
    )
    return '\n'.join(md_parts)


def _write_html(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    title = 'QWK Messages'
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Archive"

    if settings and settings.search_term:
        title = f"Search Results for '{settings.search_term}' - {title}"

    search_term = settings.search_term if settings else None
    is_regex = settings.regex if settings else False

    html_parts = _get_html_header(title)
    attachment_prefix = "attachments/" if settings and settings.extract_attachments else None

    if settings and settings.include_toc:
        html_parts.append(f"<h1>{html.escape(title)}</h1>")
        if bbs_info:
            html_parts.append('<div class="bbs-info">')
            if bbs_info.sysop:
                html_parts.append(f'<div><strong>SysOp:</strong> {html.escape(bbs_info.sysop)}</div>')
            if bbs_info.location:
                html_parts.append(f'<div><strong>Location:</strong> {html.escape(bbs_info.location)}</div>')
            if bbs_info.packet_at:
                html_parts.append(f'<div><strong>Packet Date:</strong> {html.escape(bbs_info.packet_at)}</div>')
            html_parts.append(f'<div><strong>Total Messages:</strong> {len(messages)}</div>')
            html_parts.append('</div>')

        html_parts.append("<h2>Conferences</h2>")
        html_parts.append("<ul>")
        seen_confs = set()
        for i, msg in enumerate(messages):
            if msg.confnum not in seen_confs:
                conf_name = msg.confname or f"Conference {msg.confnum}"
                html_parts.append(f'<li><a href="#conf-{msg.confnum}">{html.escape(conf_name)} (Conf {msg.confnum})</a></li>')
                seen_confs.add(msg.confnum)
        html_parts.append("</ul>")
        html_parts.append("<hr>")

    current_depth = 0
    last_confnum = None

    for i, message in enumerate(messages):
        if settings and settings.include_toc and message.confnum != last_confnum:
            conf_name = message.confname or f"Conference {message.confnum}"
            html_parts.append(f'<h2 id="conf-{message.confnum}">{html.escape(conf_name)}</h2>')
            last_confnum = message.confnum

        while current_depth < message.depth:
            html_parts.append('<div class="reply">')
            current_depth += 1
        while current_depth > message.depth:
            html_parts.append('</div>')
            current_depth -= 1

        msg_id = f"msg-{i}" if settings and settings.include_toc else None
        html_parts.extend(
            _render_single_message_html(
                message,
                msg_id=msg_id,
                attachment_prefix=attachment_prefix,
                search_term=search_term,
                is_regex=is_regex,
            )
        )

    while current_depth > 0:
        html_parts.append('</div>')
        current_depth -= 1

    html_parts.extend(_get_html_footer())

    _write_text_output('\n'.join(html_parts), output_path, encoding='utf-8')


def _write_markdown(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    title = 'QWK Messages'
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Archive"

    if settings and settings.search_term:
        title = f"Search Results for '{settings.search_term}' - {title}"

    search_term = settings.search_term if settings else None
    is_regex = settings.regex if settings else False

    md_parts = [f"# {title}\n"]
    attachment_prefix = "attachments/" if settings and settings.extract_attachments else None

    if settings and settings.include_toc:
        if bbs_info:
            if bbs_info.sysop:
                md_parts.append(f"- **SysOp:** {bbs_info.sysop}")
            if bbs_info.location:
                md_parts.append(f"- **Location:** {bbs_info.location}")
            if bbs_info.packet_at:
                md_parts.append(f"- **Packet Date:** {bbs_info.packet_at}")
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
    for message in messages:
        if settings and settings.include_toc and message.confnum != last_confnum:
            conf_name = message.confname or f"Conference {message.confnum}"
            md_parts.append(f"## {conf_name} <a name=\"conf-{message.confnum}\"></a>\n")
            last_confnum = message.confnum

        single_md = _render_single_message_markdown(
            message,
            attachment_prefix=attachment_prefix,
            search_term=search_term,
            is_regex=is_regex,
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

    _write_text_output('\n'.join(md_parts), output_path, encoding='utf-8')


def _parse_qwk_date(msgdate: str, msgtime: str) -> datetime.datetime:
    """Convert a QWK date and time into a standard Python date object.

    If the date is invalid, it returns a default date of 1970-01-01.
    """
    try:
        # Handle ISO 8601 format (used in SQLite exports)
        if 'T' in msgdate:
            return datetime.datetime.fromisoformat(msgdate)

        # Normalize date separators
        msgdate = msgdate.replace('/', '-')

        month, day, year = map(int, msgdate.split('-'))
        hour, minute = map(int, msgtime.split(':'))

        # Handle Year 2000 problem (sliding window)
        # If year is < 80, assume 2000s, else 1900s
        if year < 100:
            if year < 80:
                year += 2000
            else:
                year += 1900

        return datetime.datetime(year, month, day, hour, minute)
    except ValueError:
        # Fallback for invalid dates
        return datetime.datetime(1970, 1, 1, 0, 0)


def _serialize_rfc822(message: ProcessedMessage, include_mbox_header: bool = True) -> str:
    """Serialize a message to RFC 822 (Email) format with optional MBOX header.

    Includes standard email headers for threading (Message-ID, In-Reply-To, References)
    and custom X-QWK headers for conference names, message numbers, and statuses.
    """
    header = message.header

    # Parse date
    dt = _parse_qwk_date(header.msgdate, header.msgtime)

    # Format dates
    # "From " line uses ctime format: "Day Mon DD HH:MM:SS YYYY"
    # email.utils.formatdate uses RFC 2822

    from_line_date = dt.ctime()
    rfc_date = email.utils.format_datetime(dt)

    # Escape "From " lines in body
    body_lines = []
    for line in message.text.splitlines():
        if line.startswith("From "):
            body_lines.append(">" + line)
        else:
            body_lines.append(line)
    body = "\n".join(body_lines)

    parts = []
    if include_mbox_header:
        if "@" in header.msgfrom:
            sender_addr = header.msgfrom
        else:
            # Create a safe address from the name
            safe_name = re.sub(r'[^A-Za-z0-9]', '.', header.msgfrom).strip('.')
            sender_addr = f"{safe_name}@example.com"
        # Construct mbox entry
        # From <sender> <date>
        parts.append(f"From {sender_addr} {from_line_date}")

    parts.append(f"From: {header.msgfrom}")
    parts.append(f"To: {header.msgto}")
    parts.append(f"Subject: {header.msgsubject}")
    parts.append(f"Date: {rfc_date}")

    # Generate a unique Message-ID
    # <confnum.msgnum@qwk>
    msg_id = f"<{header.confnum}.{header.msgnum if header.msgnum is not None else 'x'}@qwk>"
    parts.append(f"Message-ID: {msg_id}")

    # Threading headers
    if message.parent_msgnum is not None:
        parent_id = f"<{header.confnum}.{message.parent_msgnum}@qwk>"
        parts.append(f"In-Reply-To: {parent_id}")
        parts.append(f"References: {parent_id}")

    # QWK Information headers
    parts.append(f"X-QWK-Conference: {header.confnum}")
    if message.confname:
        parts.append(f"X-QWK-Conference-Name: {message.confname}")
    if message.bbs_name:
        parts.append(f"X-QWK-BBS-Name: {message.bbs_name}")
    if message.source_file:
        parts.append(f"X-QWK-Source-File: {message.source_file}")
    if header.msgnum is not None:
        parts.append(f"X-QWK-Message-Number: {header.msgnum}")
    if header.status.strip():
        parts.append(f"X-QWK-Status: {header.status}")
    if header.msgflag.strip():
        parts.append(f"X-QWK-Flags: {header.msgflag}")
    if header.refnum is not None:
        parts.append(f"X-QWK-Reference: {header.refnum}")
    if message.attachments:
        parts.append(f"X-QWK-Attachments: {';'.join(message.attachments)}")
    if message.depth > 0:
        parts.append(f"X-QWK-Depth: {message.depth}")
    if message.thread_id:
        parts.append(f"X-QWK-Thread-ID: {message.thread_id}")
    if message.parent_msgnum is not None:
        parts.append(f"X-QWK-Parent-Msgnum: {message.parent_msgnum}")

    parts.append("Content-Type: text/plain; charset=utf-8")
    parts.append("Content-Transfer-Encoding: 8bit")

    parts.append("")  # Separator before body
    parts.append(body)
    parts.append("")  # Trailing newline required by mbox/eml

    return "\n".join(parts)


def _serialize_message_mbox(message: ProcessedMessage) -> str:
    """Serialize a message to mbox format with threading and extra headers."""
    return _serialize_rfc822(message, include_mbox_header=True)


def _serialize_message_eml(message: ProcessedMessage) -> str:
    """Serialize a message to EML format (RFC 822)."""
    return _serialize_rfc822(message, include_mbox_header=False)


def _write_mbox(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    """Write messages to an mbox file."""
    parts = []
    for message in messages:
        parts.append(_serialize_message_mbox(message))

    _write_text_output("\n".join(parts), output_path, encoding=encoding)


def _write_eml(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    """Write messages as EML.

    If multiple messages are provided and no individual files are requested,
    they are aggregated with double newlines, effectively becoming a text-based collection.
    """
    parts = []
    for message in messages:
        parts.append(_serialize_message_eml(message))

    _write_text_output("\n\n".join(parts), output_path, encoding=encoding)


def _write_text(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    """Write messages to text format with indentation for threads."""
    parts = []

    if settings and settings.oneline:
        msgnum_hdr = f"{'Num':<6} " if settings.verbose else ""
        conf_hdr = f"{'Conference':<12}"
        date_hdr = f"{'Date':<14}"
        from_hdr = f"{'From':<15}"
        to_hdr = f"{'To':<15}"
        subj_hdr = "Subject"

        use_colors = (
            not output_path
            and hasattr(sys.stdout, 'isatty')
            and sys.stdout.isatty()
        )

        if use_colors:
            BOLD = "1"
            def b(t): return f"\033[{BOLD}m{t}\033[0m"
            header_line = f"{b(msgnum_hdr)}{b(conf_hdr)} {b(date_hdr)} {b(from_hdr)} {b(to_hdr)} {b(subj_hdr)}\r\n"
        else:
            header_line = f"{msgnum_hdr}{conf_hdr} {date_hdr} {from_hdr} {to_hdr} {subj_hdr}\r\n"

        parts.append(header_line)
        # Calculate separator length from the plain text header
        plain_header = f"{msgnum_hdr}{conf_hdr} {date_hdr} {from_hdr} {to_hdr} {subj_hdr}"
        parts.append("-" * len(plain_header) + "\r\n")

    if settings and settings.include_toc:
        title = 'QWK Message Archive'
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
        parts.append("-" * 80 + "\r\n\r\n")

    for message in messages:
        text = message.text
        # Apply indentation only if NOT in oneline mode (oneline mode handles depth internally)
        if message.depth > 0 and not (settings and settings.oneline):
            indent = "  " * message.depth
            lines = text.splitlines(keepends=True)
            indented_lines = [indent + line for line in lines]
            text = "".join(indented_lines)
        parts.append(text)

    _write_text_output("".join(parts), output_path, encoding=encoding)


def _write_csv(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    output = io.StringIO()

    header_fields = [f.name for f in fields(MessageHeader)]
    fieldnames = header_fields + [
        'conference_name', 'bbs_name', 'source_file',
        'text', 'depth', 'thread_id', 'parent_msgnum',
        'attachments'
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar='\\')
    writer.writeheader()

    for message in messages:
        row = message.header.as_dict
        row['conference_name'] = message.confname
        row['bbs_name'] = message.bbs_name
        row['source_file'] = message.source_file
        row['text'] = message.text
        row['depth'] = message.depth
        row['thread_id'] = message.thread_id
        row['parent_msgnum'] = message.parent_msgnum
        row['attachments'] = ";".join(message.attachments or [])
        writer.writerow(row)

    _write_text_output(output.getvalue(), output_path, encoding=encoding)


def _write_sqlite(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
) -> None:
    if output_path is None:
        raise ValueError("Output path is required for SQLite export.")

    conn = sqlite3.connect(output_path)
    c = conn.cursor()

    c.execute('''
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
            source_file TEXT,
            attachments TEXT
        )
    ''')

    for msg in messages:
        header = msg.header
        dt = _parse_qwk_date(header.msgdate, header.msgtime)
        iso_date = dt.isoformat()

        c.execute('''
            INSERT INTO messages (
                conference_number, message_number, date, author, recipient,
                subject, status, text, reference_number, thread_id, depth,
                parent_message_number, conference_name, bbs_name, source_file,
                attachments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
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
            msg.source_file,
            ";".join(msg.attachments or [])
        ))

    conn.commit()
    conn.close()


def write_messages(
    messages: list[ProcessedMessage],
    output_path: str | None,
    settings: ProcessingSettings,
    bbs_info: BBSInfo | None = None,
) -> None:
    """Save a list of messages to a file or print them to the screen.

    This function selects the appropriate writer based on the settings and
    handles the encoding for the output.
    """
    writers: dict[
        str,
        Callable[
            [list[ProcessedMessage], str | None, str, ProcessingSettings, BBSInfo | None],
            None,
        ],
    ] = {
        'json': _write_json,
        'xml': _write_xml,
        'html': _write_html,
        'markdown': _write_markdown,
        'text': _write_text,
        'csv': _write_csv,
        'mbox': _write_mbox,
        'eml': _write_eml,
        'sqlite': _write_sqlite,
    }

    writer = writers.get(settings.format, _write_text)
    output_encoding = 'utf-8'
    if settings.format == 'text':
        output_encoding = settings.encoding

    writer(messages, output_path, output_encoding, settings, bbs_info)


def _write_index(
    collected_info: list[dict[str, Any]],
    output_dir: str | None,
    settings: ProcessingSettings,
    bbs_info: BBSInfo | None = None
) -> None:
    """Generate a browsable index (HTML or Markdown) for individual message files."""
    if not output_dir or not collected_info:
        return

    # Group by conference
    by_conf = defaultdict(list)
    for info in collected_info:
        by_conf[(info['conf_num'], info['conf_name'])].append(info)

    title = "Message Archive"
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Message Archive"

    if settings.format == 'html':
        _write_html_index(by_conf, title, output_dir)
    elif settings.format == 'markdown':
        _write_markdown_index(by_conf, title, output_dir)


def _write_html_index(
    by_conf: Mapping[tuple[int, str], list[dict[str, Any]]],
    title: str,
    output_dir: str
) -> None:
    html_parts = _get_html_header(title)
    html_parts.append(f"<h1>{html.escape(title)}</h1>")

    for (conf_num, conf_name), messages in sorted(by_conf.items()):
        html_parts.append(f"<h2>{html.escape(conf_name)} (Conference {conf_num})</h2>")
        html_parts.append("<table>")
        html_parts.append("<thead><tr><th>#</th><th>Date</th><th>From</th><th>To</th><th>Subject</th><th>Attach</th></tr></thead>")
        html_parts.append("<tbody>")
        for msg in messages:
            html_parts.append("<tr>")
            html_parts.append(f"<td>{msg['msgnum'] or ''}</td>")
            html_parts.append(f"<td>{html.escape(msg['date'])}</td>")
            html_parts.append(f"<td>{html.escape(msg['from'])}</td>")
            html_parts.append(f"<td>{html.escape(msg['to'])}</td>")
            html_parts.append(f'<td><a href="{html.escape(msg["path"])}">{html.escape(msg["subject"] or "(no subject)")}</a></td>')
            attach_count = len(msg['attachments']) if msg.get('attachments') else 0
            html_parts.append(f"<td>{attach_count if attach_count > 0 else ''}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")

    html_parts.extend(_get_html_footer())
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(html_parts))


def _write_markdown_index(
    by_conf: Mapping[tuple[int, str], list[dict[str, Any]]],
    title: str,
    output_dir: str
) -> None:
    md_parts = [f"# {title}\n"]

    for (conf_num, conf_name), messages in sorted(by_conf.items()):
        md_parts.append(f"## {conf_name} (Conference {conf_num})\n")
        md_parts.append("| # | Date | From | To | Subject | Attach |")
        md_parts.append("|---|---|---|---|---|---|")
        for msg in messages:
            def esc_md(text: Any) -> str:
                return str(text or "").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")

            subj = esc_md(msg['subject'] or "(no subject)")
            from_name = esc_md(msg['from'])
            to_name = esc_md(msg['to'])
            attach_count = len(msg['attachments']) if msg.get('attachments') else 0
            attach_str = str(attach_count) if attach_count > 0 else ""
            md_parts.append(f"| {msg['msgnum'] or ''} | {msg['date']} | {from_name} | {to_name} | [{subj}]({msg['path']}) | {attach_str} |")
        md_parts.append("")

    index_path = os.path.join(output_dir, "README.md")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_parts))


def _write_text_output(content: str, output_path: str | None, *, encoding: str = 'latin1') -> None:
    if output_path is None:
        if not content.endswith('\n'):
            content += '\n'
        sys.stdout.write(content)
    else:
        with open(output_path, 'w', encoding=encoding) as f:
            f.write(content)


def _colorize(text: str, *attributes: str) -> str:
    """Apply ANSI color codes if stdout is a TTY."""
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        return f"\033[{';'.join(attributes)}m{text}\033[0m"
    return text


def _highlight_text(
    text: str,
    term: str | None,
    is_regex: bool = False,
    use_colors: bool = False,
) -> str:
    """Apply inverted colors highlighting to matching terms in text for terminal output."""
    if not term or not use_colors:
        return text

    return _apply_highlighting(
        text, term, is_regex, start_tag="\x1b[7m", end_tag="\x1b[0m"
    )


def _apply_highlighting(
    text: str,
    term: str | None,
    is_regex: bool = False,
    start_tag: str = "",
    end_tag: str = "",
    escape_func: Callable[[str], str] | None = None,
) -> str:
    """Apply highlighting to matching terms in text, optionally escaping parts.

    Args:
        text: The input text.
        term: The search term or pattern.
        is_regex: Whether the term is a regular expression.
        start_tag: The string to prepend to matches.
        end_tag: The string to append to matches.
        escape_func: Optional function to escape both matching and non-matching parts.

    Returns:
        The text with highlighting applied.
    """
    if not term:
        return escape_func(text) if escape_func else text

    flags = re.IGNORECASE
    pattern_str = term if is_regex else re.escape(term)
    try:
        pattern = re.compile(pattern_str, flags)
    except re.error:
        return escape_func(text) if escape_func else text

    result = []
    last_end = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        # Non-matching part
        non_match = text[last_end:start]
        if non_match:
            result.append(escape_func(non_match) if escape_func else non_match)
        
        # Matching part
        match_text = match.group(0)
        processed_match = escape_func(match_text) if escape_func else match_text
        result.append(f"{start_tag}{processed_match}{end_tag}")
        last_end = end
    
    # Remaining non-matching part
    remaining = text[last_end:]
    if remaining:
        result.append(escape_func(remaining) if escape_func else remaining)

    return "".join(result)


def show_info(input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger) -> None:
    """Show a summary of the QWK packet contents."""
    # ANSI Attribute codes
    BOLD = "1"
    CYAN = "36"

    all_info = []

    for input_path in input_paths:
        info_entry = {
            "file": input_path,
            "bbs_info": None,
            "total_messages": 0,
            "conferences": []
        }
        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)

            bbs_info = getattr(board_dict, 'bbs_info', None)
            if bbs_info:
                info_entry["bbs_info"] = asdict(bbs_info)

            if isinstance(file_data, list):
                messages_to_process = file_data
            else:
                if len(file_data) < BLOCK_SIZE:
                    if settings.format != 'json':
                        print(f"File: {_colorize(input_path, CYAN)}")
                        print("  Invalid or empty file.")
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
                info_entry["conferences"].append({
                    "number": conf_num,
                    "name": conf_name,
                    "message_count": count
                })

            if settings.format != 'json':
                print(f"File: {_colorize(input_path, CYAN)}")
                if bbs_info:
                    if bbs_info.name:
                        print(f"  {_colorize('BBS Name:', BOLD)} {bbs_info.name}")
                    if bbs_info.sysop:
                        print(f"  {_colorize('SysOp:', BOLD)}    {bbs_info.sysop}")
                    if bbs_info.location:
                        print(f"  {_colorize('Location:', BOLD)} {bbs_info.location}")
                    if bbs_info.bbs_id:
                        print(f"  {_colorize('BBS ID:', BOLD)}   {bbs_info.bbs_id}")
                    if bbs_info.packet_at:
                        print(f"  {_colorize('Packet At:', BOLD)} {bbs_info.packet_at}")

                print(f"  {_colorize('Total Messages:', BOLD)} {total_messages}")
                print(f"  {_colorize('Conferences:', BOLD)}")

                for conf in info_entry["conferences"]:
                    count_str = _colorize(str(conf["message_count"]), BOLD)
                    print(f"    {conf['number']}: {conf['name']} ({count_str} messages)")
                print("")

            all_info.append(info_entry)

        except PROCESSING_EXCEPTIONS as e:
            logger.error(f"Error reading info for {input_path}: {e}")

    if settings.format == 'json':
        print(json.dumps(all_info, indent=4, ensure_ascii=False))


def show_stats(input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger) -> None:
    """Show detailed statistics about the messages in the QWK archives."""
    # ANSI Attribute codes
    BOLD = "1"
    CYAN = "36"

    all_stats = []

    for input_path in input_paths:
        stats_entry = {
            "file": input_path,
            "total_messages": 0,
            "matching_messages": 0,
            "dates": {"earliest": None, "latest": None},
            "authors": [],
            "recipients": [],
            "conferences": [],
            "subjects": [],
            "attachments_count": 0,
            "day_of_week": {},
            "hour_of_day": {},
            "private_count": 0,
        }

        try:
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, 'bbs_info', None)
            user_name = bbs_info.user_name if bbs_info else None
            allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)

            author_counter = Counter()
            recipient_counter = Counter()
            conf_counter = Counter()
            subject_counter = Counter()
            dow_counter = Counter()
            hour_counter = Counter()

            earliest_dt = None
            latest_dt = None
            private_count = 0
            attachments_count = 0
            matching_count = 0
            total_count = 0
            processed_count = 0

            desc = f"Analyzing {os.path.basename(input_path)}"
            # Use a progress bar for statistics gathering
            # We must read message bodies to accurately count attachments
            need_body = True

            if isinstance(file_data, list):
                messages_to_process = file_data
                total_progress = len(file_data)
                progress_unit = 'msg'
            else:
                messages_to_process = parse_messages(
                    file_data, None, settings.encoding, headers_only=not need_body
                )
                total_progress = len(file_data)
                progress_unit = 'B'

            with _create_progress_bar(total_progress, settings.quiet, desc=desc) as progress_bar:
                if progress_bar is not None:
                    if progress_unit == 'msg':
                        progress_bar.unit = 'msg'
                        progress_bar.unit_scale = False
                    else:
                        messages_to_process = parse_messages(
                            file_data, progress_bar, settings.encoding, headers_only=not need_body
                        )

                for message in messages_to_process:
                    if isinstance(file_data, list) and progress_bar is not None:
                        progress_bar.update(1)
                    total_count += 1

                    if not matches_filters(message, settings, allowed_conferences, user_name):
                        continue

                    matching_count += 1

                    if settings.skip is not None and matching_count <= settings.skip:
                        continue

                    if settings.limit is not None and processed_count >= settings.limit:
                        break
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
                    subject_counter[_normalize_subject(message.header.msgsubject)] += 1

                    dow_counter[dt.strftime('%A')] += 1
                    hour_counter[dt.hour] += 1

                    if message.header.is_private:
                        private_count += 1

                    # Check for attachments in the full message
                    if message.text:
                        found_binaries = extract_binaries(message.text)
                        attachments_count += len(found_binaries)

            stats_entry["total_messages"] = total_count
            stats_entry["matching_messages"] = processed_count
            stats_entry["private_count"] = private_count
            stats_entry["attachments_count"] = attachments_count

            if earliest_dt:
                stats_entry["dates"]["earliest"] = earliest_dt.isoformat()
                stats_entry["dates"]["latest"] = latest_dt.isoformat()

            # Top 10
            stats_entry["authors"] = [{"name": n, "count": c} for n, c in author_counter.most_common(10)]
            stats_entry["recipients"] = [{"name": n, "count": c} for n, c in recipient_counter.most_common(10)]
            stats_entry["conferences"] = [{"number": n, "name": board_dict.get(n, str(n)), "count": c} for n, c in conf_counter.most_common(10)]
            stats_entry["subjects"] = [{"subject": s, "count": c} for s, c in subject_counter.most_common(10)]
            stats_entry["day_of_week"] = dict(dow_counter)
            stats_entry["hour_of_day"] = {str(k): v for k, v in hour_counter.items()}

            if settings.format != 'json':
                print(f"Statistics for: {_colorize(input_path, CYAN)}")
                print(f"  {_colorize('Messages:', BOLD)} {processed_count} matching / {total_count} total")

                if attachments_count > 0:
                    print(f"  {_colorize('Attachments:', BOLD)} {attachments_count} files detected")

                if earliest_dt:
                    print(f"  {_colorize('Date Range:', BOLD)} {earliest_dt.strftime('%Y-%m-%d')} to {latest_dt.strftime('%Y-%m-%d')}")

                print(f"  {_colorize('Private:', BOLD)}    {private_count} messages")

                if author_counter:
                    print(f"\n  {_colorize('Top Authors:', BOLD)}")
                    for auth in stats_entry["authors"]:
                        print(f"    {auth['name']:25} : {auth['count']}")

                if recipient_counter:
                    print(f"\n  {_colorize('Top Recipients:', BOLD)}")
                    for rcpt in stats_entry["recipients"]:
                        print(f"    {rcpt['name']:25} : {rcpt['count']}")

                if conf_counter:
                    print(f"\n  {_colorize('Top Conferences:', BOLD)}")
                    for conf in stats_entry["conferences"]:
                        conf_name = conf['name'][:21]
                        print(f"    {conf['number']:3} {conf_name:21} : {conf['count']}")

                if dow_counter:
                    print(f"\n  {_colorize('Day of Week Distribution:', BOLD)}")
                    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    max_dow_count = max(dow_counter.values())
                    for day in days:
                        count = dow_counter.get(day, 0)
                        bar = "#" * int(count * 40 / max_dow_count) if max_dow_count > 0 else ""
                        print(f"    {day:10}: {count:4} {bar}")

                if hour_counter:
                    print(f"\n  {_colorize('Hourly Distribution:', BOLD)}")
                    max_hour_count = max(hour_counter.values())
                    for h in range(24):
                        count = hour_counter.get(h, 0)
                        bar = "#" * int(count * 40 / max_hour_count) if max_hour_count > 0 else ""
                        print(f"    {h:02}:00 : {count:4} {bar}")
                print("")

            all_stats.append(stats_entry)

        except PROCESSING_EXCEPTIONS as e:
            logger.error(f"Error calculating stats for {input_path}: {e}")

    if settings.format == 'json':
        print(json.dumps(all_stats, indent=4, ensure_ascii=False))


def process_multiple_files(
    input_paths: list[str],
    output_dir: str,
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> bool:
    os.makedirs(output_dir, exist_ok=True)
    had_errors = False
    for input_path in input_paths:
        try:
            output_filename = os.path.splitext(os.path.basename(input_path))[0]
            ext = FORMAT_EXTENSIONS.get(settings.format, '.txt')
            output_filename += ext
            output_path = os.path.join(output_dir, output_filename)
            per_file_settings = replace(
                settings,
                output_mode='file',
                output_path=output_path,
            )
            process_file(input_path, per_file_settings, logger)
        except PROCESSING_EXCEPTIONS as error:
            logger.error("Error processing file %s: %s", input_path, error)
            had_errors = True
    return had_errors


def _normalize_subject(subject: str) -> str:
    """Normalize subject line for threading by removing prefixes."""
    s = subject.strip()
    while True:
        new_s = RE_SUBJECT_PREFIX_PATTERN.sub('', s)
        if new_s == s:
            break
        s = new_s
    return s.strip().lower()


def _order_messages_by_thread(messages: list[ProcessedMessage]) -> list[ProcessedMessage]:
    """Order processed messages so that threads are grouped together.

    Messages are rearranged so that parent messages appear before children and
    warnings are emitted for circular references.

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
    children: dict[int, list[int]] = defaultdict(list)
    roots: list[int] = []

    # 1. Indexing
    for index, message in enumerate(messages):
        if message.msgnum is not None:
            index_by_key[(message.confnum, message.msgnum)] = index

        subj = _normalize_subject(message.header.msgsubject)
        normalized_subjects.append(subj)
        if subj:
            index_by_subject[(message.confnum, subj)].append(index)

    # 2. Identify Parents
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
            # Check for immediate cycle (parent is already a child of this message)
            if index in children and parent_index in children[index]:
                child_msg = messages[index]
                logger.warning(
                    "Circular reference detected (conf %s, msgnum %s) - skipping parent assignment.",
                    child_msg.confnum,
                    child_msg.msgnum,
                )
                roots.append(index)
            else:
                children[parent_index].append(index)
                parent_map[index] = parent_index
        else:
            roots.append(index)

    # 3. Traversal
    ordered_messages: list[ProcessedMessage] = []
    visited: set[int] = set()
    cycle_reported: set[int] = set()

    def visit_iterative(start_idx: int) -> None:
        if start_idx in visited:
            return

        # Determine thread_id for this tree
        start_msg = messages[start_idx]
        thread_root_id = str(start_msg.msgnum) if start_msg.msgnum is not None else f"idx_{start_idx}"

        # Stack: (idx, depth, thread_id, children_iterator)
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
                parent_msgnum=parent_msgnum
            )
            ordered_messages.append(new_msg)
            stack.append((idx, depth, thread_id, iter(children.get(idx, []))))

        enter_node(start_idx, 0, thread_root_id)

        while stack:
            parent_idx, depth, thread_id, children_iter = stack[-1]

            try:
                child_idx = next(children_iter)
            except StopIteration:
                stack.pop()
                path.remove(parent_idx)
                continue

            if child_idx in path:
                if child_idx not in cycle_reported:
                    child_msg = messages[child_idx]
                    logger.warning(
                        "Circular reference detected (conf %s, msgnum %s).",
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


def organize_by_bbs(input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger) -> None:
    """Organize QWK files into directories based on their BBS name."""
    for input_path in input_paths:
        if not os.path.isfile(input_path):
            continue

        if not input_path.lower().endswith('.qwk'):
            continue

        try:
            _, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, 'bbs_info', None)
            if bbs_info and bbs_info.name:
                bbs_name = bbs_info.name.strip()
                safe_bbs_name = "".join([c for c in bbs_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
                
                if not safe_bbs_name:
                    safe_bbs_name = "Unknown_BBS"
                
                if settings.dry_run:
                    logger.info("Dry run: Would move %s to %s/", input_path, safe_bbs_name)
                    continue

                if not os.path.exists(safe_bbs_name):
                    os.makedirs(safe_bbs_name)
                
                shutil.move(input_path, os.path.join(safe_bbs_name, os.path.basename(input_path)))
                logger.info("Moved %s to %s/", input_path, safe_bbs_name)
            else:
                logger.warning("Could not find BBS name in %s", input_path)
        except Exception as e:
            logger.error("Error processing %s: %s", input_path, e)
