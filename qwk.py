import sys
import argparse
import zipfile
import struct
import re
import hashlib
import os
import logging
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, fields
from typing import Any, Dict, Iterator, List, Mapping, NamedTuple, Optional, Tuple

BLOCK_SIZE = 128
MESSAGES_FILENAME = 'messages.dat'
CONTROL_FILENAME = 'control.dat'

QWK_NEWLINE_CHAR = '\xe3'  # DOS CP437 newline character

QUOTE_HEADER_PATTERNS = [
    re.compile(
        r".*(replied|'s comment|said|wrote|was talking|yelled|writes|mentioned|spake thusly|carried on|babbled on|spoke|wrote a message)( in a message| the following| this)? to "
    ),
    re.compile(
        r"^\s*( -=>|\*\*\*|Yo!)?\s*(Quoting|Answering msg from|In a msg on|Reply|QUOTING|In a message originally|Quoted from a message|In a message).* to "
    ),
]
RE_QUOTE_PATTERN = re.compile(r'^\s*[A-Za-z\-\=]{0,4}\s?(>|\xb3|\||\})')
RE_UUE_PATTERN = re.compile(r'^begin\s\d{3}\s')
RE_UUE_DATA_PATTERN = re.compile(r'^M[\x21-\x60]{60}$')
RE_UUE_LOOSE_PATTERN = re.compile(r'[\x21-\x4c][\x21-\x60]{4,60}$')
RE_BASE64_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{60,}$')
RE_YENC_PATTERN = re.compile(r'^=y(begin|part|end)')
RE_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
RE_PHONE_PATTERN = re.compile(r'\b(?:\+\d{1,3}[-\.\s]?)?(?:\(\d{1,4}\)[-\.\s]?)?\d{1,4}[-\.\s]?\d{1,4}[-\.\s]?\d{1,9}\b')

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
    " *** ",
)


try:
    from tqdm import tqdm as tqdm_factory  # type: ignore
except ImportError:  # pragma: no cover - tqdm is optional
    tqdm_factory = None  # type: ignore[assignment]


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
    quiet: bool = False
    output_target: str = 'auto'


@dataclass
class ParsedMessage:
    text: str
    is_private: bool
    is_password: bool
    msgnum: Optional[int]
    refnum: Optional[int]
    confnum: int
    header: 'MessageHeader'


@dataclass
class ProcessedMessage:
    text: str
    msgnum: Optional[int]
    refnum: Optional[int]
    confnum: int
    header: 'MessageHeader'


@dataclass
class MessageHeader:
    status: bytes
    msgnum: bytes
    msgdate: bytes
    msgtime: bytes
    msgto: bytes
    msgfrom: bytes
    msgsubject: bytes
    msgpassword: bytes
    refnum: bytes
    numblocks: bytes
    msgflag: bytes
    confnum: int
    lognum: int
    nettag: bytes

    def _to_dict(self):
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bytes):
                result[field.name] = value.decode('latin1').strip()
            else:
                result[field.name] = value
        return result


class MessagesDatFormatError(Exception):
    """Raised when the input file is not a valid messages.dat file."""


class ControlDatFormatError(Exception):
    """Raised when the control.dat file is not a valid format."""


class InvalidMessageTypeError(Exception):
    """Raised when an unexpected message type is encountered."""

    def __init__(self, message_type: str) -> None:
        super().__init__(f"Invalid message type '{message_type}'")
        self.message_type = message_type


def load_data(input_path: str, logger: logging.Logger) -> Tuple[bytearray, Dict[int, str]]:
    board_dict: Dict[int, str] = {}
    if zipfile.is_zipfile(input_path):
        messages_name = ''
        control_name = ''
        try:
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
                    num_conferences = int(control_data[10]) + 1
                    for i in range(num_conferences):
                        index = 11 + i * 2
                        try:
                            conf_number_raw = control_data[index]
                            conf_name_raw = control_data[index + 1]
                        except IndexError as error:
                            raise ControlDatFormatError(
                                "CONTROL.DAT is truncated; missing conference entries."
                            ) from error
                        try:
                            conf_number = int(conf_number_raw)
                        except ValueError as error:
                            raise ControlDatFormatError(
                                f"Invalid conference number in CONTROL.DAT: {conf_number_raw!r}"
                            ) from error
                        conf_name = conf_name_raw.decode('latin1')
                        board_dict[conf_number] = conf_name
                else:
                    logger.warning("CONTROL.DAT not found, conference names will not be available.")
        except zipfile.BadZipFile as error:
            raise zipfile.BadZipFile("Error: The provided file is not a valid zip file.") from error
    else:
        with open(input_path, 'rb') as f:
            file_data = bytearray(f.read())
    return file_data, board_dict


