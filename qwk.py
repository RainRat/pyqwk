import sys
import argparse
import zipfile
import struct
import re
import hashlib
import os
import logging
from collections import defaultdict
from dataclasses import dataclass
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
    noHeader: bool
    truncateSignatures: bool
    cutQuoting: bool
    individualFiles: bool
    threaded: bool
    binariesRemoval: bool
    redactPII: bool
    quiet: bool = False


class ParsedMessage(NamedTuple):
    text: str
    is_private: bool
    is_password: bool
    msgnum: Optional[int]
    refnum: Optional[int]
    confnum: int


@dataclass
class ProcessedMessage:
    text: str
    msgnum: Optional[int]
    refnum: Optional[int]
    confnum: int


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


class MessagesDatFormatError(Exception):
    """Raised when the input file is not a valid messages.dat file."""


class InvalidMessageTypeError(Exception):
    """Raised when an unexpected message type is encountered."""

    def __init__(self, message_type: str) -> None:
        super().__init__(f"Invalid message type '{message_type}'")
        self.message_type = message_type


def load_data(input_path: str, logger: logging.Logger) -> Tuple[bytearray, Dict[int, str]]:
    boarddict: Dict[int, str] = {}
    if zipfile.is_zipfile(input_path):
        messagesname = ''
        controlname = ''
        try:
            with zipfile.ZipFile(input_path) as myzip:
                file_list = myzip.namelist()
                for file_name in file_list:
                    if file_name.lower() == MESSAGES_FILENAME:
                        messagesname = file_name
                    if file_name.lower() == CONTROL_FILENAME:
                        controlname = file_name
                if not messagesname:
                    raise FileNotFoundError(
                        f"Error: '{MESSAGES_FILENAME}' not found in the zip archive {input_path}."
                    )
                with myzip.open(messagesname) as f:
                    file_data = bytearray(f.read())
                if controlname:
                    with myzip.open(controlname) as f:
                        controldata = f.read().splitlines()
                    num_conferences = int(controldata[10]) + 1
                    for i in range(num_conferences):
                        index = 11 + i * 2
                        try:
                            conf_number = int(controldata[index])
                            conf_name = controldata[index + 1].decode('latin1')
                        except IndexError as error:
                            raise MessagesDatFormatError from error
                        boarddict[conf_number] = conf_name
        except zipfile.BadZipFile as error:
            raise zipfile.BadZipFile("Error: The provided file is not a valid zip file.") from error
    else:
        with open(input_path, 'rb') as f:
            file_data = bytearray(f.read())
    return file_data, boarddict


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
    boarddict: Mapping[int, str],
    noHeader: bool,
    verbose: bool,
    progress_bar: Optional[Any],
) -> Iterator[ParsedMessage]:
    intBlocks = 0
    messagebuffer = ''
    isPrivate = True
    isPassword = False
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
        if intBlocks == 0:
            header, isPrivate, isPassword = _parse_header_record(record)

            msgnum_text = header.msgnum.decode('latin1').strip()
            current_msgnum = int(msgnum_text) if msgnum_text.isdigit() else None

            refnum_text = header.refnum.decode('latin1').strip()
            if refnum_text.isdigit():
                current_refnum = int(refnum_text) or None
            else:
                current_refnum = None

            current_confnum = header.confnum

            not_found_flag = False
            try:
                conf_name = boarddict[header.confnum]
            except KeyError:
                conf_name = str(header.confnum)
                not_found_flag = True

            messagebuffer = ''
            if not noHeader:
                messagebuffer += ("-" * 80) + '\r\n'
                if verbose is True or not_found_flag is False:
                    messagebuffer += ('Conference: ' + str(conf_name) + '\r\n')
                if verbose is True:
                    messagebuffer += ('Message number: ' + header.msgnum.decode('latin1') + (' ' * 20))
                messagebuffer += ('Date: ' + header.msgdate.decode('latin1') + ' ' + header.msgtime.decode('latin1') + '\r\n')
                messagebuffer += ('From: ' + header.msgfrom.decode('latin1') + '\r\n')
                messagebuffer += ('To: ' + header.msgto.decode('latin1') + '\r\n')
                messagebuffer += ('Subject: ' + header.msgsubject.decode('latin1') + '\r\n')
                if verbose is True:
                    messagebuffer += ('Reference number: ' + header.refnum.decode('latin1') + '\r\n')
                messagebuffer += '\r\n'
            tempblocks = header.numblocks.decode('latin1').strip()
            intBlocks = int(tempblocks) - 1
        else:
            temprecord = record.decode('latin1').replace(QWK_NEWLINE_CHAR, '\r\n')
            if intBlocks == 1:
                temprecord = temprecord.rstrip() + '\r\n'
            messagebuffer += temprecord
            intBlocks = intBlocks - 1
            if intBlocks == 0:
                yield ParsedMessage(
                    messagebuffer,
                    isPrivate,
                    isPassword,
                    current_msgnum,
                    current_refnum,
                    current_confnum,
                )


