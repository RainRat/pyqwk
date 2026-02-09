import sys
import zipfile
import struct
import re
import hashlib
import os
import logging
import json
import html
import csv
import io
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, fields, replace
from contextlib import contextmanager, nullcontext
from typing import Any, Callable, Protocol
import datetime
import email.utils
import sqlite3

__version__ = "0.1.0"

BLOCK_SIZE = 128
MESSAGES_FILENAME = 'messages.dat'
CONTROL_FILENAME = 'control.dat'

RE_QUOTE_PATTERN = re.compile(r'^\s*[A-Za-z\-\=]{0,4}\s?(>|\xb3|\||\}|│)')
RE_UUE_PATTERN = re.compile(r'^begin\s\d{3}\s')
RE_UUE_DATA_PATTERN = re.compile(r'^M[\x21-\x60]{60}$')
RE_UUE_LOOSE_PATTERN = re.compile(r'[\x21-\x4c][\x21-\x60]{4,60}$')
RE_BASE64_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{60,}$')
RE_YENC_PATTERN = re.compile(r'^=y(begin|part|end)')
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
) -> tuple[bool, bool, bool]:
    """Detect whether a line is part of a binary payload.

    Returns a tuple ``(should_skip, in_yenc_block, in_uue_block)`` indicating whether the
    caller should exclude the line from output and the updated binary block states.
    """
    is_yenc_marker = RE_YENC_PATTERN.match(line)

    if is_yenc_marker:
        return True, not line.startswith('=yend'), in_uue_block

    if in_yenc_block:
        return True, True, in_uue_block

    if in_uue_block:
        if line.strip() == 'end':
            return True, in_yenc_block, False
        return True, in_yenc_block, True

    if RE_BASE64_PATTERN.match(line):
        return True, in_yenc_block, in_uue_block
    elif RE_UUE_DATA_PATTERN.match(line) or RE_UUE_PATTERN.match(line):
        return True, in_yenc_block, True
    elif RE_UUE_LOOSE_PATTERN.match(line):
        if previous_line and (
            RE_UUE_DATA_PATTERN.match(previous_line)
            or RE_UUE_PATTERN.match(previous_line)
        ):
            return True, in_yenc_block, True

    return False, in_yenc_block, False


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
    strip_ansi: bool = False
    quiet: bool = False
    headers_only: bool = False
    merge: bool = False
    conferences: list[str] | None = None
    authors: list[str] | None = None
    recipients: list[str] | None = None
    subjects: list[str] | None = None
    search_term: str | None = None
    after: datetime.datetime | None = None
    before: datetime.datetime | None = None
    limit: int | None = None


@dataclass
class BBSInfo:
    """Metadata about the BBS that generated the QWK packet."""
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

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConferenceMap(dict):
    """A dictionary mapping conference numbers to names, with optional BBS metadata."""
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
        return self.status not in (' ', '-')

    @property
    def is_password(self) -> bool:
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
            s = b.decode(encoding).split('\x00')[0]
            return s.strip() if strip_whitespace else s

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

    def format_text(
        self,
        board_dict: Mapping[int, str],
        verbose: bool,
        include_separator: bool = True,
    ) -> str:
        """Render a message header into readable text.

        Args:
            board_dict: Mapping of conference numbers to human-readable names.
            verbose: Whether to include extra metadata such as message numbers and reference numbers.
            include_separator: Whether to prepend the message separator line.

        Returns:
            The formatted header text with DOS-style newlines appended.
        """
        not_found_flag = False
        try:
            conf_name = board_dict[self.confnum]
        except KeyError:
            conf_name = str(self.confnum)
            not_found_flag = True

        header_parts: list[str] = []
        if include_separator:
            header_parts.append(("-" * 80) + "\r\n")
        if verbose or not not_found_flag:
            header_parts.append("Conference: " + str(conf_name) + "\r\n")
        if verbose:
            message_number = str(self.msgnum) if self.msgnum is not None else ""
            header_parts.append("Message number: " + message_number + (" " * 20))
        header_parts.append(
            "Date: " + self.msgdate + " " + self.msgtime + "\r\n"
        )
        header_parts.append("From: " + self.msgfrom + "\r\n")
        header_parts.append("To: " + self.msgto + "\r\n")
        header_parts.append("Subject: " + self.msgsubject + "\r\n")
        if verbose:
            reference_number = str(self.refnum) if self.refnum is not None else ""
            header_parts.append("Reference number: " + reference_number + "\r\n")
        header_parts.append("\r\n")
        return "".join(header_parts)


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