def _parse_header_record(record: bytes) -> Tuple[MessageHeader, bool, bool]:
    header_data = struct.unpack('<c7s8s5s25s25s25s12s8s6scHHc', record)
    header = MessageHeader(*header_data)
    message_type = header.status.decode('latin1')
    is_password = False
    is_private = True
    if message_type in ['+', '*', '~', '`']:
        pass
    elif message_type in ['%', '^', '!', '#', '$']:
        is_password = True
    elif message_type in [' ', '-']:
        is_private = False
    else:
        raise InvalidMessageTypeError(message_type)
    return header, is_private, is_password


def parse_messages(
    file_data: bytearray,
    progress_bar: Optional[Any],
) -> Iterator[ParsedMessage]:
    blocks_remaining = 0
    message_buffer = ''
    is_private = True
    is_password = False
    current_msgnum: Optional[int] = None
    current_refnum: Optional[int] = None
    current_confnum = 0
    for i in range(0, len(file_data), BLOCK_SIZE):
        record = file_data[i:i + BLOCK_SIZE]
        if progress_bar is not None:
            progress_bar.update(len(record))
        if i == 0:
            if record[0:9] != b'Produced ':
                raise MessagesDatFormatError
            continue
        if blocks_remaining == 0:
            header, is_private, is_password = _parse_header_record(record)

            msgnum_text = header.msgnum.decode('latin1').strip()
            current_msgnum = int(msgnum_text) if msgnum_text.isdigit() else None

            refnum_text = header.refnum.decode('latin1').strip()
            if refnum_text.isdigit():
                current_refnum = int(refnum_text)
                if current_refnum == 0:
                    current_refnum = None
            else:
                current_refnum = None

            current_confnum = header.confnum

            message_buffer = ''
            temp_blocks = header.numblocks.decode('latin1').strip()
            blocks_remaining = int(temp_blocks) - 1
        else:
            temp_record = record.decode('latin1').replace(QWK_NEWLINE_CHAR, '\r\n')
            if blocks_remaining == 1:
                temp_record = temp_record.rstrip() + '\r\n'
            message_buffer += temp_record
            blocks_remaining = blocks_remaining - 1
            if blocks_remaining == 0:
                yield ParsedMessage(
                    text=message_buffer,
                    is_private=is_private,
                    is_password=is_password,
                    msgnum=current_msgnum,
                    refnum=current_refnum,
                    confnum=current_confnum,
                    header=header,
                )


def _format_message_header(
    header: MessageHeader,
    boarddict: Mapping[int, str],
    verbose: bool,
) -> str:
    not_found_flag = False
    try:
        conf_name = boarddict[header.confnum]
    except KeyError:
        conf_name = str(header.confnum)
        not_found_flag = True

    header_parts: List[str] = []
    header_parts.append(("-" * 80) + "\r\n")
    if verbose or not not_found_flag:
        header_parts.append("Conference: " + str(conf_name) + "\r\n")
    if verbose:
        header_parts.append(
            "Message number: " + header.msgnum.decode("latin1") + (" " * 20)
        )
    header_parts.append(
        "Date: "
        + header.msgdate.decode("latin1")
        + " "
        + header.msgtime.decode("latin1")
        + "\r\n"
    )
    header_parts.append("From: " + header.msgfrom.decode("latin1") + "\r\n")
    header_parts.append("To: " + header.msgto.decode("latin1") + "\r\n")
    header_parts.append("Subject: " + header.msgsubject.decode("latin1") + "\r\n")
    if verbose:
        header_parts.append(
            "Reference number: " + header.refnum.decode("latin1") + "\r\n"
        )
    header_parts.append("\r\n")
    return "".join(header_parts)


