import sys
import argparse
import zipfile
import struct
import re
import hashlib
import os
import logging
import json
import html
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, replace
from contextlib import contextmanager, nullcontext
from typing import Any, Callable, Protocol

__version__ = "0.1.0"

BLOCK_SIZE = 128
MESSAGES_FILENAME = 'messages.dat'
CONTROL_FILENAME = 'control.dat'

QUOTE_HEADER_PATTERNS = [
    re.compile(
        r".*(replied|'s comment|said|wrote|was talking|yelled|writes|mentioned|spake thusly|carried on|babbled on|spoke|wrote a message)( in a message| the following| this)? to "
    ),
    re.compile(
        r"^\s*( -=>|\*\*\*|Yo!)?\s*(Quoting|Answering msg from|In a msg on|Reply|QUOTING|In a message originally|Quoted from a message|In a message).* to "
    ),
]
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

    if is_yenc_marker and line.startswith('=ybegin'):
        return True, True, in_uue_block

    if in_yenc_block or is_yenc_marker:
        if is_yenc_marker and line.startswith('=yend'):
            return True, False, in_uue_block
        return True, True, in_uue_block

    if RE_BASE64_PATTERN.match(line):
        return True, in_yenc_block, in_uue_block

    if RE_UUE_DATA_PATTERN.match(line) or RE_UUE_PATTERN.match(line):
        return True, in_yenc_block, True

    if RE_UUE_LOOSE_PATTERN.match(line):
        if in_uue_block:
            return True, in_yenc_block, True
        if previous_line and (
            RE_UUE_DATA_PATTERN.match(previous_line)
            or RE_UUE_PATTERN.match(previous_line)
        ):
            return True, in_yenc_block, True

    if in_uue_block:
        if line.strip() == 'end':
            return True, in_yenc_block, False
        return False, in_yenc_block, False

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
    quiet: bool = False


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
        except (struct.error, ValueError) as error:
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
) -> dict[int, str]:
    if logger is None:
        logger = logging.getLogger(__name__)

    if len(control_data) < 11:
        raise ControlDatFormatError(
            "CONTROL.DAT is too short; header information missing."
        )

    try:
        num_conferences = int(control_data[10]) + 1
    except ValueError as error:
        raise ControlDatFormatError(
            f"Invalid conference count in CONTROL.DAT: {control_data[10]!r}"
        ) from error

    board_dict: dict[int, str] = {}
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
) -> Iterator[ParsedMessage]:
    """Parse a QWK messages.dat payload into message objects.

    Args:
        file_data: Raw bytes from a messages.dat file.
        progress_bar: Optional tqdm-compatible progress reporter to update as blocks are read.
        encoding: Character encoding to use when decoding messages.

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
            header = MessageHeader.from_bytes(record, encoding)
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
                blocks_remaining = 0
                continue

            blocks_remaining = header.numblocks - 1
        else:
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
) -> str:
    """Transform a raw message body according to processing settings.

    Args:
        message_buffer: The original message text with DOS-style newlines.
        truncate_signatures: Whether to stop output at common signature separators.
        cut_quoting: Whether to remove quoted text and quote headers.
        binaries_removal: Whether to strip uuencoded, Base64, and yEnc payloads.
        redact_pii: Whether to redact email addresses and phone numbers.

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
        new_lines.append(line)
        previous_line = line

    return '\r\n'.join(new_lines) + '\r\n'