def load_data(
    input_path: str, logger: logging.Logger, encoding: str = 'cp437'
) -> tuple[bytearray, dict[int, str]]:
    """Load message and conference metadata from a QWK packet or raw file.

    Args:
        input_path: Path to either a ``messages.dat`` file or a QWK archive containing
            that file (and optionally ``CONTROL.DAT``).
        logger: Logger used to report warnings when optional metadata is missing.
        encoding: Character encoding to use when decoding metadata.

    Returns:
        A tuple ``(file_data, board_dict)`` where ``file_data`` is a mutable
        ``bytearray`` containing the full contents of ``messages.dat`` and
        ``board_dict`` maps conference numbers to their names parsed from
        ``CONTROL.DAT``. If ``CONTROL.DAT`` is not present, the mapping will be empty
        and conference identifiers will remain numeric.
    """
    board_dict: dict[int, str] = {}
    if zipfile.is_zipfile(input_path):
        messages_name = ''
        control_name = ''
        with zipfile.ZipFile(input_path) as myzip:
            file_list = myzip.namelist()
            for file_name in file_list:
                if file_name.lower() == MESSAGES_FILENAME:
                    messages_name = file_name
                if file_name.lower() == CONTROL_FILENAME:
                    control_name = file_name
            if not messages_name:
                raise FileNotFoundError(
                    f"Error: '{MESSAGES_FILENAME}' not found in the zip archive {input_path}."
                )
            with myzip.open(messages_name) as f:
                file_data = bytearray(f.read())
            if control_name:
                with myzip.open(control_name) as f:
                    control_data = f.read().splitlines()
                board_dict = _parse_control_dat(control_data, logger, encoding)
            else:
                logger.warning("CONTROL.DAT not found, conference names will not be available.")
    else:
        with open(input_path, 'rb') as f:
            file_data = bytearray(f.read())
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
        conf_name = conf_name_raw.decode(encoding)
        board_dict[conf_number] = conf_name

    return board_dict


