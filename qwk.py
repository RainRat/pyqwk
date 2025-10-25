import sys
import argparse
import zipfile
import struct
import re
import hashlib
import os
import logging

BLOCK_SIZE = 128
MESSAGES_FILENAME = 'messages.dat'
CONTROL_FILENAME = 'control.dat'

QUOTE_HEADER_PATTERNS = [
    r".*(replied|'s comment|said|wrote|was talking|yelled|writes|mentioned|spake thusly|carried on|babbled on|spoke|wrote a message)( in a message| the following| this)? to ",
    r"^\s*( -=>|\*\*\*|Yo!)?\s*(Quoting|Answering msg from|In a msg on|Reply|QUOTING|In a message originally|Quoted from a message|In a message).* to "
]
QUOTE_PATTERN = r'^\s*[A-Za-z\-\=]{0,4}\s?(>|\xb3|\||\})'
UUE_PATTERN = r'^begin\s\d{3}\s'
UUE_DATA_PATTERN = r'^M[\x21-\x60]{60}$'
UUE_LOOSE_PATTERN = r'[\x21-\x4c][\x21-\x60]{4,60}$'
BASE64_PATTERN = r'^[A-Za-z0-9+/=]{60,}$'
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
PHONE_PATTERN = r'\b(?:\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})\b'


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
                    logger.error(f"Error: '{MESSAGES_FILENAME}' not found in the zip archive {input_path}.")
                    sys.exit(1)
                with myzip.open(messagesname) as f:
                    file_data = bytearray(f.read())
                if controlname:
                    with myzip.open(controlname) as f:
                        controldata = f.read().splitlines()
                    numlines = int(controldata[10])
                    for i in range(0, numlines):
                        boarddict[int(controldata[i * 2 + 11])] = controldata[i * 2 + 12].decode('latin1')
        except zipfile.BadZipFile:
            logger.error("Error: The provided file is not a valid zip file.")
            sys.exit(1)
    else:
        try:
            with open(input_path, 'rb') as f:
                file_data = bytearray(f.read())
        except IOError:
            logger.error(f"Error reading {input_path}")
            sys.exit(1)
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
            (status, msgnum, msgdate, msgtime, msgto, msgfrom, msgsubject, msgpassword, refnum, numblocks,
             msgflag, confnum, lognum, nettag) = struct.unpack('<c7s8s5s25s25s25s12s8s6scHHc', record)
            messageType = status.decode('latin1')
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
                conf_name = boarddict[confnum]
            except KeyError:
                conf_name = str(confnum)
                not_found_flag = True

            messagebuffer = ''
            if not noHeader:
                messagebuffer += ("-" * 80) + '\r\n'
                if verbose is True or not_found_flag is False:
                    messagebuffer += ('Conference: ' + str(conf_name) + '\r\n')
                if verbose is True:
                    messagebuffer += ('Message number: ' + msgnum.decode('latin1') + (' ' * 20))
                messagebuffer += ('Date: ' + msgdate.decode('latin1') + ' ' + msgtime.decode('latin1') + '\r\n')
                messagebuffer += ('From: ' + msgfrom.decode('latin1') + '\r\n')
                messagebuffer += ('To: ' + msgto.decode('latin1') + '\r\n')
                messagebuffer += ('Subject: ' + msgsubject.decode('latin1') + '\r\n')
                if verbose is True:
                    messagebuffer += ('Reference number: ' + refnum.decode('latin1') + '\r\n')
                messagebuffer += '\r\n'
            tempblocks = numblocks.decode('latin1').strip()
            intBlocks = int(tempblocks) - 1
        else:
            temprecord = record.decode('latin1').replace('\xe3', '\r\n')
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
                line == "---" or line.startswith(" * ") or line.startswith("--- ") or line == "___"
                or line == "--" or line.startswith("-- ") or line.startswith("___ ")
                or line.startswith("... ") or line.startswith("-+- ")
                or line == "-----BEGIN PGP SIGNATURE-----" or line.startswith("~~~ ")
                or line == "___--BEGIN PGP SIGNATURE-----" or line.startswith(" \xfe ")
                or line == "-----BEGIN GPG SIGNATURE-----" or line.startswith(" *** ")):
            break
        if cutQuoting:
            if seenNonBlankLine is False:
                if any(re.match(pattern, line) for pattern in QUOTE_HEADER_PATTERNS):
                    continue
            if re.match(QUOTE_PATTERN, line):
                continue
            elif j > 0 and j < (len(lines) - 1) \
                    and re.match(QUOTE_PATTERN, lines[j - 1]) \
                    and re.match(QUOTE_PATTERN, lines[j + 1]):
                continue
        if binariesRemoval:
            if (re.match(BASE64_PATTERN, line)
                    or re.match(UUE_DATA_PATTERN, line)
                    or re.match(UUE_PATTERN, line)):
                continue
            if re.match(UUE_LOOSE_PATTERN, line):
                prevLine = lines[max(0, j - 1)]
                if re.match(UUE_DATA_PATTERN, prevLine) or re.match(UUE_PATTERN, prevLine):
                    continue
        if seenNonBlankLine is False and line.strip() == '':
            continue
        else:
            seenNonBlankLine = True
        if redactPII:
            line = re.sub(EMAIL_PATTERN, '[EMAIL]', line)
            line = re.sub(PHONE_PATTERN, '[PHONE]', line)
        new_lines.append(line.strip('\r\n'))

    return '\r\n'.join(new_lines) + '\r\n'


