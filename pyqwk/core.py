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

__version__ = "0.1.0"

BLOCK_SIZE = 128
MESSAGES_FILENAME = 'messages.dat'
REPLY_FILENAME = 'reply.dat'
CONTROL_FILENAME = 'control.dat'

def expand_paths(paths: list[str]) -> list[str]:
    """Recursively find supported QWK files in directories."""
    expanded_paths = []
    for path in paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    lower_file = file.lower()
                    if lower_file.endswith(('.qwk', '.zip', '.rep', '.json', '.jsonl', '.csv', '.db', '.sqlite', '.xml', '.mbox', '.eml', '.md', '.markdown', '.html', '.htm')) or lower_file == 'messages.dat':
                        expanded_paths.append(os.path.join(root, file))
        else:
            expanded_paths.append(path)
    return sorted(expanded_paths)

FORMAT_EXTENSIONS = {
    'text': '.txt',
    'json': '.json',
    'jsonl': '.jsonl',
    'xml': '.xml',
    'html': '.html',
    'markdown': '.md',
    'mbox': '.mbox',
    'csv': '.csv',
    'sqlite': '.db',
    'eml': '.eml',
    'qwk': '.qwk',
    'rep': '.rep',
    'rss': '.rss',
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
    if output_format is not None:
        return output_format

    if output_path and output_mode == 'file':
        ext = os.path.splitext(output_path)[1].lower()
        mapping = {
            '.json': 'json',
            '.jsonl': 'jsonl',
            '.xml': 'xml',
            '.html': 'html',
            '.csv': 'csv',
            '.mbox': 'mbox',
            '.eml': 'eml',
            '.md': 'markdown',
            '.markdown': 'markdown',
            '.sqlite': 'sqlite',
            '.db': 'sqlite',
            '.qwk': 'qwk',
            '.rep': 'rep',
            '.rss': 'rss',
        }
        if ext in mapping:
            return mapping[ext]

    return 'text'

RE_QUOTE_PATTERN = re.compile(r'^\s*[A-Za-z\-\=]{0,4}\s?(>|\xb3|\||\}|│)')
RE_UUE_PATTERN = re.compile(r'^begin\s+\d{3}\s+')
RE_UUE_DATA_PATTERN = re.compile(r'^M[\x21-\x60]{60}$')
RE_UUE_LOOSE_PATTERN = re.compile(r'[\x21-\x4c][\x21-\x60]{4,60}$')
RE_BASE64_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{60,}$')
RE_YENC_PATTERN = re.compile(r'^=y(begin|part|end)')
RE_BASE64_LOOSE_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{4,}$')
RE_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
RE_URL_PATTERN = re.compile(
    r'\b(?:https?|ftp|telnet|gopher)://[^\s<>"]+|www\.[^\s<>"]+',
    re.IGNORECASE
)
RE_PHONE_PATTERN = re.compile(
    r'(?<!\w)'
    r'(?!(?:19|20)\d{2}[-./]\d{2}[-./]\d{2}\b)'
    r'(?=(?:\D*\d){7,})'
    r'(?:'
    r'(?:\+\d{1,3}[-\.\s]?)?'
    r'(?:\(\d{1,4}\)|\d{1,4})'
    r'[-\.\s]?\d{3,4}(?:[-\.\s]?\d{3,4}){1,3}'
    r'|'
    r'\d{3}[-\.\s]?\d{4}'
    r')'
    r'\b'
)

RE_SUBJECT_PREFIX_PATTERN = re.compile(
    r'^\s*(?:re|fw|fwd)(?:\[\d+\])?[:\s-]+\s*', re.IGNORECASE
)

RE_ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

DEFAULT_STOP_WORDS = {
    'the', 'and', 'for', 'that', 'this', 'with', 'from', 'have', 'was', 'were',
    'but', 'not', 'are', 'you', 'your', 'his', 'her', 'they', 'them', 'their',
    'will', 'can', 'has', 'had', 'been', 'which', 'who', 'how', 'when', 'where',
    'all', 'any', 'some', 'there', 'what', 'about', 'just', 'more', 'very',
    'than', 'then', 'also', 'only', 'even', 'into', 'most', 'well', 'would',
    'could', 'should', 'these', 'those', 'much', 'many', 'once', 'here', 'back',
    'still', 'over', 'must', 'does', 'made', 'said', 'went', 'came', 'down',
    'give', 'take', 'find', 'look', 'work', 'part',
}

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

    This function uses a simple state machine to identify the start, data, and end
    of common binary attachment formats (yEnc, UUE, and Base64) embedded in
    plain text messages.

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
        if stripped_line in ('end', '`'):
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
                decoded = base64.b64decode("".join(current_data))
            except (binascii.Error, ValueError, TypeError):
                decoded = b""
        elif in_yenc:
            try:
                encoded_str = "".join(current_data)
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
                decoded = bytes(decoded_bytes)
            except Exception:
                decoded = b""

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
    filename_pattern: str | None = None
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
    include_toc: bool = False
    extract_attachments: bool = False
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
    threading information used for organizing conversations.
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



# Aliases for backward compatibility
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

    def to_bytes(self, encoding: str = 'cp437') -> bytes:
        """Serialize the message header into a 128-byte QWK record."""
        def encode_pad(text: str, length: int, align: str = 'left') -> bytes:
            if align == 'right':
                return text.rjust(length).encode(encoding)[:length]
            return text.ljust(length).encode(encoding)[:length]

        def get_char_bytes(text: str) -> bytes:
            b = text.encode(encoding)
            return b[:1] if b else b' '

        # QWK headers use right-aligned, space-padded strings for numeric fields
        msgnum_raw = str(self.msgnum if self.msgnum is not None else 0)
        refnum_raw = str(self.refnum if self.refnum is not None else 0)
        numblocks_raw = str(self.numblocks if self.numblocks is not None else 0)

        # Re-pack the data using the same format as from_bytes
        return struct.pack(
            '<c7s8s5s25s25s25s12s8s6scHHc',
            get_char_bytes(self.status),
            encode_pad(msgnum_raw, 7, 'right'),
            encode_pad(self.msgdate, 8),
            encode_pad(self.msgtime, 5),
            encode_pad(self.msgto, 25),
            encode_pad(self.msgfrom, 25),
            encode_pad(self.msgsubject, 25),
            encode_pad(self.msgpassword, 12),
            encode_pad(refnum_raw, 8, 'right'),
            encode_pad(numblocks_raw, 6, 'right'),
            get_char_bytes(self.msgflag),
            self.confnum,
            self.lognum,
            get_char_bytes(self.nettag),
        )

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

        def prepare_field(text: str, width: int) -> str:
            truncated = text[:width]
            display_len = len(truncated)
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


def _parse_sqlite_messages(db_path: str) -> tuple[list[ParsedMessage], ConferenceMap]:
    """Import messages and information from a pyqwk SQLite database."""
    # Ensure the file exists before connecting to avoid creating an empty database
    if db_path and db_path != ':memory:' and not os.path.exists(db_path):
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
                board_dict[row['number']] = row['name']
        except sqlite3.OperationalError:
            pass

        cursor.execute("SELECT * FROM messages")
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

            header = MessageHeader.from_dict(header_dict)

            attachments = row['attachments'].split(';') if row['attachments'] else None

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
                bbs_name=row['bbs_name'] or bbs_info.name,
                bbs_id=(row['bbs_id'] if 'bbs_id' in row.keys() else None) or bbs_info.bbs_id,
                source_file=row['source_file'],
                attachments=attachments,
            )
            messages.append(msg)
    finally:
        conn.close()

    # If board_dict is empty, we reconstruct it from messages for backward compatibility
    if not board_dict:
        # Preserve existing bbs_info if it was loaded from a table.
        # We only restore it if it's not a default empty BBSInfo object.
        loaded_bbs_info = board_dict.bbs_info
        board_dict = _reconstruct_archive_information(messages)
        if loaded_bbs_info and loaded_bbs_info != BBSInfo():
            # Merge: prefer data loaded from SQLite tables, but fill gaps from reconstruction
            for field in fields(BBSInfo):
                if not getattr(loaded_bbs_info, field.name):
                    setattr(loaded_bbs_info, field.name, getattr(board_dict.bbs_info, field.name))
            board_dict.bbs_info = loaded_bbs_info

    return messages, board_dict