def parse_messages(
    file_data: bytearray,
    progress_bar: ProgressBar | None,
    encoding: str = 'cp437',
    headers_only: bool = False,
) -> Iterator[ParsedMessage]:
    """Parse a QWK messages.dat payload into message objects.

    Args:
        file_data: Raw bytes from a messages.dat file.
        progress_bar: Optional tqdm-compatible progress reporter to update as blocks are read.
        encoding: Character encoding to use when decoding messages.
        headers_only: If True, skips reading the message body content.

    Yields:
        ParsedMessage instances containing the message body, header, and metadata flags.

    Raises:
        MessagesDatFormatError: If the payload does not start with a valid messages.dat header.
        InvalidMessageTypeError: If a message header encodes an unknown message type.
    """
    blocks_remaining = 0
    message_buffer = ''
    current_msgnum: int | None = None
    current_refnum: int | None = None
    current_confnum = 0
    header: MessageHeader | None = None

    if len(file_data) < BLOCK_SIZE:
        raise MessagesDatFormatError(
            "Input too short to contain a valid messages.dat header block."
        )

    first_record = file_data[0:BLOCK_SIZE]
    if progress_bar is not None:
        progress_bar.update(len(first_record))
    if first_record[0:9] != b'Produced ':
        raise MessagesDatFormatError(
            "Input does not start with 'Produced ' header; not a messages.dat file."
        )

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

            current_msgnum = header.msgnum
            current_refnum = header.refnum
            current_confnum = header.confnum

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
                    msgnum=current_msgnum,
                    refnum=current_refnum,
                    confnum=current_confnum,
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
                    msgnum=current_msgnum,
                    refnum=current_refnum,
                    confnum=current_confnum,
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
    """Transform a raw message body according to processing settings.

    Args:
        message_buffer: The original message text with DOS-style newlines.
        truncate_signatures: Whether to stop output at common signature separators.
        cut_quoting: Whether to remove quoted text and quote headers.
        binaries_removal: Whether to strip uuencoded, Base64, and yEnc payloads.
        redact_pii: Whether to redact email addresses and phone numbers.
        strip_ansi: Whether to remove ANSI escape sequences from the text.

    Returns:
        The processed message text with transformations applied.
    """
    message_buffer = message_buffer.lstrip('\r\n').rstrip()
    lines = message_buffer.splitlines()

    new_lines = []
    in_yenc_block = False
    in_uue_block = False
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
            elif j > 0 and j < (len(lines) - 1) \
                and RE_QUOTE_PATTERN.match(lines[j - 1]) \
                and RE_QUOTE_PATTERN.match(lines[j + 1]):
                continue
        if binaries_removal:
            should_skip, in_yenc_block, in_uue_block = _is_binary_line(
                line, previous_line, in_yenc_block, in_uue_block
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
) -> bool:
    """Check if a message satisfies all configured processing filters.

    Args:
        message: The message to evaluate.
        settings: Processing settings containing filter criteria.
        allowed_conferences: Pre-computed set of allowed conference numbers.

    Returns:
        True if the message matches all filters, False otherwise.
    """
    # 1. Private/Password Check
    if (not settings.private and message.header.is_private) or message.header.is_password:
        return False

    # 2. Conference Filter
    if settings.conferences and message.confnum not in allowed_conferences:
        return False

    # 3. Author Filter
    if settings.authors:
        msg_from_lower = message.header.msgfrom.lower()
        if not any(a.lower() in msg_from_lower for a in settings.authors):
            return False

    # 4. Recipient Filter
    if settings.recipients:
        msg_to_lower = message.header.msgto.lower()
        if not any(r.lower() in msg_to_lower for r in settings.recipients):
            return False

    # 5. Subject Filter
    if settings.subjects:
        msg_subject_lower = message.header.msgsubject.lower()
        if not any(s.lower() in msg_subject_lower for s in settings.subjects):
            return False

    # 6. Full-Text Search
    if settings.search_term:
        search_lower = settings.search_term.lower()
        found = (
            search_lower in message.header.msgfrom.lower()
            or search_lower in message.header.msgto.lower()
            or search_lower in message.header.msgsubject.lower()
            or search_lower in message.text.lower()
        )
        if not found:
            return False

    # 6. Date Filter
    if settings.after or settings.before:
        msg_dt = _parse_qwk_date(message.header.msgdate, message.header.msgtime)
        if settings.after and msg_dt < settings.after:
            return False
        if settings.before and msg_dt > settings.before:
            return False

    return True


