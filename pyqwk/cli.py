import argparse
import logging
import os
import sys
import datetime

from pyqwk.core import (
    LogFormatter,
    PROCESSING_EXCEPTIONS,
    ProcessingSettings,
    __version__,
    process_file,
    process_merged_files,
    process_multiple_files,
    show_info,
    show_stats,
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
            if ext == '.md' or ext == '.markdown':
                return 'markdown'
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


def _parse_cli_date(date_str: str | None, end_of_day: bool = False) -> datetime.datetime | None:
    """Parse a date string from the command line into a datetime object.

    Args:
        date_str: Date string in 'YYYY-MM-DD' format.
        end_of_day: If True, set the time to 23:59:59.999999.

    Returns:
        A datetime object or None.
    """
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt
    except ValueError:
        raise ValueError(f"The date format for '{date_str}' is invalid. Please use YYYY-MM-DD.")


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
        help='Where to save the results. Use a folder for multiple files. Defaults to screen.',
    )
    io_group.add_argument(
        '-i',
        '--individual-files',
        dest='individualfiles',
        help='Save each message in a separate file. Do not use this with --threaded.',
        action='store_true',
    )
    io_group.add_argument(
        '-E',
        '--encoding',
        help='Character encoding of the input file (default: cp437)',
        default='cp437',
    )

    content_group = parser.add_argument_group('Content Processing')
    content_group.add_argument(
        '--clean',
        help='Clean the message by removing signatures, old quotes, binary data, and ANSI colors.',
        action='store_true',
    )
    content_group.add_argument(
        '-t',
        '--truncate-signatures',
        dest='truncatesignatures',
        help="Stop reading the message when a signature (like '---') is found.",
        action='store_true',
    )
    content_group.add_argument(
        '-c',
        '--cut-quoting',
        dest='cutquoting',
        help="Remove text quoted from earlier messages (lines starting with '>').",
        action='store_true',
    )
    content_group.add_argument(
        '-b',
        '--binaries-removal',
        dest='binariesremoval',
        help='Remove binary attachments such as images or programs.',
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
        '-A',
        '--strip-ansi',
        dest='stripansi',
        help='Remove ANSI escape sequences (colors) from the message text.',
        action='store_true',
    )
    content_group.add_argument(
        '-p',
        '--private',
        help="Include messages marked as 'Private'.",
        action='store_true',
    )
    content_group.add_argument(
        '-H',
        '--headers-only',
        help='Only process message headers and skip the message body.',
        action='store_true',
    )

    format_group = parser.add_argument_group('Formatting & Structure')
    format_group.add_argument(
        '-F',
        '--format',
        help=(
            'Choose the output format (text, json, xml, html, markdown, csv, mbox, or sqlite). '
            'If you do not choose one, it is guessed from the output filename.'
        ),
        default=None,
        choices=['text', 'json', 'xml', 'html', 'markdown', 'csv', 'mbox', 'sqlite'],
    )
    format_group.add_argument(
        '--separator',
        choices=['auto', 'none', 'dashes', 'blank'],
        default='auto',
        help='Choose how to separate messages in the output file.',
    )
    format_group.add_argument(
        '-n',
        '--noheader',
        help='Do not include message information in the output text.',
        action='store_true',
    )
    format_group.add_argument(
        '-T',
        '--threaded',
        help='Group replies together into conversations. Do not use this with --individual-files.',
        action='store_true',
    )
    format_group.add_argument(
        '-m',
        '--merge',
        help='Merge multiple input archives into a single output. Enables cross-archive threading.',
        action='store_true',
    )

    control_group = parser.add_argument_group('Output Control')
    control_group.add_argument(
        '-v',
        '--verbose',
        help='Show more details like conference names and message numbers.',
        action='store_true',
    )
    control_group.add_argument(
        '-q',
        '--quiet',
        help='Hide the progress bar and other info.',
        action='store_true',
    )
    control_group.add_argument(
        '-l',
        '--loglevel',
        help='Choose how much detail to show in logs (DEBUG, INFO, WARNING, ERROR).',
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
        '-f',
        '--from',
        dest='authors',
        action='append',
        help='Filter messages by author name (case-insensitive substring match).',
    )
    filter_group.add_argument(
        '--to',
        dest='recipients',
        action='append',
        help='Filter messages by recipient name (case-insensitive substring match).',
    )
    filter_group.add_argument(
        '-s',
        '--subject',
        dest='subjects',
        action='append',
        help='Filter messages by subject line (case-insensitive substring match).',
    )
    filter_group.add_argument(
        '-S',
        '--search',
        dest='search_term',
        help='Search for a keyword in author, subject, and message body.',
    )
    filter_group.add_argument(
        '--after',
        help='Filter messages dated on or after this date (format: YYYY-MM-DD).',
        default=None,
    )
    filter_group.add_argument(
        '--before',
        help='Filter messages dated on or before this date (format: YYYY-MM-DD).',
        default=None,
    )
    filter_group.add_argument(
        '-L',
        '--limit',
        help='Stop after processing this many messages.',
        type=int,
        default=None,
    )
    filter_group.add_argument(
        '-u',
        '--unique',
        help='Only include unique messages (removes duplicates when merging archives).',
        action='store_true',
    )

    parser.add_argument(
        '-I',
        '--info',
        action='store_true',
        help='Show a summary of the QWK archive and exit. Use --format json for JSON output.',
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show detailed statistics about the messages and exit. Use --format json for JSON output.',
    )
    parser.add_argument(
        '-V',
        '--version',
        action='version',
        version=f"%(prog)s {__version__}",
        help='Show the version number and exit.',
    )
    args = parser.parse_args()

    if args.threaded and args.individualfiles:
        parser.error("You cannot use --threaded and --individual-files at the same time.")

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"'{args.loglevel}' is not a valid log level.")

    use_colors = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter(use_colors=use_colors))
    logging.basicConfig(level=numeric_level, handlers=[handler])

    logger = logging.getLogger(__name__)

    has_directory_input = any(os.path.isdir(p) for p in args.input_paths)
    input_paths = _expand_directories(args.input_paths)
    output_path = args.output_path

    if not input_paths:
        logger.error("No valid QWK files were found in the paths you provided.")
        sys.exit(1)

    if args.info:
        output_mode = 'stdout'
        resolved_output_path = None
    elif args.individualfiles:
        if output_path is None:
            parser.error("You must provide an output folder when saving messages as individual files.")
        if os.path.exists(output_path) and not os.path.isdir(output_path):
            parser.error("The output path must be a folder when saving messages as individual files.")
        output_mode = 'file'
        resolved_output_path = output_path
    elif args.merge:
        output_mode = 'stdout' if not output_path else 'file'
        resolved_output_path = output_path
    elif len(input_paths) > 1 or has_directory_input:
        if not output_path:
            parser.error("You must provide an output folder when processing more than one file.")
        output_mode = 'file'
        resolved_output_path = output_path
    else:
        output_mode = 'stdout' if not output_path else 'file'
        resolved_output_path = output_path

    output_format = _resolve_output_format(args.format, output_path, output_mode)

    try:
        after_date = _parse_cli_date(args.after)
        before_date = _parse_cli_date(args.before, end_of_day=True)
    except ValueError as e:
        parser.error(str(e))

    settings = ProcessingSettings(
        verbose=args.verbose,
        private=args.private,
        no_header=args.noheader,
        truncate_signatures=args.truncatesignatures or args.clean,
        cut_quoting=args.cutquoting or args.clean,
        individual_files=args.individualfiles,
        threaded=args.threaded,
        merge=args.merge,
        binaries_removal=args.binariesremoval or args.clean,
        redact_pii=args.redactpii,
        strip_ansi=args.stripansi or args.clean,
        quiet=args.quiet,
        headers_only=args.headers_only,
        unique=args.unique,
        format=output_format,
        separator=args.separator,
        output_mode=output_mode,
        output_path=resolved_output_path,
        encoding=args.encoding,
        conferences=args.conferences,
        authors=args.authors,
        recipients=args.recipients,
        subjects=args.subjects,
        search_term=args.search_term,
        after=after_date,
        before=before_date,
        limit=args.limit,
    )

    if args.info:
        show_info(input_paths, settings, logger)
        sys.exit(0)

    if args.stats:
        show_stats(input_paths, settings, logger)
        sys.exit(0)

    if args.merge:
        try:
            process_merged_files(input_paths, settings, logger)
        except PROCESSING_EXCEPTIONS as error:
            logger.error(error)
            sys.exit(1)
    elif len(input_paths) > 1 or has_directory_input:
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