def _parse_json_messages(data: list[dict[str, Any]] | dict[str, Any]) -> list[ParsedMessage]:
    """Convert a list of dictionaries or a single dictionary into ParsedMessage objects."""
    if isinstance(data, dict):
        data = [data]
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
            bbs_id=entry.get('bbs_id'),
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

    if root.tag == 'message':
        entries = [root]
    else:
        entries = root.findall('message')

    for entry in entries:
        header_el = entry.find('header')
        header_dict = {el.tag: el.text for el in header_el} if header_el is not None else {}

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
            bbs_id=get_text('bbs_id'),
            source_file=get_text('source_file'),
            attachments=attachments or None,
        )
        messages.append(msg)
    return messages


def _parse_csv_messages(data: Iterator[dict[str, Any]]) -> list[ParsedMessage]:
    """Convert CSV rows into ParsedMessage objects."""
    messages = []

    for row in data:
        header = MessageHeader.from_dict(row)

        attachments = row.get('attachments', "").split(';') if row.get('attachments') else None

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
            bbs_id=row.get('bbs_id'),
            source_file=row.get('source_file'),
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
    conf_num = _safe_to_int(get_hdr('X-QWK-Conference')) or 0
    msg_num = _safe_to_int(get_hdr('X-QWK-Message-Number'))
    ref_num = _safe_to_int(get_hdr('X-QWK-Reference'))
    status = get_hdr('X-QWK-Status') or " "
    msg_flag = get_hdr('X-QWK-Flags') or " "
    conf_name = get_hdr('X-QWK-Conference-Name')
    bbs_name = get_hdr('X-QWK-BBS-Name')
    bbs_id = get_hdr('X-QWK-BBS-ID')
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
    msg_date = "01-01-70"
    msg_time = "00:00"
    date_hdr = get_hdr('Date')
    if date_hdr:
        try:
            dt = email.utils.parsedate_to_datetime(date_hdr)
            msg_date = dt.strftime('%m-%d-%y')
            msg_time = dt.strftime('%H:%M')
        except (ValueError, TypeError):
            pass

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
        bbs_id=bbs_id or None,
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