def process_merged_files(
    input_paths: list[str],
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:
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

    separator_mode = settings.separator
    if separator_mode == 'auto':
        if settings.individual_files or settings.format in ('json', 'xml', 'html', 'csv', 'markdown'):
            separator_mode = 'none'
        else:
            separator_mode = 'dashes'
    separator_str = ""
    if separator_mode == 'dashes':
        separator_str = ("-" * 80) + "\r\n"
    elif separator_mode == 'blank':
        separator_str = "\r\n"

    count = 0
    for input_path in input_paths:
        file_data, board_dict = load_data(input_path, logger, settings.encoding)
        allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)

        desc = f"Processing {os.path.basename(input_path)}"
        with _create_progress_bar(len(file_data), settings.quiet, desc=desc) as progress_bar:
            for parsed_message in parse_messages(
                file_data,
                progress_bar,
                settings.encoding,
                settings.headers_only,
            ):
                if not matches_filters(parsed_message, settings, allowed_conferences):
                    continue

                count += 1
                if settings.limit is not None and count > settings.limit:
                    break

                processed_buffer = process_message(
                    parsed_message.text,
                    settings.truncate_signatures,
                    settings.cut_quoting,
                    settings.binaries_removal,
                    settings.redact_pii,
                    settings.strip_ansi,
                )
                if not settings.no_header and settings.format not in ('html', 'markdown'):
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
                    )
                    processed_buffer = header_text + processed_buffer

                # Add separator for text format, or if headers are enabled (legacy behavior for non-text formats)
                if settings.format == 'text' or (not settings.no_header and settings.format not in ('html', 'markdown')):
                    processed_buffer = separator_str + processed_buffer

                if settings.individual_files:
                    target_encoding = 'utf-8'
                    if settings.format == 'text':
                        target_encoding = settings.encoding
                        encoded_buffer = processed_buffer.encode(target_encoding)
                    elif settings.format == 'json':
                        # For JSON, we use the message object but update the text with processed_buffer
                        # Note: processed_buffer may contain the header if not --noheader, matching existing behavior
                        # If headers_only, we want empty text in the JSON, not processed_buffer (which might be the formatted header)
                        text_content = "" if settings.headers_only else processed_buffer
                        temp_msg = replace(parsed_message, text=text_content)
                        encoded_buffer = json.dumps(
                            _message_to_dict(temp_msg), indent=4, ensure_ascii=False
                        ).encode(target_encoding)
                    elif settings.format == 'xml':
                        temp_msg = replace(parsed_message, text=processed_buffer)
                        encoded_buffer = _serialize_message_xml(temp_msg).encode(target_encoding)
                    elif settings.format == 'html':
                        temp_msg = replace(parsed_message, text=processed_buffer)
                        encoded_buffer = _serialize_message_html(temp_msg).encode(target_encoding)
                    elif settings.format == 'markdown':
                        temp_msg = replace(parsed_message, text=processed_buffer)
                        encoded_buffer = _serialize_message_markdown(temp_msg).encode(target_encoding)
                    elif settings.format == 'mbox':
                        temp_msg = replace(parsed_message, text=processed_buffer)
                        encoded_buffer = _serialize_message_mbox(temp_msg).encode(target_encoding)
                    else:
                        encoded_buffer = processed_buffer.encode(target_encoding)

                    assert output_dir is not None
                    # We use sha1 of encoded buffer to determine filename, as before
                    with open(
                        os.path.join(output_dir, hashlib.sha1(encoded_buffer).hexdigest()),
                        'wb',
                    ) as f:
                        f.write(encoded_buffer)
                else:
                    text_content = processed_buffer
                    if settings.headers_only:
                        # For structured formats (JSON, XML, CSV, SQLite), we want empty text field
                        # For text/HTML formats, we might have formatted header in processed_buffer, which we want to keep
                        # But if the format is JSON/XML/CSV/SQLite, we want to strip that.
                        if settings.format in ('json', 'xml', 'csv', 'sqlite'):
                            text_content = ""

                    collected_messages.append(
                        replace(
                            parsed_message,
                            text=text_content,
                        )
                    )
            if settings.limit is not None and count > settings.limit:
                break

    if not settings.individual_files:
        ordered_messages = (
            _order_messages_by_thread(collected_messages)
            if settings.threaded
            else collected_messages
        )

        writers: dict[str, Callable[[list[ProcessedMessage], str | None, str], None]] = {
            'json': _write_json,
            'xml': _write_xml,
            'html': _write_html,
            'markdown': _write_markdown,
            'text': _write_text,
            'csv': _write_csv,
            'mbox': _write_mbox,
            'sqlite': _write_sqlite,
        }

        writer = writers.get(settings.format, _write_text)
        output_encoding = 'utf-8'
        if settings.format == 'text':
            output_encoding = settings.encoding
        writer(ordered_messages, resolved_output_path, output_encoding)


