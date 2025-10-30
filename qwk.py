import sys
import argparse
import zipfile
import struct
import re
import hashlib
import os
import logging
from dataclasses import dataclass

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
RE_PHONE_PATTERN = re.compile(r'\b(?:\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})\b')

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


@dataclass
class ProcessingSettings:
    verbose: bool
    private: bool
    noHeader: bool
    truncateSignatures: bool
    cutQuoting: bool
    individualFiles: bool
    binariesRemoval: bool
    redactPII: bool


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


def load_data(input_path, logger):
    boarddict = {}
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
                    numlines = int(controldata[10])
                    for i in range(0, numlines):
                        boarddict[int(controldata[i * 2 + 11])] = controldata[i * 2 + 12].decode('latin1')
        except zipfile.BadZipFile as error:
            raise zipfile.BadZipFile("Error: The provided file is not a valid zip file.") from error
    else:
        try:
            with open(input_path, 'rb') as f:
                file_data = bytearray(f.read())
        except IOError as error:
            raise IOError(f"Error reading {input_path}") from error
    return file_data, boarddict


def parse_messages(file_data, boarddict, noHeader, verbose):
    intBlocks = 0
    messagebuffer = ''
    isPrivate = True
    isPassword = False
    for i in range(0, len(file_data), BLOCK_SIZE):
        record = file_data[i:i + BLOCK_SIZE]
        if i == 0:
            if record[0:9] != b'Produced ':
                raise MessagesDatFormatError
            continue
        if intBlocks == 0:
            header_data = struct.unpack('<c7s8s5s25s25s25s12s8s6scHHc', record)
            header = MessageHeader(*header_data)
            messageType = header.status.decode('latin1')
            isPassword = False
            isPrivate = True
            if messageType in ['+', '*', '~', '`']:
                pass
            elif messageType in ['%', '^', '!', '#', '$']:
                isPassword = True
            elif messageType in [' ', '-']:
                isPrivate = False
            else:
                raise InvalidMessageTypeError(messageType)

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
                yield messagebuffer, isPrivate, isPassword


def process_message(messagebuffer, truncateSignatures, cutQuoting, binariesRemoval, redactPII):
    lines = messagebuffer.splitlines()

    new_lines = []
    seenNonBlankLine = False
    for j, line in enumerate(lines):
        if truncateSignatures and (
            line in SIGNATURE_PATTERNS_EXACT
            or any(line.startswith(prefix) for prefix in SIGNATURE_PATTERNS_STARTSWITH)
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


def process_file(input_path, output_path, settings: ProcessingSettings, logger):

    if settings.individualFiles:
        os.makedirs(output_path, exist_ok=True)

    file_data, boarddict = load_data(input_path, logger)
    fullmessagebuffer = ''

    for messagebuffer, isPrivate, isPassword in parse_messages(
        file_data,
        boarddict,
        settings.noHeader,
        settings.verbose,
    ):
        if (settings.private is True or isPrivate is False) and isPassword is False:
            processed_buffer = process_message(
                messagebuffer,
                settings.truncateSignatures,
                settings.cutQuoting,
                settings.binariesRemoval,
                settings.redactPII,
            )
            if settings.individualFiles:
                encodedBuffer = processed_buffer.encode('latin1')
                with open(os.path.join(output_path, hashlib.sha1(encodedBuffer).hexdigest()), 'wb') as f:
                    f.write(encodedBuffer)
            else:
                fullmessagebuffer += processed_buffer

    if not settings.individualFiles:
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
    parser.add_argument('-t', '--truncatesignatures', help='truncate at signatures (everything after a line that consists only of "---" or starts with " * ")', action='store_true')
    parser.add_argument('-c', '--cutquoting', help='delete quoted text (that uses ">" as quoting character)', action='store_true')
    parser.add_argument('-i', '--individualfiles', help='output individual files (output_path will be treated as a directory)', action='store_true')
    parser.add_argument('-b', '--binariesremoval', help='delete binaries (currently removes uuencoded and Base64-encoded blocks)', action='store_true')
    parser.add_argument('-r', '--redactpii', help='redact PII (currently e-mail addresses and phone numbers)', action='store_true')
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
        binariesRemoval=args.binariesremoval,
        redactPII=args.redactpii,
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


if __name__ == '__main__':
    main()