def _parse_html_messages(path: str) -> list[ParsedMessage]:
    """Import messages from an HTML file."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    messages = []

    # Identify message blocks
    msg_blocks = list(re.finditer(r'<div class="message"(?: id="[^"]*")?>', content))

    # Pre-calculate depths for all message starts in a single pass
    div_tags = list(re.finditer(r"<(div|/div)([^>]*)>", content))
    msg_depths = {}
    current_depth = 0
    stack = []
    div_idx = 0

    for block in msg_blocks:
        start = block.start()
        # Advance div_idx and update depth until we reach the current message block
        while div_idx < len(div_tags) and div_tags[div_idx].start() < start:
            m_tag = div_tags[div_idx]
            tag_name = m_tag.group(1)
            attrs = m_tag.group(2)
            if tag_name == "div":
                if 'class="reply"' in attrs:
                    stack.append("reply")
                    current_depth += 1
                else:
                    stack.append("other")
            elif tag_name == "/div":
                if stack:
                    if stack.pop() == "reply":
                        current_depth -= 1
            div_idx += 1
        msg_depths[start] = max(0, current_depth)

    re_date = re.compile(r'<strong>Date:</strong>\s*(.*?)\s*</div>')
    re_from = re.compile(r'<strong>From:</strong>\s*(.*?)\s*</div>')
    re_to = re.compile(r'<strong>To:</strong>\s*(.*?)\s*</div>')
    re_subject = re.compile(r'<strong>Subject:</strong>\s*(.*?)\s*</div>')
    re_conf = re.compile(r'<strong>Conference:</strong>\s*(.*?)\s*\((\d+)\)\s*</div>')
    re_bbs = re.compile(r'<strong>BBS:</strong>\s*(.*?)\s*</div>')
    re_source = re.compile(r'<strong>Source:</strong>\s*(.*?)\s*</div>')
    re_number = re.compile(r'<strong>Number:</strong>\s*(\d+)\s*</div>')
    re_attachments = re.compile(r'<strong>Attachments:</strong>\s*(.*?)\s*</div>')
    re_body = re.compile(r'<pre class="body">(.*?)</pre>', re.DOTALL)

    def clean_html(text: str) -> str:
        # Remove tags like <mark>, </mark>, <span class="quote">, </span>, and <a> tags
        text = re.sub(r'<[^>]+>', '', text)
        return html.unescape(text).strip()

    for i, match in enumerate(msg_blocks):
        start = match.start()
        end = msg_blocks[i+1].start() if i+1 < len(msg_blocks) else len(content)
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
            attachments = [clean_html(a) for a in attach_match.group(1).split(',')]

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
            msgsubject=clean_html(subject_match.group(1)) if subject_match else "(no subject)",
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


def _parse_markdown_messages(path: str) -> list[ParsedMessage]:
    """Import messages from a Markdown file."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into sections by horizontal rules '---'
    raw_sections = re.split(r'\n---\n', content)
    sections = []
    current_chunk = ""
    for s in raw_sections:
        # A new message section contains '## ' or '> ## '
        if '## ' in s:
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
    re_subject = re.compile(r'^## (.*)', re.MULTILINE)
    re_date = re.compile(r'^- \*\*Date:\*\* (.*)', re.MULTILINE)
    re_from = re.compile(r'^- \*\*From:\*\* (.*)', re.MULTILINE)
    re_to = re.compile(r'^- \*\*To:\*\* (.*)', re.MULTILINE)
    re_conf = re.compile(r'^- \*\*Conference:\*\* (.*) \((\d+)\)', re.MULTILINE)
    re_bbs = re.compile(r'^- \*\*BBS:\*\* (.*)', re.MULTILINE)
    re_source = re.compile(r'^- \*\*Source:\*\* (.*)', re.MULTILINE)
    re_number = re.compile(r'^- \*\*Number:\*\* (.*)', re.MULTILINE)
    re_attachments = re.compile(r'^- \*\*Attachments:\*\* (.*)', re.MULTILINE)

    for section in sections:
        # Detect blockquote depth for threaded Markdown
        depth = 0
        working_section = section.lstrip('\n')
        while working_section.startswith('>'):
            depth += 1
            lines = working_section.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith('> '):
                    new_lines.append(line[2:])
                elif line.startswith('>'):
                    new_lines.append(line[1:])
                elif not line.strip():
                    new_lines.append("")
                else:
                    new_lines.append(line)
            working_section = "\n".join(new_lines).strip()

        # If it's the first section, it might start with the archive title (# )
        msg_start = working_section.find('## ')
        if msg_start == -1:
            continue

        working_section = working_section[msg_start:]

        # Extract message information
        subject_match = re_subject.search(working_section)
        if not subject_match:
            continue

        subject = subject_match.group(1).strip().replace('**', '')
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
            conf_name = conf_match.group(1).strip().replace('**', '')
            conf_num = int(conf_match.group(2))

        # BBS info
        bbs_name = bbs_match.group(1).strip().replace('**', '') if bbs_match else None
        source_file = source_match.group(1).strip().replace('**', '') if source_match else None
        msg_num = _safe_to_int(num_match.group(1).strip()) if num_match else None

        attachments = None
        if attach_match:
            attach_str = attach_match.group(1).strip()
            if '[' in attach_str:
                attachments = re.findall(r'\[(.*?)\]', attach_str)
            else:
                attachments = [a.strip() for a in attach_str.split(',') if a.strip()]

        # Message body: everything after the information lines
        # In our Markdown format, metadata ends at the first blank line.
        lines = working_section.splitlines()
        body_start_idx = 0
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if not line_strip:
                body_start_idx = i + 1
                break
            if line_strip.startswith('## ') or line_strip.startswith('- **'):
                body_start_idx = i + 1
            else:
                body_start_idx = i
                break

        body = "\n".join(lines[body_start_idx:]).strip()

        # Construct MessageHeader
        header = MessageHeader(
            status=" ",
            msgnum=msg_num,
            msgdate=msg_date,
            msgtime=msg_time,
            msgto=to_match.group(1).strip().replace('**', '') if to_match else "",
            msgfrom=from_match.group(1).strip().replace('**', '') if from_match else "",
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


def load_data(
    input_path: str, logger: logging.Logger, encoding: str = 'cp437'
) -> tuple[bytearray | list[ParsedMessage], ConferenceMap]:
    """Load message data and conference mappings from an archive file.

    This function handles both raw legacy formats (QWK, REP) and modern
    structured formats (JSON, SQLite, XML, CSV, mbox, EML).

    Args:
        input_path: Path to the archive file or a raw 'MESSAGES.DAT' file.
        logger: Logger for reporting warnings and informational messages.
        encoding: The character set used to decode legacy text (default is 'cp437').

    Returns:
        A tuple of (file_data, board_dict):
        - file_data: A 'bytearray' of raw records for QWK/REP files, or
          a list of 'ParsedMessage' objects for modern structured formats.
        - board_dict: A 'ConferenceMap' linking conference numbers to names,
          which may also include BBS information.

        Note: When loading a raw 'MESSAGES.DAT' file, it automatically searches
        for a corresponding 'CONTROL.DAT' in the same folder to load conference names.
    """
    board_dict: dict[int, str] = {}

    if input_path.lower().endswith(('.db', '.sqlite')) or input_path == ':memory:':
        try:
            messages, board_dict = _parse_sqlite_messages(input_path)
        except (ValueError, sqlite3.Error) as e:
            raise ValueError(f"Failed to load SQLite archive: {e}")

        return messages, board_dict

    if input_path.lower().endswith('.json'):
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            messages = _parse_json_messages(data)

            board_dict = _reconstruct_archive_information(messages)
            return messages, board_dict

    if input_path.lower().endswith('.jsonl'):
        messages = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    messages.extend(_parse_json_messages(data))

        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if input_path.lower().endswith(('.html', '.htm')):
        try:
            messages = _parse_html_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load HTML archive: {e}")

        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if input_path.lower().endswith('.mbox'):
        try:
            messages = _parse_mbox_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load mbox archive: {e}")

        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if input_path.lower().endswith(('.md', '.markdown')):
        try:
            messages = _parse_markdown_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load Markdown archive: {e}")

        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if input_path.lower().endswith('.eml'):
        try:
            messages = _parse_eml_messages(input_path)
        except Exception as e:
            raise ValueError(f"Failed to load EML file: {e}")

        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if input_path.lower().endswith('.xml'):
        try:
            tree = ET.parse(input_path)
            root = tree.getroot()
            messages = _parse_xml_messages(root)
        except Exception as e:
            raise ValueError(f"Failed to load XML archive: {e}")

        board_dict = _reconstruct_archive_information(messages)
        return messages, board_dict

    if input_path.lower().endswith('.csv'):
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            messages = _parse_csv_messages(reader)

            board_dict = _reconstruct_archive_information(messages)
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
                        error_msg = f"unzip failed with return code {result.returncode}: {result.stderr}"
                        if os.name == 'nt' and result.returncode == 127:
                            error_msg += "\nTip: On Windows, run 'winget install GnuWin32.UnZip' or install 'unzip.exe' via Git Bash."
                        raise RuntimeError(error_msg)
                    
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
                        
                except Exception as final_e:
                    error_msg = f"An error occurred while handling older ZIP archive: {str(final_e)}"
                    if os.name == 'nt' and "[WinError 2]" in str(final_e):
                        error_msg += "\nTip: This error usually means the 'unzip' tool is missing. On Windows, run 'winget install GnuWin32.UnZip' or install it via Git Bash."
                    raise RuntimeError(error_msg) from final_e
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
    """Check if a message matches all your filters.

    Args:
        message: The message to check.
        settings: Settings containing your filter choices.
        allowed_conferences: A set of allowed conference numbers.
        user_name: Your name to use for the "mine" filter.

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

    # 1. Private/Password Check
    if (not settings.private and message.header.is_private) or message.header.is_password:
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
    if settings.mine and user_name:
        is_from_me = user_name.lower() in message.header.msgfrom.lower()
        is_to_me = user_name.lower() in message.header.msgto.lower()
        if not (is_from_me or is_to_me):
            return False

    # 3. Message Number Filter
    if settings.msgnum_filters and message.msgnum is not None:
        if message.msgnum not in settings.msgnum_filters:
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
    if settings.search_term:
        if message.text and message.attachments is None:
            found_attachments = extract_binaries(message.text)
            message.attachments = [name for name, data in found_attachments]

        found = (
            check_str_match(settings.search_term, message.header.msgfrom)
            or check_str_match(settings.search_term, message.header.msgto)
            or check_str_match(settings.search_term, message.header.msgsubject)
            or check_str_match(settings.search_term, message.text)
            or (message.confname and check_str_match(settings.search_term, message.confname))
            or (message.bbs_name and check_str_match(settings.search_term, message.bbs_name))
            or (message.bbs_id and check_str_match(settings.search_term, message.bbs_id))
            or (message.source_file and check_str_match(settings.search_term, message.source_file))
            or (message.attachments and any(check_str_match(settings.search_term, a) for a in message.attachments))
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

    # 10. Length Filter
    msg_len = len(message.text) if message.text else 0
    if settings.min_length is not None and msg_len < settings.min_length:
        return False
    if settings.max_length is not None and msg_len > settings.max_length:
        return False

    return True


def _slugify(text: str, default: str) -> str:
    """Create a safe name for a file or folder by removing special characters."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()[:30]
    return slug if slug else default


def _generate_safe_filename(message: ParsedMessage, settings_or_format: ProcessingSettings | str, count: int) -> str:
    """Generate a human-readable filename for an individual message."""
    if isinstance(settings_or_format, ProcessingSettings):
        settings = settings_or_format
        output_format = settings.format
    else:
        settings = None
        output_format = settings_or_format

    ext = FORMAT_EXTENSIONS.get(output_format, '.txt')

    if settings and settings.filename_pattern:
        try:
            mapping = {
                'date': _slugify(message.header.msgdate, "date"),
                'time': _slugify(message.header.msgtime, "time"),
                'author': _slugify(message.header.msgfrom, "author"),
                'to': _slugify(message.header.msgto, "to"),
                'subject': _slugify(message.header.msgsubject, "subject"),
                'msgnum': message.msgnum if message.msgnum is not None else count,
                'confnum': message.confnum,
                'confname': _slugify(message.confname or f"conf_{message.confnum}", "conf"),
                'bbs_name': _slugify(message.bbs_name or "bbs", "bbs"),
                'bbs_id': _slugify(message.bbs_id or "id", "id"),
                'length': len(message.text) if message.text else 0,
            }
            # Use formatting while preserving the pattern's intent
            filename = settings.filename_pattern.format(**mapping)
            # Basic sanitization of the resulting filename (replace any remaining odd chars)
            filename = re.sub(r'[^\w\-.]', '_', filename)
            if not filename.endswith(ext):
                filename += ext
            return filename
        except (KeyError, ValueError, AttributeError):
            # Fallback to default if pattern is invalid
            pass

    msg_num = message.msgnum if message.msgnum is not None else count
    slug = _slugify(message.header.msgsubject, "message")

    return f"{message.confnum:03d}-{msg_num:05d}-{slug}{ext}"


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
        if not settings.dry_run:
            os.makedirs(output_dir, exist_ok=True)

    collected_messages: list[ParsedMessage] = []
    seen_ids: set[tuple[str, int, int | str]] = set()

    use_colors = (
        output_mode == 'stdout'
        and settings.format == 'text'
        and hasattr(sys.stdout, 'isatty')
        and sys.stdout.isatty()
    )

    separator_mode = settings.separator
    if separator_mode == 'auto':
        if settings.individual_files or settings.format in (
            'json', 'xml', 'html', 'csv', 'markdown', 'sqlite', 'mbox', 'eml', 'qwk', 'rep'
        ):
            separator_mode = 'none'
        else:
            separator_mode = 'dashes'
    separator_str = ""
    if separator_mode == 'dashes':
        separator_str = ("-" * 80) + "\r\n"
        if use_colors:
            # ANSI Dim (90)
            separator_str = f"\x1b[90m{separator_str}\x1b[0m"
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
    board_dict_to_use = None
    total_attachments = 0

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

            # Apply quote highlighting for terminal output
            cleaned_body = _highlight_quotes(cleaned_body, use_colors)

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
        if settings.format in ('json', 'xml', 'csv', 'sqlite', 'mbox', 'eml') and settings.headers_only:
            text_content = ""
        elif (
            settings.oneline
            and settings.format in ('json', 'xml', 'csv', 'sqlite', 'mbox', 'eml', 'html', 'markdown')
        ):
            text_content = cleaned_body
        else:
            text_content = processed_buffer

        temp_msg = replace(parsed_message, text=text_content)

        if settings.individual_files:
            assert output_dir is not None

            target_dir = output_dir
            relative_sub_path = ""
            if any([
                settings.organize,
                settings.organize_by_date,
                settings.organize_by_bbs,
                settings.organize_by_author,
                settings.organize_by_to
            ]):
                sub_parts = []
                if settings.organize_by_bbs:
                    bbs_name = parsed_message.bbs_name or "unknown_bbs"
                    sub_parts.append(_slugify(bbs_name, "bbs"))

                if settings.organize_by_author:
                    author = parsed_message.header.msgfrom or "unknown_author"
                    sub_parts.append(_slugify(author, "author"))

                if settings.organize_by_to:
                    recipient = parsed_message.header.msgto or "unknown_to"
                    sub_parts.append(_slugify(recipient, "to"))

                if settings.organize:
                    conf_name = parsed_message.confname or "unknown"
                    conf_slug = _slugify(conf_name, "conference")
                    sub_parts.append(f"{parsed_message.confnum:03d}-{conf_slug}")

                if settings.organize_by_date:
                    msg_dt = _parse_qwk_date(parsed_message.header.msgdate, parsed_message.header.msgtime)
                    sub_parts.append(msg_dt.strftime('%Y'))
                    sub_parts.append(msg_dt.strftime('%m'))

                relative_sub_path = os.path.join(*sub_parts)
                target_dir = os.path.join(output_dir, relative_sub_path)
                if not settings.dry_run:
                    os.makedirs(target_dir, exist_ok=True)

            attachment_prefix = None
            if settings.extract_attachments:
                if relative_sub_path:
                    # Each level of directory nesting requires an extra '../'
                    depth = len(relative_sub_path.replace(os.sep, '/').split('/'))
                    attachment_prefix = ("../" * depth) + "attachments/"
                else:
                    attachment_prefix = "attachments/"

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
                encoded_buffer = _serialize_rfc822(temp_msg, include_mbox_header=True).encode(target_encoding)
            elif settings.format == 'eml':
                encoded_buffer = _serialize_rfc822(temp_msg, include_mbox_header=False).encode(target_encoding)
            else:
                encoded_buffer = processed_buffer.encode(target_encoding)

            filename = _generate_safe_filename(parsed_message, settings, processed_count)
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
                rel_path = os.path.join(relative_sub_path, filename)
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
        if board_dict and not board_dict_to_use:
            board_dict_to_use = board_dict
        bbs_key = f"{bbs_info.name}|{bbs_info.bbs_id}" if bbs_info else ""

        allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)

        desc = f"Processing {os.path.basename(input_path)}"

        is_structured = isinstance(file_data, list)
        total_progress = len(file_data)

        with _create_progress_bar(total_progress, settings.quiet, desc=desc) as progress_bar:
            if is_structured:
                messages_to_process = file_data
                if progress_bar is not None:
                    progress_bar.unit = 'msg'
                    progress_bar.unit_scale = False
            else:
                messages_to_process = parse_messages(
                    file_data,
                    progress_bar,
                    settings.encoding,
                    settings.headers_only,
                )

            for parsed_message in messages_to_process:
                if is_structured and progress_bar is not None:
                    progress_bar.update(1)

                parsed_message = replace(
                    parsed_message,
                    confname=parsed_message.confname or board_dict.get(parsed_message.confnum),
                    bbs_name=parsed_message.bbs_name or (bbs_info.name if bbs_info else None),
                    bbs_id=parsed_message.bbs_id or (bbs_info.bbs_id if bbs_info else None),
                    source_file=parsed_message.source_file or os.path.basename(input_path),
                )
                if not matches_filters(parsed_message, settings, allowed_conferences, user_name):
                    continue

                if settings.unique:
                    msg_id: tuple[str, int, int | str]
                    # Use the message's own BBS information for the ID to ensure
                    # correct deduplication across mixed sources (e.g. JSONL)
                    current_bbs_key = f"{parsed_message.bbs_name}|{parsed_message.bbs_id}" if parsed_message.bbs_name or parsed_message.bbs_id else bbs_key
                    if parsed_message.msgnum is not None:
                        msg_id = (current_bbs_key, parsed_message.confnum, parsed_message.msgnum)
                    else:
                        content_hash = hashlib.sha1(
                            parsed_message.text.encode(settings.encoding, errors='replace')
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
        if settings.sort:
            sort_keys: dict[str, Callable[[tuple[ParsedMessage, dict[int, str]]], Any]] = {
                'date': lambda x: _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime),
                'author': lambda x: x[0].header.msgfrom.lower(),
                'to': lambda x: x[0].header.msgto.lower(),
                'subject': lambda x: x[0].header.msgsubject.lower(),
                'num': lambda x: (x[0].confnum, x[0].msgnum or 0),
                'conference': lambda x: (x[0].confnum, _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime)),
                'bbs': lambda x: (x[0].bbs_name or "", x[0].bbs_id or "", _parse_qwk_date(x[0].header.msgdate, x[0].header.msgtime)),
                'length': lambda x: len(x[0].text) if x[0].text else 0,
                'size': lambda x: len(x[0].text) if x[0].text else 0,
            }
            if settings.sort in sort_keys:
                sort_buffer.sort(key=sort_keys[settings.sort], reverse=settings.reverse)
                reversal_needed = False

        if reversal_needed:
            sort_buffer.reverse()

        for parsed_message, board_dict in sort_buffer:
            if handle_output(parsed_message, board_dict):
                break

    if settings.individual_files:
        if not settings.dry_run and collected_for_index:
            # Reconstruct dummy messages for stats if necessary, or just extract info from collected_for_index
            def gen_dummy_messages():
                for info in collected_for_index:
                    # Date is stored as "msgdate msgtime", split carefully to avoid IndexError
                    date_parts = info['date'].split(' ', 1)
                    msgdate = date_parts[0]
                    msgtime = date_parts[1] if len(date_parts) > 1 else ""

                    h = MessageHeader(
                        status=" ", msgnum=info['msgnum'], msgdate=msgdate,
                        msgtime=msgtime, msgto=info['to'], msgfrom=info['from'],
                        msgsubject=info['subject'], msgpassword="", refnum=None, numblocks=None,
                        msgflag=" ", confnum=info['conf_num'], lognum=0, nettag=""
                    )
                    yield ParsedMessage(
                        text="", msgnum=info['msgnum'], refnum=None, confnum=info['conf_num'],
                        header=h, confname=info['conf_name'], attachments=info['attachments']
                    )

            export_stats = _compute_stats_from_messages(gen_dummy_messages())
            _write_index(collected_for_index, resolved_output_path, settings, bbs_info_to_use, stats=export_stats)
    else:
        if not settings.dry_run:
            ordered_messages = (
                _order_messages_by_thread(collected_messages)
                if settings.threaded
                else collected_messages
            )
            write_messages(
                ordered_messages, resolved_output_path, settings, bbs_info_to_use, board_dict_to_use
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
            print("Files to create:    1 (merged)")

        size_str = f"{estimated_bytes / 1024:.1f} KB" if estimated_bytes < 1024 * 1024 else f"{estimated_bytes / (1024 * 1024):.1f} MB"
        print(f"Estimated size:     {size_str}")
        print(f"{_colorize('No changes were made to the disk.', BOLD)}")


def _message_to_dict(message: ProcessedMessage) -> dict[str, Any]:
    return {
        'header': message.header.as_dict,
        'conference': message.confname,
        'bbs_name': message.bbs_name,
        'bbs_id': message.bbs_id,
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
    board_dict: Mapping[int, str] | None = None,
) -> None:
    output_data = [_message_to_dict(msg) for msg in messages]
    output_json = json.dumps(output_data, indent=4, ensure_ascii=False)
    _write_text_output(output_json, output_path, encoding='utf-8')


def _write_jsonl(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    lines = []
    for msg in messages:
        lines.append(json.dumps(_message_to_dict(msg), ensure_ascii=False))
    output_jsonl = "\n".join(lines)
    _write_text_output(output_jsonl, output_path, encoding='utf-8')


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
    if message.bbs_id:
        ET.SubElement(msg_element, 'bbs_id').text = message.bbs_id
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
    board_dict: Mapping[int, str] | None = None,
) -> None:
    root = ET.Element('messages')
    for message in messages:
        msg_element = _message_to_xml_element(message)
        root.append(msg_element)

    xml_text = _xml_element_to_str(root)
    _write_text_output(xml_text, output_path, encoding='utf-8')


def _write_rss(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to an RSS 2.0 feed."""
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')

    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Feed"
        description = f"Message feed from {bbs_info.name}"
    else:
        title = 'QWK Message Feed'
        description = "Message feed from QWK archive"

    ET.SubElement(channel, 'title').text = title
    ET.SubElement(channel, 'link').text = 'https://github.com/mprokop/pyqwk'
    ET.SubElement(channel, 'description').text = description

    if messages:
        try:
            latest_msg = max(messages, key=lambda m: _parse_qwk_date(m.header.msgdate, m.header.msgtime))
            dt = _parse_qwk_date(latest_msg.header.msgdate, latest_msg.header.msgtime)
            ET.SubElement(channel, 'pubDate').text = email.utils.format_datetime(dt)
        except Exception:
            pass

    for message in messages:
        item = ET.SubElement(channel, 'item')
        header = message.header

        conf_name = message.confname or (board_dict.get(header.confnum) if board_dict else str(header.confnum))
        item_title = f"[{conf_name}] {header.msgsubject.strip()}"
        ET.SubElement(item, 'title').text = item_title

        # RSS items should ideally have a link, but these are offline messages.
        ET.SubElement(item, 'link').text = ""

        # Description contains the message text
        desc = ET.SubElement(item, 'description')
        desc.text = message.text

        # Author (RSS 2.0 expects an email address if possible, but we use the name)
        ET.SubElement(item, 'author').text = header.msgfrom.strip()

        # Publication Date
        dt = _parse_qwk_date(header.msgdate, header.msgtime)
        ET.SubElement(item, 'pubDate').text = email.utils.format_datetime(dt)

        # Unique identifier
        guid_val = f"{header.confnum}.{header.msgnum if header.msgnum is not None else id(message)}@qwk"
        guid = ET.SubElement(item, 'guid', isPermaLink='false')
        guid.text = guid_val

    xml_text = _xml_element_to_str(rss)
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
        '.quote { color: #4e9a06; }',
        '.stats-container { margin-bottom: 2em; padding: 1em; border: 1px solid #ddd; background-color: #fcfcfc; }',
        '.stats-grid { display: flex; flex-wrap: wrap; gap: 2em; }',
        '.stats-box { flex: 1; min-width: 300px; }',
        '.stats-bar-container { display: flex; align-items: center; margin-bottom: 0.5em; }',
        '.stats-bar-label { width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.9em; }',
        '.stats-bar-count { width: 40px; text-align: right; margin-right: 10px; font-weight: bold; font-size: 0.9em; }',
        '.stats-bar { height: 1.2em; background-color: #00aaaa; min-width: 1px; }',
        '.stats-summary-info { margin-bottom: 1em; font-size: 0.95em; color: #555; }',
        '</style>',
        '</head>',
        '<body>',
    ]


def _get_html_footer() -> list[str]:
    return [
        '</body>',
        '</html>',
    ]


def _render_stats_html(stats: dict[str, Any]) -> list[str]:
    """Render a statistics summary as an HTML fragment."""
    parts = []
    parts.append('<div class="stats-container">')
    parts.append('<h2>Archive Summary</h2>')

    parts.append('<div class="stats-summary-info">')
    parts.append(f'<div><strong>Messages:</strong> {stats["matching_messages"]} matching / {stats["total_messages"]} total</div>')
    if stats['dates']['earliest']:
        earliest = datetime.datetime.fromisoformat(stats['dates']['earliest']).strftime('%Y-%m-%d')
        latest = datetime.datetime.fromisoformat(stats['dates']['latest']).strftime('%Y-%m-%d')
        parts.append(f'<div><strong>Date Range:</strong> {earliest} to {latest}</div>')
    parts.append(f'<div><strong>Reply Rate:</strong> {stats["reply_rate"]}%</div>')
    parts.append('</div>')

    parts.append('<div class="stats-grid">')

    # Top Authors
    if stats['authors']:
        parts.append('<div class="stats-box">')
        parts.append('<h3>Top Authors</h3>')
        authors = stats['authors'][:5]
        max_count = authors[0]['count'] if authors else 1
        for author in authors:
            width = int(author['count'] * 100 / max_count)
            parts.append('<div class="stats-bar-container">')
            parts.append(f'<div class="stats-bar-label" title="{html.escape(author["name"])}">{html.escape(author["name"])}</div>')
            parts.append(f'<div class="stats-bar-count">{author["count"]}</div>')
            parts.append(f'<div class="stats-bar" style="width: {width}%"></div>')
            parts.append('</div>')
        parts.append('</div>')

    # Top Conferences
    if stats['conferences']:
        parts.append('<div class="stats-box">')
        parts.append('<h3>Top Conferences</h3>')
        confs = stats['conferences'][:5]
        max_count = confs[0]['count'] if confs else 1
        for conf in confs:
            width = int(conf['count'] * 100 / max_count)
            parts.append('<div class="stats-bar-container">')
            parts.append(f'<div class="stats-bar-label" title="{html.escape(conf["name"])}">{html.escape(conf["name"])}</div>')
            parts.append(f'<div class="stats-bar-count">{conf["count"]}</div>')
            parts.append(f'<div class="stats-bar" style="width: {width}%"></div>')
            parts.append('</div>')
        parts.append('</div>')

    # Top Attachments
    if stats.get('top_attachments'):
        parts.append('<div class="stats-box">')
        parts.append('<h3>Top Attachments</h3>')
        attaches = stats['top_attachments'][:5]
        max_count = attaches[0]['count'] if attaches else 1
        for attach in attaches:
            width = int(attach['count'] * 100 / max_count)
            parts.append('<div class="stats-bar-container">')
            parts.append(f'<div class="stats-bar-label" title="{html.escape(attach["name"])}">{html.escape(attach["name"])}</div>')
            parts.append(f'<div class="stats-bar-count">{attach["count"]}</div>')
            parts.append(f'<div class="stats-bar" style="width: {width}%"></div>')
            parts.append('</div>')
        parts.append('</div>')

    parts.append('</div>')  # stats-grid
    parts.append('</div>')  # stats-container
    return parts


def _render_single_message_html(
    message: ProcessedMessage,
    msg_id: str | None = None,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> list[str]:
    """Render a single message into HTML components with quote highlighting."""
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
    parts.append('<pre class="body">')

    body_text = message.text.replace('\r\n', '\n')
    body_lines = body_text.split('\n')
    processed_lines = []

    for line in body_lines:
        is_quote = bool(RE_QUOTE_PATTERN.match(line))
        highlighted_line = h_esc(line)
        if is_quote:
            processed_lines.append(f'<span class="quote">{highlighted_line}</span>')
        else:
            processed_lines.append(highlighted_line)

    parts.append('\n'.join(processed_lines))
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


def _render_stats_markdown(stats: dict[str, Any]) -> list[str]:
    """Render a statistics summary as a Markdown fragment."""
    parts = []
    parts.append("### Archive Summary\n")

    parts.append(f"- **Messages:** {stats['matching_messages']} matching / {stats['total_messages']} total")
    if stats['dates']['earliest']:
        earliest = datetime.datetime.fromisoformat(stats['dates']['earliest']).strftime('%Y-%m-%d')
        latest = datetime.datetime.fromisoformat(stats['dates']['latest']).strftime('%Y-%m-%d')
        parts.append(f"- **Date Range:** {earliest} to {latest}")
    parts.append(f"- **Reply Rate:** {stats['reply_rate']}%")
    parts.append("")

    def render_bar(count, max_count):
        bar_len = int(count * 20 / max_count) if max_count > 0 else 0
        return "#" * bar_len

    if stats['authors']:
        parts.append("#### Top Authors\n")
        parts.append("| Author | Messages | |")
        parts.append("|---|---|---|")
        authors = stats['authors'][:5]
        max_count = authors[0]['count'] if authors else 1
        for author in authors:
            bar = render_bar(author['count'], max_count)
            parts.append(f"| {author['name']} | {author['count']} | `{bar}` |")
        parts.append("")

    if stats['conferences']:
        parts.append("#### Top Conferences\n")
        parts.append("| Conference | Messages | |")
        parts.append("|---|---|---|")
        confs = stats['conferences'][:5]
        max_count = confs[0]['count'] if confs else 1
        for conf in confs:
            bar = render_bar(conf['count'], max_count)
            parts.append(f"| {conf['name']} | {conf['count']} | `{bar}` |")
        parts.append("")

    if stats.get('top_attachments'):
        parts.append("#### Top Attachments\n")
        parts.append("| Attachment | Count | |")
        parts.append("|---|---|---|")
        attaches = stats['top_attachments'][:5]
        max_count = attaches[0]['count'] if attaches else 1
        for attach in attaches:
            bar = render_bar(attach['count'], max_count)
            parts.append(f"| {attach['name']} | {attach['count']} | `{bar}` |")
        parts.append("")

    parts.append("---\n")
    return parts


def _render_single_message_markdown(
    message: ProcessedMessage,
    attachment_prefix: str | None = None,
    search_term: str | None = None,
    is_regex: bool = False,
) -> list[str]:
    """Render a single message into Markdown with blockquote standardization."""
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

    body_text = message.text.replace('\r\n', '\n')
    body_lines = body_text.split('\n')
    processed_lines = []

    for line in body_lines:
        is_quote = bool(RE_QUOTE_PATTERN.match(line))
        highlighted_line = md_high(line)
        if is_quote:
            # Standardize to use '> ' for blockquotes if it's not already starting with it
            if not highlighted_line.startswith('>'):
                processed_lines.append(f"> {highlighted_line}")
            else:
                processed_lines.append(highlighted_line)
        else:
            processed_lines.append(highlighted_line)

    parts.append('\n'.join(processed_lines))
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
    board_dict: Mapping[int, str] | None = None,
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

        # Add Statistics Summary
        stats = _compute_stats_from_messages(iter(messages))
        html_parts.extend(_render_stats_html(stats))

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
    board_dict: Mapping[int, str] | None = None,
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
    """Convert a QWK date and time into a standard Python datetime object.

    If the date is invalid, it returns a default date of 1970-01-01.
    """
    try:
        # Handle ISO 8601 format (used in SQLite exports)
        if 'T' in msgdate:
            return datetime.datetime.fromisoformat(msgdate)

        # Normalize date separators
        msgdate = msgdate.replace('/', '-')
        date_parts = msgdate.split('-')

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

        time_parts = list(map(int, msgtime.split(':')))
        hour = time_parts[0]
        minute = time_parts[1]
        second = time_parts[2] if len(time_parts) > 2 else 0

        return datetime.datetime(year, month, day, hour, minute, second)
    except (ValueError, IndexError):
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
    if message.bbs_id:
        parts.append(f"X-QWK-BBS-ID: {message.bbs_id}")
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


def _write_mbox(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to an mbox file."""
    parts = []
    for message in messages:
        parts.append(_serialize_rfc822(message, include_mbox_header=True))

    _write_text_output("\n".join(parts), output_path, encoding=encoding)


def _write_eml(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages as EML.

    If multiple messages are provided and no individual files are requested,
    they are aggregated with double newlines, effectively becoming a text-based collection.
    """
    parts = []
    for message in messages:
        parts.append(_serialize_rfc822(message, include_mbox_header=False))

    _write_text_output("\n\n".join(parts), output_path, encoding=encoding)


def _serialize_control_dat(
    bbs_info: BBSInfo | None,
    board_dict: Mapping[int, str] | None,
    encoding: str = 'cp437'
) -> list[bytes]:
    """Serialize BBS information and conference list into CONTROL.DAT format."""
    lines = [b""] * 11
    if bbs_info:
        lines[0] = bbs_info.name.encode(encoding)
        lines[1] = bbs_info.location.encode(encoding)
        lines[2] = bbs_info.phone.encode(encoding)
        lines[3] = bbs_info.sysop.encode(encoding)

        id_line = f"{bbs_info.serial_number},{bbs_info.bbs_id}"
        lines[4] = id_line.encode(encoding)

        lines[5] = bbs_info.packet_at.encode(encoding)
        lines[6] = bbs_info.user_name.encode(encoding)

    if board_dict:
        # Line 11 (index 10) is number of conferences - 1
        lines[10] = str(len(board_dict) - 1).encode(encoding)
        for conf_num, conf_name in sorted(board_dict.items()):
            lines.append(str(conf_num).encode(encoding))
            lines.append(conf_name.encode(encoding))
    else:
        lines[10] = b"-1"

    return lines


def _text_to_qwk_blocks(text: str, encoding: str = 'cp437') -> bytes:
    """Convert message text into 128-byte QWK blocks with \xe3 newlines."""
    # QWK uses \xe3 (227) as a newline character
    qwk_text = text.replace('\r\n', '\xe3').replace('\n', '\xe3')
    encoded = qwk_text.encode(encoding, errors='replace')

    # Pad to 128-byte boundary
    padding_len = (BLOCK_SIZE - (len(encoded) % BLOCK_SIZE)) % BLOCK_SIZE
    return encoded + (b' ' * padding_len)


def _write_text(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Write messages to text format with indentation for threads."""
    parts = []

    use_colors = (
        not output_path
        and hasattr(sys.stdout, 'isatty')
        and sys.stdout.isatty()
    )

    if settings and settings.oneline:
        msgnum_hdr = f"{'Num':<6} " if settings.verbose else ""
        conf_hdr = f"{'Conference':<12}"
        date_hdr = f"{'Date':<14}"
        from_hdr = f"{'From':<15}"
        to_hdr = f"{'To':<15}"
        subj_hdr = "Subject"

        if use_colors:
            BOLD = "1"
            def b(t): return f"\033[{BOLD}m{t}\033[0m"
            header_line = f"{b(msgnum_hdr)}{b(conf_hdr)} {b(date_hdr)} {b(from_hdr)} {b(to_hdr)} {b(subj_hdr)}\r\n"
        else:
            header_line = f"{msgnum_hdr}{conf_hdr} {date_hdr} {from_hdr} {to_hdr} {subj_hdr}\r\n"

        parts.append(header_line)
        # Calculate separator length from the plain text header
        plain_header = f"{msgnum_hdr}{conf_hdr} {date_hdr} {from_hdr} {to_hdr} {subj_hdr}"
        separator_line = "-" * len(plain_header) + "\r\n"
        if use_colors:
            # ANSI Dim (90)
            separator_line = f"\x1b[90m{separator_line}\x1b[0m"
        parts.append(separator_line)

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
        separator_line = "-" * 80 + "\r\n\r\n"
        if use_colors:
            # ANSI Dim (90)
            separator_line = f"\x1b[90m{separator_line}\x1b[0m"
        parts.append(separator_line)

    for message in messages:
        if settings and settings.oneline:
            # Re-format oneline summary to account for threading depth
            text = message.header.format_oneline(
                {},  # board_dict not needed when conf_name is provided
                use_colors=use_colors,
                highlight_term=settings.search_term,
                is_regex=settings.regex,
                verbose=settings.verbose,
                depth=message.depth,
                conf_name=message.confname,
            )
        else:
            text = message.text

            # Apply quote highlighting for terminal output
            text = _highlight_quotes(text, use_colors)

            # Apply indentation for threads
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
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    output = io.StringIO()

    header_fields = [f.name for f in fields(MessageHeader)]
    fieldnames = header_fields + [
        'conference_name', 'bbs_name', 'bbs_id', 'source_file',
        'text', 'depth', 'thread_id', 'parent_msgnum',
        'attachments'
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar='\\')
    writer.writeheader()

    for message in messages:
        row = message.header.as_dict
        row['conference_name'] = message.confname
        row['bbs_name'] = message.bbs_name
        row['bbs_id'] = message.bbs_id
        row['source_file'] = message.source_file
        row['text'] = message.text
        row['depth'] = message.depth
        row['thread_id'] = message.thread_id
        row['parent_msgnum'] = message.parent_msgnum
        row['attachments'] = ";".join(message.attachments or [])
        writer.writerow(row)

    _write_text_output(output.getvalue(), output_path, encoding=encoding)


def _write_qwk(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'cp437',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Export messages to a QWK/REP archive (ZIP file)."""
    if output_path is None:
        raise ValueError("Output path is required for QWK/REP export.")

    is_rep = output_path.lower().endswith('.rep')

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if is_rep:
            # REPLY.DAT
            content = bytearray()
            # First block is BBS ID
            bbs_id = (bbs_info.bbs_id if bbs_info else "") or "QWK"
            content.extend(bbs_id.ljust(BLOCK_SIZE).encode(encoding)[:BLOCK_SIZE])

            for msg in messages:
                body_blocks = _text_to_qwk_blocks(msg.text, encoding)
                num_blocks = (len(body_blocks) // BLOCK_SIZE) + 1
                header = replace(msg.header, numblocks=num_blocks)
                content.extend(header.to_bytes(encoding))
                content.extend(body_blocks)

            zf.writestr(REPLY_FILENAME, content)
        else:
            # MESSAGES.DAT
            content = bytearray()
            # First block is "Produced by pyqwk"
            header_block = "Produced by pyqwk".ljust(BLOCK_SIZE)
            content.extend(header_block.encode(encoding)[:BLOCK_SIZE])

            for msg in messages:
                body_blocks = _text_to_qwk_blocks(msg.text, encoding)
                num_blocks = (len(body_blocks) // BLOCK_SIZE) + 1
                header = replace(msg.header, numblocks=num_blocks)
                content.extend(header.to_bytes(encoding))
                content.extend(body_blocks)

            zf.writestr(MESSAGES_FILENAME, content)

            # CONTROL.DAT
            control_lines = _serialize_control_dat(bbs_info, board_dict, encoding)
            zf.writestr(CONTROL_FILENAME, b"\r\n".join(control_lines) + b"\r\n")


def _write_sqlite(
    messages: list[ProcessedMessage],
    output_path: str | None,
    encoding: str = 'utf-8',
    settings: ProcessingSettings | None = None,
    bbs_info: BBSInfo | None = None,
    board_dict: Mapping[int, str] | None = None,
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
            bbs_id TEXT,
            source_file TEXT,
            attachments TEXT
        )
    ''')

    c.execute('''
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
    ''')

    if bbs_info:
        c.execute('''
            INSERT INTO bbs_info (
                name, location, phone, sysop, serial_number, bbs_id,
                user_name, packet_at, total_messages, num_conferences
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
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
        ))

    c.execute('''
        CREATE TABLE IF NOT EXISTS conferences (
            number INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')

    if board_dict:
        for conf_num, conf_name in board_dict.items():
            c.execute('''
                INSERT OR REPLACE INTO conferences (number, name)
                VALUES (?, ?)
            ''', (conf_num, conf_name))

    for msg in messages:
        header = msg.header
        dt = _parse_qwk_date(header.msgdate, header.msgtime)
        iso_date = dt.isoformat()

        c.execute('''
            INSERT INTO messages (
                conference_number, message_number, date, author, recipient,
                subject, status, text, reference_number, thread_id, depth,
                parent_message_number, conference_name, bbs_name, bbs_id, source_file,
                attachments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            msg.bbs_id,
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
    board_dict: Mapping[int, str] | None = None,
) -> None:
    """Save a list of messages to a file or print them to the screen.

    This function selects the appropriate writer based on the settings and
    handles the encoding for the output.
    """
    writers: dict[
        str,
        Callable[
            [list[ProcessedMessage], str | None, str, ProcessingSettings, BBSInfo | None, Mapping[int, str] | None],
            None,
        ],
    ] = {
        'json': _write_json,
        'jsonl': _write_jsonl,
        'xml': _write_xml,
        'html': _write_html,
        'markdown': _write_markdown,
        'text': _write_text,
        'csv': _write_csv,
        'mbox': _write_mbox,
        'eml': _write_eml,
        'sqlite': _write_sqlite,
        'qwk': _write_qwk,
        'rep': _write_qwk,
        'rss': _write_rss,
    }

    writer = writers.get(settings.format, _write_text)
    output_encoding = 'utf-8'
    if settings.format == 'text':
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
        by_conf[(info['conf_num'], info['conf_name'])].append(info)

    title = "Message Archive"
    if bbs_info and bbs_info.name:
        title = f"{bbs_info.name} Message Archive"

    if settings.format == 'html':
        _write_html_index(by_conf, title, output_dir, stats=stats)
    elif settings.format == 'markdown':
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


def _highlight_quotes(text: str, use_colors: bool) -> str:
    """Apply green coloring to quoted lines in text for terminal output."""
    if not use_colors:
        return text

    lines = text.splitlines(keepends=True)
    highlighted_lines = []
    for line in lines:
        if RE_QUOTE_PATTERN.match(line):
            # Strip trailing newlines to place the reset code before them.
            content = line.rstrip('\r\n')
            ending = line[len(content):]
            # ANSI Green (32)
            highlighted_lines.append(f"\x1b[32m{content}\x1b[0m{ending}")
        else:
            highlighted_lines.append(line)
    return "".join(highlighted_lines)


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
        items: List of (label, count) tuples.
        use_colors: Whether to apply ANSI colors.
        bold: ANSI code for bold text.
        cyan: ANSI code for cyan color.
        dim: ANSI code for dim text.

    Returns:
        A list of formatted strings representing the bar chart.
    """
    if not items:
        return []

    def c(t, *a):
        if use_colors:
            return f"\033[{';'.join(a)}m{t}\033[0m"
        return str(t)

    parts = []
    parts.append(f"\n  {c(title, bold)}")

    max_count = max(count for _, count in items)
    for label, count in items:
        # Consistent 25-character label alignment with truncation
        label_str = str(label)
        truncated_label = f"{label_str[:25]:<25}"
        count_str = f"{count:4}"
        # Scale bars to a maximum of 40 characters
        bar_len = int(count * 40 / max_count) if max_count > 0 else 0
        bar = "#" * bar_len

        # Consistent coloring: Dim labels, Bold counts, Cyan bars
        parts.append(f"    {c(truncated_label, dim)} : {c(count_str, bold)} {c(bar, cyan)}")

    return parts


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

        dow_counter[dt.strftime('%A')] += 1
        hour_counter[dt.hour] += 1
        year_counter[dt.year] += 1
        month_counter[dt.strftime('%Y-%m')] += 1

        if message.header.is_private:
            private_count += 1

        # Detect if it's a reply
        is_reply = (
            (message.header.refnum is not None and message.header.refnum != 0)
            or RE_SUBJECT_PREFIX_PATTERN.match(message.header.msgsubject)
        )
        if is_reply:
            reply_count += 1

        # Check for attachments in the full message
        if message.text:
            total_chars += len(message.text)

            # Use cached attachments if available to avoid re-scanning
            current_attachments = message.attachments
            if current_attachments is None:
                found_binaries = extract_binaries(message.text)
                current_attachments = [name for name, data in found_binaries]
                # Lazily cache them back for other filters to use
                message.attachments = current_attachments

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
            words = re.findall(r'\b\w{3,}\b', message.text.lower())
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
    stats_entry["reply_rate"] = round(reply_count / processed_count * 100, 1) if processed_count > 0 else 0.0
    stats_entry["avg_message_length"] = round(total_chars / processed_count, 1) if processed_count > 0 else 0.0

    if earliest_dt:
        stats_entry["dates"]["earliest"] = earliest_dt.isoformat()
        stats_entry["dates"]["latest"] = latest_dt.isoformat()

    # Top 10
    stats_entry["authors"] = [{"name": n, "count": c} for n, c in author_counter.most_common(10)]
    stats_entry["recipients"] = [{"name": n, "count": c} for n, c in recipient_counter.most_common(10)]
    stats_entry["conferences"] = [{"number": n, "name": conf_names.get(n, str(n)), "count": c} for n, c in conf_counter.most_common(10)]
    stats_entry["bbses"] = [{"name": n, "count": c} for n, c in bbs_counter.most_common(10)]
    stats_entry["subjects"] = [{"subject": s, "count": c} for s, c in subject_counter.most_common(10)]
    stats_entry["keywords"] = [{"word": w, "count": c} for w, c in keyword_counter.most_common(10)]
    stats_entry["links"] = [{"url": u, "count": c} for u, c in link_counter.most_common(10)]
    stats_entry["emails"] = [{"email": e, "count": c} for e, c in email_counter.most_common(10)]
    stats_entry["phones"] = [{"phone": p, "count": c} for p, c in phone_counter.most_common(10)]
    stats_entry["top_attachments"] = [{"name": n, "count": c} for n, c in attachment_counter.most_common(10)]
    stats_entry["top_attachment_types"] = [{"extension": e, "count": c} for e, c in attachment_type_counter.most_common(10)]
    stats_entry["day_of_week"] = dict(dow_counter)
    stats_entry["hour_of_day"] = {str(k): v for k, v in hour_counter.items()}
    stats_entry["year_distribution"] = {str(k): v for k, v in sorted(year_counter.items())}
    stats_entry["month_distribution"] = dict(sorted(month_counter.items()))

    return stats_entry


def calculate_archive_stats(
    input_paths: list[str],
    settings: ProcessingSettings,
    logger: logging.Logger
) -> dict[str, Any]:
    """Calculate detailed statistics for one or more archives."""
    total_count = 0
    matching_count = 0
    processed_count = 0

    def filtered_messages_gen():
        nonlocal total_count, matching_count, processed_count
        for input_path in input_paths:
            if settings.limit is not None and processed_count >= settings.limit:
                break
            file_data, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, 'bbs_info', None)
            user_name = bbs_info.user_name if bbs_info else None
            allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)

            desc = f"Analyzing {os.path.basename(input_path)}"
            is_structured = isinstance(file_data, list)
            total_progress = len(file_data)

            with _create_progress_bar(total_progress, settings.quiet, desc=desc) as progress_bar:
                if is_structured:
                    messages_to_process = file_data
                    if progress_bar is not None:
                        progress_bar.unit = 'msg'
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
                        bbs_name=message.bbs_name or (bbs_info.name if bbs_info else None),
                        bbs_id=message.bbs_id or (bbs_info.bbs_id if bbs_info else None),
                        source_file=message.source_file or os.path.basename(input_path),
                    )

                    if not matches_filters(message, settings, allowed_conferences, user_name):
                        continue

                    matching_count += 1
                    if settings.skip is not None and matching_count <= settings.skip:
                        continue

                    if settings.limit is not None and processed_count >= settings.limit:
                        break
                    processed_count += 1
                    yield message

    file_label = input_paths[0] if len(input_paths) == 1 else "Multiple Archives"
    stats_entry = _compute_stats_from_messages(filtered_messages_gen(), file_label=file_label)

    # Override counts with actual values tracked during filtering
    stats_entry["total_messages"] = total_count
    stats_entry["matching_messages"] = processed_count

    return stats_entry


def render_stats_as_text(stats: dict[str, Any], use_colors: bool = False) -> str:
    """Render a statistics entry into a human-readable text report."""
    # ANSI Attribute codes
    BOLD = "1"
    CYAN = "36"

    def c(t, *a):
        if use_colors:
            return f"\033[{';'.join(a)}m{t}\033[0m"
        return t

    parts = []
    parts.append(f"Statistics for: {c(stats['file'], CYAN)}")
    parts.append(f"  {c('Messages:', BOLD)} {stats['matching_messages']} matching / {stats['total_messages']} total")

    if stats['attachments_count'] > 0:
        parts.append(f"  {c('Attachments:', BOLD)} {stats['attachments_count']} files detected")

    if stats['dates']['earliest']:
        earliest = datetime.datetime.fromisoformat(stats['dates']['earliest']).strftime('%Y-%m-%d')
        latest = datetime.datetime.fromisoformat(stats['dates']['latest']).strftime('%Y-%m-%d')
        parts.append(f"  {c('Date Range:', BOLD)} {earliest} to {latest}")

    parts.append(f"  {c('Private:', BOLD)}    {stats['private_count']} messages")

    parts.append(f"\n  {c('Activity & Content:', BOLD)}")
    parts.append(f"    Reply Rate:    {stats['reply_rate']}% ({stats['reply_count']} replies)")
    parts.append(f"    Avg Length:    {int(stats['avg_message_length'])} characters")

    if stats['year_distribution']:
        items = [(y, c) for y, c in sorted(stats['year_distribution'].items())]
        parts.extend(_render_stats_bar_chart('Yearly Activity:', items, use_colors=use_colors))

    if stats['month_distribution'] and len(stats['month_distribution']) <= 24:
        items = [(m, c) for m, c in sorted(stats['month_distribution'].items())]
        parts.extend(_render_stats_bar_chart('Monthly Activity:', items, use_colors=use_colors))

    parts.extend(_render_stats_bar_chart('Top Authors:', [(a["name"], a["count"]) for a in stats['authors']], use_colors=use_colors))
    parts.extend(_render_stats_bar_chart('Top Recipients:', [(r["name"], r["count"]) for r in stats['recipients']], use_colors=use_colors))

    if stats.get('bbses'):
        parts.extend(_render_stats_bar_chart('Top BBSes:', [(b["name"], b["count"]) for b in stats['bbses']], use_colors=use_colors))

    if stats['conferences']:
        items = [(f"{c['number']:3} {c['name']}", c["count"]) for c in stats['conferences']]
        parts.extend(_render_stats_bar_chart('Top Conferences:', items, use_colors=use_colors))

    parts.extend(_render_stats_bar_chart('Top Subjects:', [(s["subject"], s["count"]) for s in stats['subjects']], use_colors=use_colors))
    parts.extend(_render_stats_bar_chart('Top Keywords:', [(k["word"], k["count"]) for k in stats['keywords']], use_colors=use_colors))

    if stats.get('links'):
        parts.extend(_render_stats_bar_chart('Top Links:', [(link["url"], link["count"]) for link in stats['links']], use_colors=use_colors))

    if stats.get('emails'):
        parts.extend(_render_stats_bar_chart('Top Emails:', [(e["email"], e["count"]) for e in stats['emails']], use_colors=use_colors))

    if stats.get('phones'):
        parts.extend(_render_stats_bar_chart('Top Phone Numbers:', [(p["phone"], p["count"]) for p in stats['phones']], use_colors=use_colors))

    if stats.get('top_attachments'):
        parts.extend(_render_stats_bar_chart('Top Attachments:', [(a["name"], a["count"]) for a in stats['top_attachments']], use_colors=use_colors))

    if stats.get('top_attachment_types'):
        parts.extend(_render_stats_bar_chart('Top Attachment Types:', [(t["extension"], t["count"]) for t in stats['top_attachment_types']], use_colors=use_colors))

    if stats['day_of_week']:
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        items = [(d, stats['day_of_week'].get(d, 0)) for d in days]
        parts.extend(_render_stats_bar_chart('Day of Week Distribution:', items, use_colors=use_colors))

    if stats['hour_of_day']:
        items = [(f"{h:02}:00", stats['hour_of_day'].get(str(h), 0)) for h in range(24)]
        parts.extend(_render_stats_bar_chart('Hourly Distribution:', items, use_colors=use_colors))

    return "\n".join(parts) + "\n"


def show_stats(input_paths: list[str], settings: ProcessingSettings, logger: logging.Logger) -> None:
    """Show detailed statistics about the messages in the QWK archives."""
    all_stats = []

    use_colors = (
        settings.format == 'text'
        and hasattr(sys.stdout, 'isatty')
        and sys.stdout.isatty()
    )

    if settings.merge_stats:
        try:
            stats_entry = calculate_archive_stats(input_paths, settings, logger)
            if settings.format != 'json':
                print(render_stats_as_text(stats_entry, use_colors=use_colors))
            all_stats.append(stats_entry)
        except PROCESSING_EXCEPTIONS as e:
            logger.error(f"Error calculating merged stats: {e}")
    else:
        for input_path in input_paths:
            try:
                stats_entry = calculate_archive_stats([input_path], settings, logger)
                if settings.format != 'json':
                    print(render_stats_as_text(stats_entry, use_colors=use_colors))
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
    if not settings.dry_run:
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
            process_merged_files([input_path], per_file_settings, logger)
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

    # Build lookup tables to efficiently match replies by message number and subject
    for index, message in enumerate(messages):
        if message.msgnum is not None:
            index_by_key[(message.confnum, message.msgnum)] = index

        subj = _normalize_subject(message.header.msgsubject)
        normalized_subjects.append(subj)
        if subj:
            index_by_subject[(message.confnum, subj)].append(index)

    # Establish parent-child relationships using explicit references or subject-based heuristics
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

    # Perform an iterative depth-first traversal to group threads while safely handling potential cycles and recursion depth
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
    """Organize archive files into directories based on their BBS name and ID."""
    supported_extensions = ('.qwk', '.rep', '.json', '.csv', '.xml', '.db', '.sqlite', '.mbox', '.eml')

    for input_path in input_paths:
        if not os.path.isfile(input_path):
            continue

        if not input_path.lower().endswith(supported_extensions) and os.path.basename(input_path).lower() != 'messages.dat':
            continue

        try:
            _, board_dict = load_data(input_path, logger, settings.encoding)
            bbs_info = getattr(board_dict, 'bbs_info', None)

            if bbs_info and (bbs_info.name or bbs_info.bbs_id):
                name_part = bbs_info.name.strip() if bbs_info.name else "Unknown BBS"
                id_part = f" ({bbs_info.bbs_id.strip()})" if bbs_info.bbs_id else ""

                folder_name = f"{name_part}{id_part}"
                safe_folder_name = "".join([c for c in folder_name if c.isalnum() or c in (' ', '.', '_', '-', '(', ')')]).strip()
                
                if not safe_folder_name:
                    safe_folder_name = "Unknown_BBS"
                
                if settings.dry_run:
                    logger.info("Dry run: Would move %s to %s/", input_path, safe_folder_name)
                    continue

                if not os.path.exists(safe_folder_name):
                    os.makedirs(safe_folder_name)
                
                shutil.move(input_path, os.path.join(safe_folder_name, os.path.basename(input_path)))
                logger.info("Moved %s to %s/", input_path, safe_folder_name)
            else:
                logger.warning("Could not find BBS information in %s", input_path)
        except Exception as e:
            logger.error("Error organizing %s: %s", input_path, e)