def process_file(
    input_path: str,
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:
    process_merged_files([input_path], settings, logger)


def _message_to_dict(message: ProcessedMessage) -> dict[str, Any]:
    return {
        'header': message.header.as_dict,
        'text': message.text,
        'depth': message.depth,
        'thread_id': message.thread_id,
        'parent_msgnum': message.parent_msgnum,
    }


def _write_json(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
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

    header_element = ET.SubElement(msg_element, 'header')
    header_data = message.header.as_dict
    for key, value in header_data.items():
        child = ET.SubElement(header_element, key)
        child.text = XML_INVALID_CHAR_PATTERN.sub('', str(value))

    text_element = ET.SubElement(msg_element, 'text')
    text_element.text = XML_INVALID_CHAR_PATTERN.sub('', message.text)

    return msg_element


def _xml_element_to_str(element: ET.Element) -> str:
    """Helper to indent and serialize an XML element to a string."""
    ET.indent(element, space='  ')
    return ET.tostring(element, encoding='unicode')


def _serialize_message_xml(message: ProcessedMessage) -> str:
    root = _message_to_xml_element(message)
    return _xml_element_to_str(root)


def _write_xml(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
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
        f'<title>{title}</title>',
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


def _render_single_message_html(message: ProcessedMessage) -> list[str]:
    parts = []
    parts.append('<div class="message">')

    # Header
    header = message.header
    parts.append('<div class="header">')
    parts.append(f'<div><strong>Date:</strong> {html.escape(header.msgdate)} {html.escape(header.msgtime)}</div>')
    parts.append(f'<div><strong>From:</strong> {html.escape(header.msgfrom)}</div>')
    parts.append(f'<div><strong>To:</strong> {html.escape(header.msgto)}</div>')
    parts.append(f'<div><strong>Subject:</strong> {html.escape(header.msgsubject)}</div>')
    # Conference number is always present as an int
    parts.append(f'<div><strong>Conference:</strong> {header.confnum}</div>')
    if header.msgnum is not None:
        parts.append(f'<div><strong>Number:</strong> {header.msgnum}</div>')
    parts.append('</div>')

    # Body
    escaped_text = html.escape(message.text.replace('\r\n', '\n'))
    parts.append('<pre class="body">')
    parts.append(escaped_text)
    parts.append('</pre>')
    parts.append('</div>')

    return parts


def _serialize_message_html(message: ProcessedMessage) -> str:
    html_parts = _get_html_header('QWK Message')
    html_parts.extend(_render_single_message_html(message))
    html_parts.extend(_get_html_footer())

    return '\n'.join(html_parts)


def _render_single_message_markdown(message: ProcessedMessage) -> list[str]:
    header = message.header
    parts = []
    parts.append(f"## {header.msgsubject}")
    parts.append(f"- **Date:** {header.msgdate} {header.msgtime}")
    parts.append(f"- **From:** {header.msgfrom}")
    parts.append(f"- **To:** {header.msgto}")
    parts.append(f"- **Conference:** {header.confnum}")
    if header.msgnum is not None:
        parts.append(f"- **Number:** {header.msgnum}")
    parts.append("")
    parts.append(message.text.replace('\r\n', '\n'))
    parts.append("")
    parts.append("---")
    return parts


def _serialize_message_markdown(message: ProcessedMessage) -> str:
    md_parts = ["# QWK Message\n"]
    md_parts.extend(_render_single_message_markdown(message))
    return '\n'.join(md_parts)


def _write_html(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    html_parts = _get_html_header('QWK Messages')
    current_depth = 0

    for message in messages:
        while current_depth < message.depth:
            html_parts.append('<div class="reply">')
            current_depth += 1
        while current_depth > message.depth:
            html_parts.append('</div>')
            current_depth -= 1

        html_parts.extend(_render_single_message_html(message))

    while current_depth > 0:
        html_parts.append('</div>')
        current_depth -= 1

    html_parts.extend(_get_html_footer())

    _write_text_output('\n'.join(html_parts), output_path, encoding='utf-8')


def _write_markdown(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    md_parts = ["# QWK Messages\n"]

    for message in messages:
        single_md = _render_single_message_markdown(message)
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
    """Parse QWK date (MM-DD-YY) and time (HH:MM) into a datetime object.

    Args:
        msgdate: Date string in 'MM-DD-YY' format.
        msgtime: Time string in 'HH:MM' format.

    Returns:
        A datetime object. Defaults to epoch if parsing fails.
    """
    try:
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
    except (ValueError, IndexError):
        # Fallback for invalid dates
        return datetime.datetime(1970, 1, 1, 0, 0)


def _serialize_message_mbox(message: ProcessedMessage) -> str:
    """Serialize a message to mbox format."""
    header = message.header

    # Parse date
    dt = _parse_qwk_date(header.msgdate, header.msgtime)

    # Format dates
    # "From " line uses ctime format: "Day Mon DD HH:MM:SS YYYY"
    # email.utils.formatdate uses RFC 2822

    from_line_date = dt.ctime()
    rfc_date = email.utils.format_datetime(dt)

    sender_addr = "user@example.com"
    if "@" in header.msgfrom:
         sender_addr = header.msgfrom
    else:
         # Create a safe address from the name
         safe_name = re.sub(r'[^A-Za-z0-9]', '.', header.msgfrom).strip('.')
         sender_addr = f"{safe_name}@example.com"

    # Escape "From " lines in body
    body_lines = []
    for line in message.text.splitlines():
        if line.startswith("From "):
            body_lines.append(">" + line)
        else:
            body_lines.append(line)
    body = "\n".join(body_lines)

    # Construct mbox entry
    # From <sender> <date>
    parts = [f"From {sender_addr} {from_line_date}"]
    parts.append(f"From: {header.msgfrom}")
    parts.append(f"To: {header.msgto}")
    parts.append(f"Subject: {header.msgsubject}")
    parts.append(f"Date: {rfc_date}")

    # Generate a unique Message-ID
    # <confnum.msgnum@qwk>
    msg_id = f"<{header.confnum}.{header.msgnum if header.msgnum is not None else 'x'}@qwk>"
    parts.append(f"Message-ID: {msg_id}")
    parts.append(f"X-QWK-Conference: {header.confnum}")

    parts.append("")  # Separator before body
    parts.append(body)
    parts.append("")  # Trailing newline required by mbox

    return "\n".join(parts)


def _write_mbox(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    """Write messages to an mbox file."""
    parts = []
    for message in messages:
        parts.append(_serialize_message_mbox(message))

    _write_text_output("\n".join(parts), output_path, encoding=encoding)


def _write_text(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    """Write messages to text format with indentation for threads."""
    parts = []
    for message in messages:
        text = message.text
        if message.depth > 0:
            indent = "  " * message.depth
            lines = text.splitlines(keepends=True)
            indented_lines = [indent + line for line in lines]
            text = "".join(indented_lines)
        parts.append(text)

    _write_text_output("".join(parts), output_path, encoding=encoding)


def _write_csv(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    output = io.StringIO()

    header_fields = [f.name for f in fields(MessageHeader)]
    fieldnames = header_fields + ['text', 'depth', 'thread_id', 'parent_msgnum']

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for message in messages:
        row = message.header.as_dict
        row['text'] = message.text
        row['depth'] = message.depth
        row['thread_id'] = message.thread_id
        row['parent_msgnum'] = message.parent_msgnum
        writer.writerow(row)

    _write_text_output(output.getvalue(), output_path, encoding=encoding)


def _write_sqlite(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
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
            parent_message_number INTEGER
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
                parent_message_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            msg.parent_msgnum
        ))

    conn.commit()
    conn.close()


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
                info_entry["bbs_info"] = bbs_info.as_dict()

            if len(file_data) < BLOCK_SIZE or not file_data.startswith(b'Produced '):
                if settings.format != 'json':
                    print(f"File: {_colorize(input_path, CYAN)}")
                    if len(file_data) < BLOCK_SIZE:
                        print("  Invalid or empty file.")
                    else:
                        print("  Not a valid QWK messages.dat file.")
                all_info.append(info_entry)
                continue

            total_messages = 0
            conference_counts = defaultdict(int)

            try:
                for message in parse_messages(
                    file_data, None, settings.encoding, headers_only=True
                ):
                    total_messages += 1
                    conference_counts[message.confnum] += 1
            except MessagesDatFormatError:
                pass

            info_entry["total_messages"] = total_messages
            if bbs_info:
                bbs_info.total_messages = total_messages
                info_entry["bbs_info"] = bbs_info.as_dict()

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

        except Exception as e:
            logger.error(f"Error reading info for {input_path}: {e}")

    if settings.format == 'json':
        print(json.dumps(all_info, indent=4, ensure_ascii=False))


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
            if settings.format == 'json':
                output_filename += '.json'
            elif settings.format == 'xml':
                output_filename += '.xml'
            elif settings.format == 'html':
                output_filename += '.html'
            elif settings.format == 'markdown':
                output_filename += '.md'
            elif settings.format == 'csv':
                output_filename += '.csv'
            elif settings.format == 'mbox':
                output_filename += '.mbox'
            else:
                output_filename += '.txt'
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