def _create_progress_bar(total: int, quiet: bool) -> Any:
    """Create a progress bar instance or a null context.

    Args:
        total: Total number of units (bytes).
        quiet: If True, suppress progress output.

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
            desc='Processing messages',
        )
    except ImportError:  # pragma: no cover - tqdm is optional
        if not getattr(_create_progress_bar, "_logged_missing_tqdm", False):
            logging.getLogger(__name__).info('Install tqdm to enable progress reporting.')
            setattr(_create_progress_bar, "_logged_missing_tqdm", True)
        return nullcontext()


def process_file(
    input_path: str,
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
            raise ValueError('The output path must be a directory when using individual files.')
        os.makedirs(output_dir, exist_ok=True)
    file_data, board_dict = load_data(input_path, logger, settings.encoding)
    collected_messages: list[ParsedMessage] = []

    separator_mode = settings.separator
    if separator_mode == 'auto':
        if settings.individual_files or settings.format in ('json', 'xml', 'html'):
            separator_mode = 'none'
        else:
            separator_mode = 'dashes'
    separator_str = ""
    if separator_mode == 'dashes':
        separator_str = ("-" * 80) + "\r\n"
    elif separator_mode == 'blank':
        separator_str = "\r\n"

    with _create_progress_bar(len(file_data), settings.quiet) as progress_bar:
        for parsed_message in parse_messages(
            file_data,
            progress_bar,
            settings.encoding,
        ):
            if (
                (settings.private is True or parsed_message.header.is_private is False)
                and parsed_message.header.is_password is False
            ):
                processed_buffer = process_message(
                    parsed_message.text,
                    settings.truncate_signatures,
                    settings.cut_quoting,
                    settings.binaries_removal,
                    settings.redact_pii,
                )
                if not settings.no_header and settings.format != 'html':
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
                if settings.format == 'text' or (not settings.no_header and settings.format != 'html'):
                    processed_buffer = separator_str + processed_buffer

                if settings.individual_files:
                    target_encoding = 'utf-8'
                    if settings.format == 'text':
                        target_encoding = settings.encoding

                    encoded_buffer = processed_buffer.encode(target_encoding)
                    assert output_dir is not None
                    with open(
                        os.path.join(output_dir, hashlib.sha1(encoded_buffer).hexdigest()),
                        'wb',
                    ) as f:
                        f.write(encoded_buffer)
                else:
                    collected_messages.append(
                        replace(
                            parsed_message,
                            text=processed_buffer,
                        )
                    )

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
            'text': _write_text,
        }

        writer = writers.get(settings.format, _write_text)
        output_encoding = 'utf-8'
        if settings.format == 'text':
            output_encoding = settings.encoding
        writer(ordered_messages, resolved_output_path, output_encoding)


def _write_json(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    output_data = []
    for message in messages:
        msg_dict = {
            'header': message.header.as_dict,
            'text': message.text,
            'depth': message.depth,
            'thread_id': message.thread_id,
            'parent_msgnum': message.parent_msgnum,
        }
        output_data.append(msg_dict)
    output_json = json.dumps(output_data, indent=4)
    _write_text_output(output_json, output_path, encoding='utf-8')


XML_INVALID_CHAR_PATTERN = re.compile(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]')


def _write_xml(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    root = ET.Element('messages')
    for message in messages:
        msg_element = ET.SubElement(root, 'message')

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

    ET.indent(root, space='  ')
    xml_bytes = ET.tostring(root, encoding='utf-8')
    xml_text = xml_bytes.decode('utf-8')

    _write_text_output(xml_text, output_path, encoding='utf-8')


def _write_html(
    messages: list[ProcessedMessage], output_path: str | None, encoding: str = 'utf-8'
) -> None:
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="utf-8" />',
        '<title>QWK Messages</title>',
        '<style>',
        '.reply { margin-left: 2em; border-left: 2px solid #ccc; padding-left: 1em; }',
        '.message { margin-bottom: 1em; border: 1px solid #eee; padding: 1em; }',
        '.header { background-color: #f9f9f9; padding: 0.5em; margin-bottom: 0.5em; }',
        '.body { white-space: pre-wrap; font-family: monospace; }',
        '</style>',
        '</head>',
        '<body>',
    ]

    current_depth = 0

    for message in messages:
        while current_depth < message.depth:
            html_parts.append('<div class="reply">')
            current_depth += 1
        while current_depth > message.depth:
            html_parts.append('</div>')
            current_depth -= 1

        html_parts.append('<div class="message">')

        # Header
        header = message.header
        html_parts.append('<div class="header">')
        html_parts.append(f'<div><strong>Date:</strong> {html.escape(header.msgdate)} {html.escape(header.msgtime)}</div>')
        html_parts.append(f'<div><strong>From:</strong> {html.escape(header.msgfrom)}</div>')
        html_parts.append(f'<div><strong>To:</strong> {html.escape(header.msgto)}</div>')
        html_parts.append(f'<div><strong>Subject:</strong> {html.escape(header.msgsubject)}</div>')
        # Conference number is always present as an int
        html_parts.append(f'<div><strong>Conference:</strong> {header.confnum}</div>')
        if header.msgnum is not None:
            html_parts.append(f'<div><strong>Number:</strong> {header.msgnum}</div>')
        html_parts.append('</div>')

        # Body
        escaped_text = html.escape(message.text.replace('\r\n', '\n'))
        html_parts.append('<pre class="body">')
        html_parts.append(escaped_text)
        html_parts.append('</pre>')
        html_parts.append('</div>')

    while current_depth > 0:
        html_parts.append('</div>')
        current_depth -= 1

    html_parts.append('</body>')
    html_parts.append('</html>')

    _write_text_output('\n'.join(html_parts), output_path, encoding='utf-8')


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


def _write_text_output(content: str, output_path: str | None, *, encoding: str = 'latin1') -> None:
    if output_path is None:
        if not content.endswith('\n'):
            content += '\n'
        sys.stdout.write(content)
    else:
        with open(output_path, 'w', encoding=encoding) as f:
            f.write(content)


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('input_paths', help='The QWK archive files or messages.dat files you want to read.', nargs='+')
    parser.add_argument(
        '-o',
        '--output',
        dest='output_path',
        help='Where to save the results (filename or folder). Defaults to showing on screen.',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        help=(
            'Show extra details like conference names and message numbers.'
        ),
        action='store_true',
    )
    parser.add_argument('-p', '--private', help="Include messages marked as 'Private'.", action='store_true')
    parser.add_argument('-n', '--noheader', help='Do not include the message info (header) in the body text.', action='store_true')
    parser.add_argument('-t', '--truncate-signatures', dest='truncatesignatures', help="Stop reading when a common signature (like '---') is found.", action='store_true')
    parser.add_argument('-c', '--cut-quoting', dest='cutquoting', help="Remove text quoted from previous messages (lines starting with '>').", action='store_true')
    parser.add_argument('-i', '--individual-files', dest='individualfiles', help='Save each message as its own separate file. (Cannot use with --threaded).', action='store_true')
    parser.add_argument('-T', '--threaded', help='Group replies with their original messages. (Cannot use with --individual-files).', action='store_true')
    parser.add_argument('-b', '--binaries-removal', dest='binariesremoval', help='Remove binary data attachments (like images or programs).', action='store_true')
    parser.add_argument('-r', '--redact-pii', dest='redactpii', help='Hide personal info like email addresses and phone numbers.', action='store_true')
    parser.add_argument('--clean', help='Enable all content cleaning options: truncate signatures, cut quoting, and remove binaries.', action='store_true')
    parser.add_argument('-q', '--quiet', help='Do not show the progress bar.', action='store_true')
    parser.add_argument(
        '-l',
        '--loglevel',
        help='Control how much technical detail to display (DEBUG, INFO, WARNING, ERROR).',
        default='INFO',
    )
    parser.add_argument(
        '--format',
        help='Choose the output format: text, json, xml, or html.',
        default='text',
        choices=['text', 'json', 'xml', 'html'],
    )
    parser.add_argument(
        '--separator',
        choices=['auto', 'none', 'dashes', 'blank'],
        default='auto',
        help='Choose how to separate messages in the output.',
    )
    parser.add_argument(
        '--encoding',
        help='Character encoding of the input file (default: cp437)',
        default='cp437',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f"%(prog)s {__version__}",
        help='Show the version number and exit.',
    )
    args = parser.parse_args()

    if args.threaded and args.individualfiles:
        parser.error("Threading is not compatible with individual files output.")

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {args.loglevel}')
    logging.basicConfig(level=numeric_level)
    logger = logging.getLogger(__name__)

    input_paths = args.input_paths
    output_path = args.output_path

    if args.individualfiles:
        if output_path is None:
            parser.error('Output directory is required when writing individual files.')
        if os.path.exists(output_path) and not os.path.isdir(output_path):
            parser.error('Output path must be a directory when writing individual files.')
        output_mode = 'file'
        resolved_output_path = output_path
    elif len(input_paths) > 1:
        if not output_path:
            parser.error('Output directory is required when processing multiple files.')
        output_mode = 'file'
        resolved_output_path = output_path
    else:
        output_mode = 'stdout' if not output_path else 'file'
        resolved_output_path = output_path

    settings = ProcessingSettings(
        verbose=args.verbose,
        private=args.private,
        no_header=args.noheader,
        truncate_signatures=args.truncatesignatures or args.clean,
        cut_quoting=args.cutquoting or args.clean,
        individual_files=args.individualfiles,
        threaded=args.threaded,
        binaries_removal=args.binariesremoval or args.clean,
        redact_pii=args.redactpii,
        quiet=args.quiet,
        format=args.format,
        separator=args.separator,
        output_mode=output_mode,
        output_path=resolved_output_path,
        encoding=args.encoding,
    )

    if len(input_paths) > 1:
        had_errors = process_multiple_files(input_paths, output_path, settings, logger)
        if had_errors:
            sys.exit(1)
    else:
        try:
            process_file(input_paths[0], settings, logger)
        except PROCESSING_EXCEPTIONS as error:
            logger.error(error)
            sys.exit(1)


def _normalize_subject(subject: str) -> str:
    """Normalize subject line for threading by removing prefixes."""
    s = subject.strip()
    while True:
        m = re.match(r'^(?:re|fw|fwd)[:\[\s-]', s, re.IGNORECASE)
        if not m:
            break
        s = re.sub(r'^\s*(?:re|fw|fwd)(?:\[\d+\])?[:\s-]+\s*', '', s, flags=re.IGNORECASE)
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
    children: dict[int, list[int]] = defaultdict(list)
    roots: list[int] = []

    # 1. Indexing
    for index, message in enumerate(messages):
        if message.msgnum is not None:
            index_by_key[(message.confnum, message.msgnum)] = index

        subj = _normalize_subject(message.header.msgsubject)
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
            subj = _normalize_subject(message.header.msgsubject)
            if subj:
                candidates = index_by_subject.get((message.confnum, subj), [])
                # Prefer candidates that appear before this message
                preceding = [i for i in candidates if i < index]
                if preceding:
                    parent_index = preceding[-1]

        if parent_index is not None and parent_index != index:
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

            if child_idx not in visited:
                enter_node(child_idx, depth + 1, thread_id)

    for root_idx in roots:
        visit_iterative(root_idx)

    for idx in range(len(messages)):
        if idx not in visited:
            visit_iterative(idx)

    return ordered_messages


if __name__ == '__main__':
    main()