def process_message(
    messagebuffer: str,
    truncateSignatures: bool,
    cutQuoting: bool,
    binariesRemoval: bool,
    redactPII: bool,
) -> str:
    lines = messagebuffer.splitlines()

    new_lines = []
    seenNonBlankLine = False
    for j, line in enumerate(lines):
        if truncateSignatures and (
            line in SIGNATURE_PATTERNS_EXACT
            or line.startswith(SIGNATURE_PATTERNS_STARTSWITH)
        ):
            break
        if cutQuoting:
            if seenNonBlankLine is False:
                if any(pattern.match(line) for pattern in QUOTE_HEADER_PATTERNS):
                    continue
            if RE_QUOTE_PATTERN.match(line):
                continue
            elif j > 0 and j < (len(lines) - 1) \
                    and RE_QUOTE_PATTERN.match(lines[j - 1]) \
                    and RE_QUOTE_PATTERN.match(lines[j + 1]):
                continue
        if binariesRemoval:
            if (
                RE_BASE64_PATTERN.match(line)
                or RE_UUE_DATA_PATTERN.match(line)
                or RE_UUE_PATTERN.match(line)
            ):
                continue
            if RE_UUE_LOOSE_PATTERN.match(line):
                prevLine = lines[max(0, j - 1)]
                if RE_UUE_DATA_PATTERN.match(prevLine) or RE_UUE_PATTERN.match(prevLine):
                    continue
        if seenNonBlankLine is False and line.strip() == '':
            continue
        else:
            seenNonBlankLine = True
        if redactPII:
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
    if settings.individualFiles:
        if output_path is None:
            raise ValueError('An output path is required when using individual files.')
        output_dir = output_path
        os.makedirs(output_dir, exist_ok=True)

    file_data, boarddict = load_data(input_path, logger)
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
            boarddict,
            settings.noHeader,
            settings.verbose,
            progress_bar,
        ):
            if (settings.private is True or parsed_message.is_private is False) and parsed_message.is_password is False:
                processed_buffer = process_message(
                    parsed_message.text,
                    settings.truncateSignatures,
                    settings.cutQuoting,
                    settings.binariesRemoval,
                    settings.redactPII,
                )
                if settings.individualFiles:
                    encodedBuffer = processed_buffer.encode('latin1')
                    assert output_dir is not None
                    with open(
                        os.path.join(output_dir, hashlib.sha1(encodedBuffer).hexdigest()),
                        'wb',
                    ) as f:
                        f.write(encodedBuffer)
                else:
                    collected_messages.append(
                        ProcessedMessage(
                            text=processed_buffer,
                            msgnum=parsed_message.msgnum,
                            refnum=parsed_message.refnum,
                            confnum=parsed_message.confnum,
                        )
                    )
    finally:
        if progress_bar is not None:
            progress_bar.close()

    if not settings.individualFiles:
        if settings.threaded:
            ordered_messages = _order_messages_by_thread(collected_messages)
        else:
            ordered_messages = collected_messages

        fullmessagebuffer = ''.join(message.text for message in ordered_messages)

        if output_path is None:
            print(fullmessagebuffer)
        else:
            with open(output_path, 'w', encoding='latin1') as f:
                f.write(fullmessagebuffer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_path', help='The messages.dat filename, or the QWK packet (default: messages.dat)', nargs='?', default='messages.dat')
    parser.add_argument('output_path', help='The output filename or directory. (default: print to console)', nargs='?')
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
    args = parser.parse_args()

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {args.loglevel}')
    logging.basicConfig(level=numeric_level)
    logger = logging.getLogger(__name__)

    settings = ProcessingSettings(
        verbose=args.verbose,
        private=args.private,
        noHeader=args.noheader,
        truncateSignatures=args.truncatesignatures,
        cutQuoting=args.cutquoting,
        individualFiles=args.individualfiles,
        threaded=args.threaded,
        binariesRemoval=args.binariesremoval,
        redactPII=args.redactpii,
        quiet=args.quiet,
    )

    try:
        process_file(args.input_path, args.output_path, settings, logger)
    except (
        MessagesDatFormatError,
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

    def visit(idx: int, path: set[int]) -> None:
        if idx in path:
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