def process_message(
    message_buffer: str,
    truncate_signatures: bool,
    cut_quoting: bool,
    binaries_removal: bool,
    redact_pii: bool,
) -> str:
    lines = message_buffer.splitlines()

    new_lines = []
    seen_non_blank_line = False
    in_yenc_block = False
    for j, line in enumerate(lines):
        if truncate_signatures and (
            line in SIGNATURE_PATTERNS_EXACT
            or line.startswith(SIGNATURE_PATTERNS_STARTSWITH)
        ):
            break
        if cut_quoting:
            if not seen_non_blank_line:
                if any(pattern.match(line) for pattern in QUOTE_HEADER_PATTERNS):
                    continue
            if RE_QUOTE_PATTERN.match(line):
                continue
            elif j > 0 and j < (len(lines) - 1) \
                    and RE_QUOTE_PATTERN.match(lines[j - 1]) \
                    and RE_QUOTE_PATTERN.match(lines[j + 1]):
                continue
        if binaries_removal:
            is_yenc_marker = RE_YENC_PATTERN.match(line)

            if is_yenc_marker and line.startswith('=ybegin'):
                in_yenc_block = True

            if in_yenc_block or is_yenc_marker:
                if is_yenc_marker and line.startswith('=yend'):
                    in_yenc_block = False
                continue

            if (
                RE_BASE64_PATTERN.match(line)
                or RE_UUE_DATA_PATTERN.match(line)
                or RE_UUE_PATTERN.match(line)
            ):
                continue
            if RE_UUE_LOOSE_PATTERN.match(line):
                prev_line = lines[max(0, j - 1)]
                if RE_UUE_DATA_PATTERN.match(prev_line) or RE_UUE_PATTERN.match(prev_line):
                    continue
        if not seen_non_blank_line and not line.strip():
            continue

        seen_non_blank_line = True
        if redact_pii:
            line = RE_EMAIL_PATTERN.sub('[EMAIL]', line)
            line = RE_PHONE_PATTERN.sub('[PHONE]', line)
        new_lines.append(line)

    return '\r\n'.join(new_lines) + '\r\n'


def process_file(
    input_path: str,
    output_path: Optional[str],
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:

    output_dir: Optional[str] = None
    output_mode = 'file' if settings.individual_files else settings.output_target
    if output_mode == 'auto':
        output_mode = 'file' if output_path is not None else 'stdout'

    if settings.individual_files:
        if output_path is None:
            raise ValueError('An output path is required when using individual files.')
        if os.path.exists(output_path) and not os.path.isdir(output_path):
            raise ValueError('The output path must be a directory when using individual files.')
        output_dir = output_path
        os.makedirs(output_dir, exist_ok=True)
    else:
        if output_mode == 'file' and output_path is None:
            raise ValueError('An output path is required when output is set to file.')
        if output_mode == 'stdout' and output_path is not None:
            raise ValueError('An output path cannot be provided when output is set to stdout.')

    resolved_output_path: Optional[str] = None if output_mode == 'stdout' else output_path

    file_data, board_dict = load_data(input_path, logger)
    collected_messages: List[ProcessedMessage] = []

    progress_bar: Optional[Any] = None
    if not settings.quiet:
        if tqdm_factory is None:
            logger.info('Install tqdm to enable progress reporting.')
        else:
            progress_bar = tqdm_factory(
                total=len(file_data),
                unit='B',
                unit_scale=True,
                desc='Processing messages',
            )

    try:
        for parsed_message in parse_messages(
            file_data,
            progress_bar,
        ):
            if (settings.private is True or parsed_message.is_private is False) and parsed_message.is_password is False:
                processed_buffer = process_message(
                    parsed_message.text,
                    settings.truncate_signatures,
                    settings.cut_quoting,
                    settings.binaries_removal,
                    settings.redact_pii,
                )
                if not settings.no_header:
                    leading_newlines = 0
                    text_prefix = parsed_message.text
                    while text_prefix.startswith('\r\n'):
                        leading_newlines += 1
                        text_prefix = text_prefix[2:]
                    if leading_newlines and not processed_buffer.startswith('\r\n'):
                        processed_buffer = ('\r\n' * leading_newlines) + processed_buffer
                    header_text = _format_message_header(
                        parsed_message.header,
                        board_dict,
                        settings.verbose,
                    )
                    processed_buffer = header_text + processed_buffer
                if settings.individual_files:
                    encoded_buffer = processed_buffer.encode('latin1')
                    assert output_dir is not None
                    with open(
                        os.path.join(output_dir, hashlib.sha1(encoded_buffer).hexdigest()),
                        'wb',
                    ) as f:
                        f.write(encoded_buffer)
                else:
                    collected_messages.append(
                        ProcessedMessage(
                            text=processed_buffer,
                            msgnum=parsed_message.msgnum,
                            refnum=parsed_message.refnum,
                            confnum=parsed_message.confnum,
                            header=parsed_message.header,
                        )
                    )
    finally:
        if progress_bar is not None:
            progress_bar.close()

    if not settings.individual_files:
        if settings.threaded:
            ordered_messages = _order_messages_by_thread(collected_messages)
        else:
            ordered_messages = collected_messages

        if settings.format == 'json':
            _export_json(ordered_messages, resolved_output_path)
        elif settings.format == 'xml':
            _export_xml(ordered_messages, resolved_output_path)
        else:
            full_message_buffer = ''.join(message.text for message in ordered_messages)

            if resolved_output_path is None:
                sys.stdout.write(full_message_buffer + '\n')
            else:
                with open(resolved_output_path, 'w', encoding='latin1') as f:
                    f.write(full_message_buffer)


def _export_json(messages: List[ProcessedMessage], output_path: Optional[str]) -> None:
    output_data = []
    for message in messages:
        output_data.append(
            {
                'header': message.header._to_dict(),
                'text': message.text,
            }
        )
    output_json = json.dumps(output_data, indent=4)
    if output_path is None:
        sys.stdout.write(output_json + '\n')
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_json)


