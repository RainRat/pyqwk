import argparse
import logging
import os
import sys

from pyqwk.core import (
    LogFormatter,
    PROCESSING_EXCEPTIONS,
    ProcessingSettings,
    __version__,
    process_file,
    process_multiple_files,
    show_info,
)


def _resolve_output_format(
    output_format: str | None,
    output_path: str | None,
    output_mode: str,
) -> str:
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
            if ext == '.sqlite' or ext == '.db':
                return 'sqlite'
        return 'text'
    return output_format


def _expand_directories(paths: list[str]) -> list[str]:
    """Recursively find supported QWK files in directories."""
    expanded_paths = []
    for path in paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    lower_file = file.lower()
                    if lower_file.endswith(('.qwk', '.zip', '.rep')) or lower_file == 'messages.dat':
                        expanded_paths.append(os.path.join(root, file))
        else:
            expanded_paths.append(path)
    return sorted(expanded_paths)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'input_paths',
        help='The QWK archive files, messages.dat files, or directories you want to read.',
        nargs='+',
    )

    io_group = parser.add_argument_group('Input & Output')
    io_group.add_argument(
        '-o',
        '--output',
        dest='output_path',
        help='Where to save the results (filename or folder). Defaults to showing on screen.',
    )
    io_group.add_argument(
        '-i',
        '--individual-files',
        dest='individualfiles',
        help='Save each message as its own separate file. (Cannot use with --threaded).',
        action='store_true',
    )
    io_group.add_argument(
        '--encoding',
        help='Character encoding of the input file (default: cp437)',
        default='cp437',
    )

    content_group = parser.add_argument_group('Content Processing')
    content_group.add_argument(
        '--clean',
        help='Enable all content cleaning options: truncate signatures, cut quoting, and remove binaries.',
        action='store_true',
    )
    content_group.add_argument(
        '-t',
        '--truncate-signatures',
        dest='truncatesignatures',
        help="Stop reading when a common signature (like '---') is found.",
        action='store_true',
    )
    content_group.add_argument(
        '-c',
        '--cut-quoting',
        dest='cutquoting',
        help="Remove text quoted from previous messages (lines starting with '>').",
        action='store_true',
    )
    content_group.add_argument(
        '-b',
        '--binaries-removal',
        dest='binariesremoval',
        help='Remove binary data attachments (like images or programs).',
        action='store_true',
    )
    content_group.add_argument(
        '-r',
        '--redact-pii',
        dest='redactpii',
        help='Hide personal info like email addresses and phone numbers.',
        action='store_true',
    )
    content_group.add_argument(
        '-p',
        '--private',
        help="Include messages marked as 'Private'.",
        action='store_true',
    )

    format_group = parser.add_argument_group('Formatting & Structure')
    format_group.add_argument(
        '--format',
        help=(
            'Choose the output format: text, json, xml, html, csv, mbox, or sqlite. '
            '(Default: auto-detected from output filename, or text)'
        ),
        default=None,
        choices=['text', 'json', 'xml', 'html', 'csv', 'mbox', 'sqlite'],
    )
    format_group.add_argument(
        '--separator',
        choices=['auto', 'none', 'dashes', 'blank'],
        default='auto',
        help='Choose how to separate messages in the output.',
    )
    format_group.add_argument(
        '-n',
        '--noheader',
        help='Do not include the message info (header) in the body text.',
        action='store_true',
    )
    format_group.add_argument(
        '-T',
        '--threaded',
        help='Group replies with their original messages. (Cannot use with --individual-files).',
        action='store_true',
    )

    control_group = parser.add_argument_group('Output Control')
    control_group.add_argument(
        '-v',
        '--verbose',
        help='Show extra details like conference names and message numbers.',
        action='store_true',
    )
    control_group.add_argument(
        '-q',
        '--quiet',
        help='Do not show the progress bar.',
        action='store_true',
    )
    control_group.add_argument(
        '-l',
        '--loglevel',
        help='Control how much technical detail to display (DEBUG, INFO, WARNING, ERROR).',
        default='INFO',
    )

    filter_group = parser.add_argument_group('Filtering Options')
    filter_group.add_argument(
        '-C',
        '--conference',
        dest='conferences',
        action='append',
        help='Filter messages by conference name or number (can be used multiple times).',
    )
    filter_group.add_argument(
        '--from',
        dest='authors',
        action='append',
        help='Filter messages by author name (case-insensitive substring match).',
    )
    filter_group.add_argument(
        '--subject',
        dest='subjects',
        action='append',
        help='Filter messages by subject line (case-insensitive substring match).',
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='Show a summary of the QWK packet (conferences, message counts) and exit.',
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

    use_colors = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter(use_colors=use_colors))
    logging.basicConfig(level=numeric_level, handlers=[handler])

    logger = logging.getLogger(__name__)

    has_directory_input = any(os.path.isdir(p) for p in args.input_paths)
    input_paths = _expand_directories(args.input_paths)
    output_path = args.output_path

    if not input_paths:
        logger.error("No valid QWK files found in the provided paths.")
        sys.exit(1)

    if args.individualfiles:
        if output_path is None:
            parser.error('Output folder is required when writing individual files.')
        if os.path.exists(output_path) and not os.path.isdir(output_path):
            parser.error('Output path must be a folder when writing individual files.')
        output_mode = 'file'
        resolved_output_path = output_path
    elif len(input_paths) > 1 or has_directory_input:
        if not output_path:
            parser.error('Output folder is required when processing multiple files.')
        output_mode = 'file'
        resolved_output_path = output_path
    else:
        output_mode = 'stdout' if not output_path else 'file'
        resolved_output_path = output_path

    output_format = _resolve_output_format(args.format, output_path, output_mode)

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
        format=output_format,
        separator=args.separator,
        output_mode=output_mode,
        output_path=resolved_output_path,
        encoding=args.encoding,
        conferences=args.conferences,
        authors=args.authors,
        subjects=args.subjects,
    )

    if args.info:
        show_info(input_paths, settings, logger)
        sys.exit(0)

    if len(input_paths) > 1 or has_directory_input:
        had_errors = process_multiple_files(input_paths, output_path, settings, logger)
        if had_errors:
            sys.exit(1)
    else:
        try:
            process_file(input_paths[0], settings, logger)
        except PROCESSING_EXCEPTIONS as error:
            logger.error(error)
            sys.exit(1)


if __name__ == '__main__':
    main()