def process_file(input_path, output_path, verbose, private, noHeader, truncateSignatures,
                 cutQuoting, individualFiles, binariesRemoval, redactPII, logger):

    if individualFiles:
        if not os.path.isdir(output_path):
            os.mkdir(output_path)

    file_data, boarddict = load_data(input_path, logger)
    fullmessagebuffer = ''

    try:
        for messagebuffer, isPrivate, isPassword in parse_messages(file_data, boarddict, noHeader, verbose):
            if (private is True or isPrivate is False) and isPassword is False:
                processed_buffer = process_message(messagebuffer, truncateSignatures, cutQuoting, binariesRemoval, redactPII)
                if individualFiles:
                    encodedBuffer = processed_buffer.encode('latin1')
                    with open(os.path.join(output_path, hashlib.sha1(encodedBuffer).hexdigest()), 'wb') as f:
                        f.write(encodedBuffer)
                else:
                    fullmessagebuffer += processed_buffer
    except MessagesDatFormatError:
        logger.error("Error: Input file is not a messages.dat file. Missing 'Produced ' header.")
        sys.exit(1)
    except InvalidMessageTypeError as error:
        logger.error(f"Error: Invalid message type '{error.message_type}'. File may be corrupt.")
        sys.exit(1)

    if not individualFiles:
        if output_path is None:
            print(fullmessagebuffer)
        else:
            with open(output_path, 'w', encoding='latin1') as f:
                f.write(fullmessagebuffer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_path', help='The messages.dat filename, or the QWK packet (default: messages.dat)', nargs='?', default='messages.dat')
    parser.add_argument('output_path', help='The output filename or directory. (default: print to console)', nargs='?')
    parser.add_argument('-v', '--verbose', help='verbose output. export message id fields that may not be relevant', action='store_true')
    parser.add_argument('-p', '--private', help='export messages marked private', action='store_true')
    parser.add_argument('-n', '--noheader', help='leave out message header', action='store_true')
    parser.add_argument('-t', '--truncatesignatures', help='truncate at signatures (everything after a line that consists only of "---" or starts with " * ")', action='store_true')
    parser.add_argument('-c', '--cutquoting', help='delete quoted text (that uses ">" as quoting character)', action='store_true')
    parser.add_argument('-i', '--individualfiles', help='output individual files (output_path will be treated as a directory)', action='store_true')
    parser.add_argument('-b', '--binariesremoval', help='delete binaries (currently removes uuencoded and Base64-encoded blocks)', action='store_true')
    parser.add_argument('-r', '--redactpii', help='redact PII (currently e-mail addresses and phone numbers)', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    process_file(args.input_path, args.output_path, args.verbose, args.private, args.noheader, args.truncatesignatures,
            args.cutquoting, args.individualfiles, args.binariesremoval, args.redactpii, logger)


if __name__ == '__main__':
    main()