def _sanitize_xml_string(s: str) -> str:
    return re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\u10000-\u10FFFF]', '', s)


def _export_xml(messages: List[ProcessedMessage], output_path: Optional[str]) -> None:
    root = ET.Element('messages')
    for message in messages:
        msg_element = ET.SubElement(root, 'message')
        header_element = ET.SubElement(msg_element, 'header')
        header_data = message.header._to_dict()
        for key, value in header_data.items():
            child = ET.SubElement(header_element, key)
            child.text = _sanitize_xml_string(str(value))

        text_element = ET.SubElement(msg_element, 'text')
        text_element.text = _sanitize_xml_string(message.text)

    ET.indent(root, space='  ')
    xml_bytes = ET.tostring(root, encoding='utf-8')
    xml_text = xml_bytes.decode('utf-8')

    if output_path is None:
        sys.stdout.write(xml_text + '\n')
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_text)


def process_multiple_files(
    input_paths: List[str],
    output_dir: str,
    settings: ProcessingSettings,
    logger: logging.Logger,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    for input_path in input_paths:
        try:
            output_filename = os.path.splitext(os.path.basename(input_path))[0]
            if settings.format == 'json':
                output_filename += '.json'
            elif settings.format == 'xml':
                output_filename += '.xml'
            else:
                output_filename += '.txt'
            output_path = os.path.join(output_dir, output_filename)
            process_file(input_path, output_path, settings, logger)
        except (
            MessagesDatFormatError,
            InvalidMessageTypeError,
            FileNotFoundError,
            zipfile.BadZipFile,
            IOError,
        ) as error:
            logger.error("Error processing file %s: %s", input_path, error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_paths', help='One or more QWK packets or messages.dat files to process.', nargs='+')
    parser.add_argument('output_path', help='The output filename or directory. Required for multiple input files. (default: print to console for single file)', nargs='?')
    parser.add_argument(
        '-v',
        '--verbose',
        help=(
            'include additional header details such as conference information, '
            'message numbers, and reference numbers'
        ),
        action='store_true',
    )
    parser.add_argument('-p', '--private', help='export messages marked private', action='store_true')
    parser.add_argument('-n', '--noheader', help='leave out message header', action='store_true')
    parser.add_argument('-t', '--truncatesignatures', help='truncate at common signature lines (e.g., "---", " * ")', action='store_true')
    parser.add_argument('-c', '--cutquoting', help='delete quoted text (that uses ">" as quoting character)', action='store_true')
    parser.add_argument('-i', '--individualfiles', help='output individual files (output_path will be treated as a directory)', action='store_true')
    parser.add_argument('-T', '--threaded', help='group messages by thread when exporting', action='store_true')
    parser.add_argument('-b', '--binariesremoval', help='delete binaries (currently removes uuencoded and Base64-encoded blocks)', action='store_true')
    parser.add_argument('-r', '--redactpii', help='redact PII (currently e-mail addresses and phone numbers)', action='store_true')
    parser.add_argument('-q', '--quiet', help='suppress progress output', action='store_true')
    parser.add_argument(
        '-l',
        '--loglevel',
        help='Set the logging level (e.g., DEBUG, INFO, WARNING, ERROR)',
        default='INFO',
    )
    parser.add_argument(
        '--format',
        help='Set the output format (text, json, xml)',
        default='text',
        choices=['text', 'json', 'xml'],
    )
    parser.add_argument(
        '-o',
        '--output',
        help='Select the output destination for single-file processing',
        choices=['stdout', 'file'],
    )
    args = parser.parse_args()

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {args.loglevel}')
    logging.basicConfig(level=numeric_level)
    logger = logging.getLogger(__name__)

    if len(args.input_paths) > 1:
        if args.output and args.output != 'file':
            logger.error('Output must be set to "file" when processing multiple inputs.')
            sys.exit(1)
        if not args.output_path:
            logger.error('Output directory is required when processing multiple files.')
            sys.exit(1)
        output_target = 'file'
    else:
        if args.output is None:
            output_target = 'file' if args.output_path else 'stdout'
        else:
            output_target = args.output

        if output_target == 'file' and not args.output_path:
            logger.error('An output path is required when --output file is specified.')
            sys.exit(1)
        if output_target == 'stdout' and args.output_path:
            logger.error('Do not provide an output path when --output stdout is specified.')
            sys.exit(1)

    settings = ProcessingSettings(
        verbose=args.verbose,
        private=args.private,
        no_header=args.noheader,
        truncate_signatures=args.truncatesignatures,
        cut_quoting=args.cutquoting,
        individual_files=args.individualfiles,
        threaded=args.threaded,
        binaries_removal=args.binariesremoval,
        redact_pii=args.redactpii,
        quiet=args.quiet,
        format=args.format,
        output_target=output_target,
    )

    if len(args.input_paths) > 1:
        process_multiple_files(args.input_paths, args.output_path, settings, logger)
    else:
        try:
            process_file(args.input_paths[0], args.output_path, settings, logger)
        except (
            MessagesDatFormatError,
            ControlDatFormatError,
            InvalidMessageTypeError,
            FileNotFoundError,
            zipfile.BadZipFile,
            IOError,
        ) as error:
            logger.error(error)
            sys.exit(1)


def _order_messages_by_thread(messages: List[ProcessedMessage]) -> List[ProcessedMessage]:
    if not messages:
        return []

    logger = logging.getLogger(__name__)
    index_by_key: Dict[Tuple[int, int], int] = {}
    children: Dict[int, List[int]] = defaultdict(list)

    for index, message in enumerate(messages):
        if message.msgnum is not None:
            index_by_key[(message.confnum, message.msgnum)] = index
            children.setdefault(index, [])

    attached = [False] * len(messages)
    for index, message in enumerate(messages):
        if message.refnum is None:
            continue
        parent_index = index_by_key.get((message.confnum, message.refnum))
        if parent_index is None or parent_index == index:
            continue
        children[parent_index].append(index)
        attached[index] = True

    ordered_indices: List[int] = []
    visited: set[int] = set()

    cycle_reported: set[int] = set()

    def visit(idx: int, path: set[int]) -> None:
        if idx in path:
            if idx not in cycle_reported:
                message = messages[idx]
                logger.warning(
                    "Circular reference detected while threading messages (conf %s, msgnum %s).",
                    message.confnum,
                    message.msgnum if message.msgnum is not None else "unknown",
                )
                cycle_reported.add(idx)
            return
        if idx in visited:
            return
        visited.add(idx)
        ordered_indices.append(idx)

        path.add(idx)
        for child_idx in children.get(idx, []):
            visit(child_idx, path)
        path.remove(idx)

    for idx, is_attached in enumerate(attached):
        if not is_attached:
            visit(idx, set())

    for idx in range(len(messages)):
        if idx not in visited:
            visit(idx, set())

    return [messages[idx] for idx in ordered_indices]


if __name__ == '__main__':
    main()
