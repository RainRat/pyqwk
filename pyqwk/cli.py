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
    resolve_output_format,
    show_info,
    show_stats,
)


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
    parser = argparse.ArgumentParser(
        description="A tool to read and convert old Bulletin Board System (BBS) message packets (QWK format) into modern formats like Text, HTML, or JSON."
    )
    parser.add_argument(
        'input_paths',
        help='The archives, message files, or folders you want to read.',
        nargs='+',
    )

    io_group = parser.add_argument_group('Input & Output')
    io_group.add_argument(
        '-o',
        '--output',
        dest='output_path',
        help='Save results to this file or folder. Prints to the screen if not set.',
    )
    io_group.add_argument(
        '-i',
        '--individual-files',
        dest='individualfiles',
        help='Save each message as its own file. HTML and Markdown exports will also get a clickable index file. You cannot use this with --threaded.',
        action='store_true',
    )
    io_group.add_argument(
        '--organize',
        help='Organize individual files into folders by conference.',
        action='store_true',
    )
    io_group.add_argument(
        '-E',
        '--encoding',
        help='The text format of the input file (default is cp437).',
        default='cp437',
    )

    content_group = parser.add_argument_group('Content Processing')
    content_group.add_argument(
        '--clean',
        help='Automatically remove signatures, old quotes, attachments, and color codes.',
        action='store_true',
    )
    content_group.add_argument(
        '-t',
        '--truncate-signatures',
        dest='truncatesignatures',
        help="Stop reading a message when a signature (like '---') is found.",
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
        help='Remove attachments such as images or programs encoded in the text.',
        action='store_true',
    )
    content_group.add_argument(
        '-x',
        '--extract-attachments',
        dest='extractattachments',
        help='Extract attachments (UUE, yEnc, Base64) to an attachments/ folder.',
        action='store_true',
    )
    content_group.add_argument(
        '-r',
        '--redact-pii',
        dest='redactpii',
        help='Hide personal information like email addresses and phone numbers.',
        action='store_true',
    )
    content_group.add_argument(
        '-A',
        '--strip-ansi',
        dest='stripansi',
        help='Remove color codes and other formatting symbols from the message text.',
        action='store_true',
    )
    content_group.add_argument(
        '-p',
        '--private',
        help="Include private messages.",
        action='store_true',
    )
    content_group.add_argument(
        '-H',
        '--headers-only',
        help='Show only the message headers and hide the message text.',
        action='store_true',
    )

    format_group = parser.add_argument_group('Formatting & Structure')
    format_group.add_argument(
        '-F',
        '--format',
        help=(
            'Choose the output format (text, html, json, etc.). '
            'If you leave this out, it is determined by the file extension of the output path.'
        ),
        default=None,
        choices=['text', 'json', 'xml', 'html', 'markdown', 'csv', 'mbox', 'eml', 'sqlite'],
    )
    format_group.add_argument(
        '-j',
        '--json',
        action='store_const',
        const='json',
        dest='format',
        help='A shortcut for --format json.',
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
        help='Group replies into conversations. This cannot be used with the --individual-files option.',
        action='store_true',
    )
    format_group.add_argument(
        '-1',
        '--oneline',
        help='Show each message as a single line summary (Conference, Date, From, Subject).',
        action='store_true',
    )
    format_group.add_argument(
        '--toc',
        dest='include_toc',
        help='Include a table of contents and archive summary in the output (supported for Text, HTML, and Markdown merged exports).',
        action='store_true',
    )
    format_group.add_argument(
        '-m',
        '--merge',
        help='Combine multiple archives into one file. This helps you follow conversations across different files.',
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
        help='Hide the progress bar and other information.',
        action='store_true',
    )
    control_group.add_argument(
        '-d',
        '--dry-run',
        action='store_true',
        help='Do everything except actually writing files. Useful for testing filters.',
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
        help='Only show messages from this author (you can use part of the name).',
    )
    filter_group.add_argument(
        '--to',
        dest='recipients',
        action='append',
        help='Only show messages to this recipient (you can use part of the name).',
    )
    filter_group.add_argument(
        '-s',
        '--subject',
        dest='subjects',
        action='append',
        help='Only show messages with this word in the subject line.',
    )
    filter_group.add_argument(
        '-S',
        '--search',
        dest='search_term',
        help='Search for a keyword in author, subject, and message body.',
    )
    filter_group.add_argument(
        '--regex',
        action='store_true',
        help='Use regular expressions for searching and filtering.',
    )
    filter_group.add_argument(
        '--after',
        help='Only show messages from this date or later (YYYY-MM-DD).',
        default=None,
    )
    filter_group.add_argument(
        '-K',
        '--skip',
        metavar='NUM',
        help='Skip this many matching messages.',
        type=int,
        default=None,
    )
    filter_group.add_argument(
        '--before',
        help='Only show messages from this date or earlier (YYYY-MM-DD).',
        default=None,
    )
    filter_group.add_argument(
        '-L',
        '--limit',
        metavar='NUM',
        help='Process only this many matching messages.',
        type=int,
        default=None,
    )
    filter_group.add_argument(
        '-u',
        '--unique',
        help='Remove duplicate messages when merging archives.',
        action='store_true',
    )
    filter_group.add_argument(
        '--sort',
        help='Sort results by field (date, author, to, subject, num, or conference).',
        choices=['date', 'author', 'to', 'subject', 'num', 'conference'],
        default=None,
    )
    filter_group.add_argument(
        '--reverse',
        help='Reverse the order of the results.',
        action='store_true',
    )
    filter_group.add_argument(
        '--has-attachments',
        help='Only show messages that contain attachments (UUE, yEnc, Base64).',
        action='store_true',
    )

    parser.add_argument(
        '-I',
        '--info',
        action='store_true',
        help='Show a summary of the archive and exit. Use --format json for JSON output.',
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show detailed statistics about the messages and exit. This respects your current filters. Use --format json for JSON output.',
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

    if args.oneline and args.individualfiles:
        parser.error("You cannot use --oneline and --individual-files at the same time.")

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

    output_format = resolve_output_format(args.format, output_path, output_mode)

    if args.threaded and output_format == 'eml':
        parser.error("You cannot use --threaded with EML format.")

    # Default to individual files for EML format if an output path is provided
    if output_format == 'eml' and not args.individualfiles and output_path:
        args.individualfiles = True
        # If the user provided an output path that looks like a file (has an extension),
        # but EML forces individual files (directory), it's confusing.
        # However, the core logic requires output_path to be a directory for individual files.
        if output_path and os.path.exists(output_path) and not os.path.isdir(output_path):
            parser.error("The output path must be a folder when saving messages as individual EML files.")
        
        output_mode = 'file'
        resolved_output_path = output_path

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
        organize=args.organize,
        include_toc=args.include_toc,
        extract_attachments=args.extractattachments,
        format=output_format,
        separator=args.separator,
        output_mode=output_mode,
        output_path=resolved_output_path,
        encoding=args.encoding,
        regex=args.regex,
        conferences=args.conferences,
        authors=args.authors,
        recipients=args.recipients,
        subjects=args.subjects,
        search_term=args.search_term,
        after=after_date,
        before=before_date,
        limit=args.limit,
        skip=args.skip,
        sort=args.sort,
        reverse=args.reverse,
        dry_run=args.dry_run,
        oneline=args.oneline,
        has_attachments=args.has_attachments,
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
