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
    expand_paths,
    process_merged_files,
    process_multiple_files,
    organize_by_bbs,
    resolve_output_format,
    show_info,
    show_stats,
)


def _parse_msgnum_ranges(msgnum_str: str | None) -> set[int] | None:
    """Parse a message number filter string like '100,200-300' into a set of integers."""
    if not msgnum_str:
        return None

    msgnums = set()
    for part in msgnum_str.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                msgnums.update(range(start, end + 1))
            except ValueError:
                raise ValueError(f"Invalid message number range: '{part}'")
        else:
            try:
                msgnums.add(int(part))
            except ValueError:
                raise ValueError(f"Invalid message number: '{part}'")
    return msgnums


def _parse_cli_date(
    date_str: str | None, end_of_day: bool = False
) -> datetime.datetime | None:
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
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt
    except ValueError:
        raise ValueError(
            f"The date format for '{date_str}' is invalid. Please use YYYY-MM-DD."
        )


def main() -> None:
    template_variables = (
        "template variables:\n"
        "  Basic Information:\n"
        "    {author}, {to}, {subject}, {subject_clean}, {body}, {body_clean},\n"
        "    {confname}, {confnum}, {confname_or_num}, {msgnum}, {snippet},\n"
        "    {url_count}, {email_count}, {phone_count}, {my_name}\n"
        "  Dates & Times:\n"
        "    {date}, {time}, {year}, {month}, {day}, {hour}, {minute}, {second},\n"
        "    {iso_date}, {iso_time}\n"
        "  BBS & Source:\n"
        "    {bbs_name}, {bbs_id}, {source_file}\n"
        "  Technical Details:\n"
        "    {msgid}, {refnum}, {status}, {msgflag}, {is_private}, {is_reply},\n"
        "    {length}, {size}, {flags}, {indent}\n"
        "  Attachments:\n"
        "    {attachments}, {attachment_count}"
    )

    parser = argparse.ArgumentParser(
        description="Save BBS message archives in modern formats like HTML, Markdown, and SQLite.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"""
examples:
  # Show a one-line summary
  qwk archive.qwk --oneline

  # Save as an HTML file
  qwk archive.qwk --format html -o messages.html

  # Save as EML files
  qwk archive.qwk --format eml -o ./output/

  # Search for a keyword and show headers
  qwk archive.qwk --search "vintage computing" --headers-only

  # Extract attachments
  qwk archive.qwk --extract-attachments

  # Show statistics
  qwk archive.qwk --stats

  # Save statistics as an HTML report
  qwk archive.qwk --stats --format html -o stats.html

  # Save archive info as Markdown
  qwk archive.qwk --info --format markdown -o info.md

{template_variables}
""",
    )
    parser.add_argument(
        "input_paths",
        help=(
            "Path to archives, folders, or compressed files (ZIP/TAR).\n"
            "Supports QWK, JSON, SQLite, EML, and many other formats.\n"
            "Multiple archives are automatically merged."
        ),
        nargs="+",
    )

    io_group = parser.add_argument_group("Input & Output")
    io_group.add_argument(
        "-o",
        "--output",
        dest="output_path",
        help="Save results to a file or folder. Messages print to the screen if you omit this.",
    )
    io_group.add_argument(
        "-i",
        "--individual-files",
        dest="individualfiles",
        help="Save each message as a separate file. This also creates a browsable index for HTML and Markdown.",
        action="store_true",
    )
    io_group.add_argument(
        "--organize",
        help="Organize individual files into subfolders by conference.",
        action="store_true",
    )
    io_group.add_argument(
        "--organize-by-date",
        help="Organize individual files into subfolders by date (YYYY/MM).",
        action="store_true",
    )
    io_group.add_argument(
        "--organize-by-bbs",
        dest="organize_by_bbs",
        help="Organize archives into folders named after the BBS. If used with -o, organizes the export folder instead.",
        action="store_true",
    )
    io_group.add_argument(
        "--organize-by-author",
        help="Organize individual files into subfolders by author name.",
        action="store_true",
    )
    io_group.add_argument(
        "--organize-by-to",
        help="Organize individual files into subfolders by recipient name.",
        action="store_true",
    )
    io_group.add_argument(
        "--organize-by-subject",
        help="Organize individual files into subfolders by message subject.",
        action="store_true",
    )
    io_group.add_argument(
        "--filename-pattern",
        help="Set a pattern for naming individual files (e.g., '{date}_{author}_{subject}').\nSee template variables below.",
    )
    io_group.add_argument(
        "--organize-pattern",
        help="Set a pattern for organizing individual files into folders (e.g., '{year}/{month}/{author}').\nSee template variables below.",
    )
    io_group.add_argument(
        "-E",
        "--encoding",
        help="Set the text encoding (default is 'cp437'). Use this if text looks incorrect.",
        default="cp437",
    )

    content_group = parser.add_argument_group("Content Processing")
    content_group.add_argument(
        "--clean",
        help="Remove signatures, old quotes, attachments, and color codes.",
        action="store_true",
    )
    content_group.add_argument(
        "-t",
        "--truncate-signatures",
        dest="truncatesignatures",
        help="Stop reading a message when a signature is found.",
        action="store_true",
    )
    content_group.add_argument(
        "-c",
        "--cut-quoting",
        dest="cutquoting",
        help="Remove quoted text from earlier messages.",
        action="store_true",
    )
    content_group.add_argument(
        "-b",
        "--binaries-removal",
        dest="binariesremoval",
        help="Remove attachments like images or programs from the message text.",
        action="store_true",
    )
    content_group.add_argument(
        "-x",
        "--extract-attachments",
        dest="extractattachments",
        help="Extract attachments (UUE, yEnc, Base64) to an attachments/ folder.",
        action="store_true",
    )
    content_group.add_argument(
        "--embed-attachments",
        dest="embed_attachments",
        help="Embed image attachments directly into HTML output as Base64 data URIs.",
        action="store_true",
    )
    content_group.add_argument(
        "--organize-attachments",
        dest="organize_attachments",
        help="Organize extracted attachments into subfolders using the same rules as messages.",
        action="store_true",
    )
    content_group.add_argument(
        "-r",
        "--redact-pii",
        dest="redactpii",
        help="Hide personal info like email addresses and phone numbers.",
        action="store_true",
    )
    content_group.add_argument(
        "-A",
        "--strip-ansi",
        dest="stripansi",
        help="Remove color codes and other formatting symbols.",
        action="store_true",
    )
    content_group.add_argument(
        "-p",
        "--private",
        help="Include private messages.",
        action="store_true",
    )
    content_group.add_argument(
        "-H",
        "--headers-only",
        help="Show only the message details (metadata).",
        action="store_true",
    )

    format_group = parser.add_argument_group("Formatting & Structure")
    format_group.add_argument(
        "-F",
        "--format",
        help="Set the output format. If omitted, the format is chosen based on the file extension.",
        default=None,
        choices=[
            "text",
            "json",
            "jsonl",
            "xml",
            "rss",
            "html",
            "markdown",
            "csv",
            "mbox",
            "eml",
            "maildir",
            "sqlite",
        ],
    )
    format_group.add_argument(
        "-j",
        "--json",
        action="store_const",
        const="json",
        dest="format",
        help="A shortcut for --format json.",
    )
    format_group.add_argument(
        "-J",
        "--jsonl",
        action="store_const",
        const="jsonl",
        dest="format",
        help="A shortcut for --format jsonl.",
    )
    format_group.add_argument(
        "--separator",
        choices=["auto", "none", "dashes", "blank"],
        default="auto",
        help="Set how to separate messages in the output file.",
    )
    format_group.add_argument(
        "-n",
        "--noheader",
        help="Hide message information in the output text.",
        action="store_true",
    )
    format_group.add_argument(
        "-T",
        "--threaded",
        help="Group replies into conversations. This cannot be used with the --individual-files option.",
        action="store_true",
    )
    format_group.add_argument(
        "-1",
        "--oneline",
        help="Show a one-line summary (MsgNum, Conf, Date, From, To, Flags, Subject).",
        action="store_true",
    )
    format_group.add_argument(
        "--oneline-pattern",
        help="Set a custom pattern for one-line summaries (e.g., '[{confnum}] {author}: {subject}').\nSee template variables below.",
    )
    format_group.add_argument(
        "--toc",
        dest="include_toc",
        help="Add a table of contents and archive summary to the output.",
        action="store_true",
    )
    format_group.add_argument(
        "-m",
        "--merge",
        help="Combine multiple archives into one file. This helps you follow conversations across different files.",
        action="store_true",
    )

    control_group = parser.add_argument_group("Output Control")
    control_group.add_argument(
        "-v",
        "--verbose",
        help="Show more details like conference names and message numbers.",
        action="store_true",
    )
    control_group.add_argument(
        "-q",
        "--quiet",
        help="Hide the progress bar and other information.",
        action="store_true",
    )
    control_group.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Preview actions without writing files to disk. Useful for testing filters.",
    )
    control_group.add_argument(
        "-l",
        "--loglevel",
        help="Set the amount of detail shown in logs (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
        default="INFO",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    filter_group = parser.add_argument_group("Filtering Options")
    filter_group.add_argument(
        "-C",
        "--conference",
        dest="conferences",
        action="append",
        help="Show messages from a specific conference (name or number). Supports partial matches.",
    )
    filter_group.add_argument(
        "-B",
        "--bbs",
        dest="bbs_names",
        action="append",
        help="Show messages from a specific BBS (name or ID). Supports partial matches.",
    )
    filter_group.add_argument(
        "-f",
        "--from",
        dest="authors",
        action="append",
        help="Show messages from a specific author (supports partial matches).",
    )
    filter_group.add_argument(
        "--to",
        dest="recipients",
        action="append",
        help="Show messages to a specific recipient (supports partial matches).",
    )
    filter_group.add_argument(
        "-s",
        "--subject",
        dest="subjects",
        action="append",
        help="Show messages with a specific word in the subject line.",
    )
    filter_group.add_argument(
        "-S",
        "--search",
        dest="search_term",
        help=(
            "Search for keywords in common fields:\n"
            "Author, To, Subject, Body, Conference, BBS, BBS ID, Source File, and Attachments."
        ),
    )
    filter_group.add_argument(
        "--body",
        dest="body_search",
        help="Search for a specific keyword within the message body text.",
    )
    filter_group.add_argument(
        "-X",
        "--exclude",
        dest="exclude_search",
        help=(
            "Hide messages that match a specific keyword in any common field:\n"
            "Author, To, Subject, Body, Conference, BBS, BBS ID, Source File, and Attachments."
        ),
    )
    filter_group.add_argument(
        "--exclude-from",
        dest="exclude_authors",
        action="append",
        help="Hide messages from a specific author (supports partial matches).",
    )
    filter_group.add_argument(
        "--exclude-to",
        dest="exclude_recipients",
        action="append",
        help="Hide messages sent to a specific recipient (supports partial matches).",
    )
    filter_group.add_argument(
        "--exclude-subject",
        dest="exclude_subjects",
        action="append",
        help="Hide messages with a specific word in the subject line.",
    )
    filter_group.add_argument(
        "--exclude-conference",
        dest="exclude_conferences",
        action="append",
        help="Hide messages from a specific conference (name or number).",
    )
    filter_group.add_argument(
        "--exclude-bbs",
        dest="exclude_bbs_names",
        action="append",
        help="Hide messages from a specific BBS (name or ID).",
    )
    filter_group.add_argument(
        "--regex",
        action="store_true",
        help="Use regular expressions (advanced patterns) for searching and filtering.",
    )
    filter_group.add_argument(
        "--after",
        help="Show messages sent on or after this date (YYYY-MM-DD).",
        default=None,
    )
    filter_group.add_argument(
        "--min-length",
        help="Show messages with at least this many characters.",
        type=int,
        default=None,
    )
    filter_group.add_argument(
        "--max-length",
        help="Show messages with at most this many characters.",
        type=int,
        default=None,
    )
    filter_group.add_argument(
        "-K",
        "--skip",
        metavar="NUM",
        help="Skip the first set of matching messages.",
        type=int,
        default=None,
    )
    filter_group.add_argument(
        "--before",
        help="Show messages sent on or before this date (YYYY-MM-DD).",
        default=None,
    )
    filter_group.add_argument(
        "-N",
        "--msgnum",
        dest="msgnum_filter",
        help="Show specific message numbers or ranges (e.g., '100', '200-300', or '10,20,50-100').",
    )
    filter_group.add_argument(
        "-L",
        "--limit",
        metavar="NUM",
        help="Stop after this many matching messages.",
        type=int,
        default=None,
    )
    filter_group.add_argument(
        "-u",
        "--unique",
        help="Remove duplicate messages during a merge.",
        action="store_true",
    )
    filter_group.add_argument(
        "-O",
        "--sort",
        help="Sort results by field (date, author, to, subject, num, conference, bbs, length, size, or random).",
        choices=[
            "date",
            "author",
            "to",
            "subject",
            "num",
            "conference",
            "bbs",
            "length",
            "size",
            "random",
        ],
        default=None,
    )
    filter_group.add_argument(
        "--reverse",
        help="Reverse the order of the results.",
        action="store_true",
    )
    filter_group.add_argument(
        "--has-attachments",
        help="Show messages that contain attachments (UUE, yEnc, Base64).",
        action="store_true",
    )
    filter_group.add_argument(
        "--mine",
        help="Show messages sent to or from your user name.",
        action="store_true",
    )
    filter_group.add_argument(
        "--my-name",
        "--user",
        dest="my_name",
        help="Set your name for the --mine filter and QWK exports.",
    )
    filter_group.add_argument(
        "--on-this-day",
        help="Show messages sent on this same month and day in any year.",
        action="store_true",
    )
    filter_group.add_argument(
        "--has-links",
        help="Only show messages that contain web, gopher, ftp, or telnet links.",
        action="store_true",
    )
    filter_group.add_argument(
        "--has-emails",
        help="Only show messages that contain email addresses.",
        action="store_true",
    )
    filter_group.add_argument(
        "--has-phones",
        help="Only show messages that contain phone numbers.",
        action="store_true",
    )
    filter_group.add_argument(
        "--has-ansi",
        help="Only show messages that contain ANSI color codes.",
        action="store_true",
    )

    parser.add_argument(
        "-I",
        "--info",
        action="store_true",
        help="Show archive information and exit. You can save this to a file with -o.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show archive statistics and exit. You can save this to a file with -o.",
    )
    parser.add_argument(
        "--merge-stats",
        action="store_true",
        help="Show a single merged report when analyzing multiple archives.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the version number and exit.",
    )
    args = parser.parse_args()

    if args.threaded and args.individualfiles:
        parser.error(
            "You cannot use --threaded and --individual-files at the same time."
        )

    if args.oneline and args.individualfiles:
        parser.error(
            "You cannot use --oneline and --individual-files at the same time."
        )

    numeric_level = getattr(logging, args.loglevel)

    use_colors = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter(use_colors=use_colors))
    logging.basicConfig(level=numeric_level, handlers=[handler])

    logger = logging.getLogger(__name__)

    has_directory_input = any(os.path.isdir(p) for p in args.input_paths)
    input_paths = expand_paths(args.input_paths)
    output_path = args.output_path

    if not input_paths:
        logger.error(
            "No supported message archives were found in the paths you provided."
        )
        sys.exit(1)

    if args.organize_by_bbs:
        output_mode = "file"
        resolved_output_path = None
    elif args.info or args.stats:
        output_mode = "stdout"
        resolved_output_path = None
    elif args.individualfiles:
        if output_path is None:
            if len(args.input_paths) == 1 and not has_directory_input:
                output_path = os.path.splitext(os.path.basename(args.input_paths[0]))[0]
                logger.info(
                    "No output path provided. Using default folder: %s/", output_path
                )
            else:
                parser.error(
                    "You must provide an output folder when saving messages as individual files."
                )
        if os.path.exists(output_path) and not os.path.isdir(output_path):
            parser.error(
                "The output path must be a folder when saving messages as individual files."
            )
        output_mode = "file"
        resolved_output_path = output_path
    elif args.merge or (
        not output_path and (len(input_paths) > 1 or has_directory_input)
    ):
        if not args.merge:
            args.merge = True
            logger.info(
                "Multiple archives provided without an output path. Merging results to the screen."
            )
        output_mode = "stdout" if not output_path else "file"
        resolved_output_path = output_path
    elif len(input_paths) > 1 or has_directory_input:
        output_mode = "file"
        resolved_output_path = output_path
    else:
        output_mode = "stdout" if not output_path else "file"
        resolved_output_path = output_path

    output_format = resolve_output_format(args.format, output_path, output_mode)

    if args.threaded and output_format in ("eml", "maildir"):
        parser.error(f"You cannot use --threaded with {output_format.upper()} format.")

    # Default to individual files for EML format if an output path is provided
    if output_format in ("eml", "maildir") and not args.individualfiles and output_path:
        args.individualfiles = True
        # If the user provided an output path that looks like a file (has an extension),
        # but these formats force individual files (directory), it's confusing.
        # However, the core logic requires output_path to be a directory for individual files.
        if (
            output_path
            and os.path.exists(output_path)
            and not os.path.isdir(output_path)
        ):
            parser.error(
                f"The output path must be a folder when saving messages in {output_format.upper()} format."
            )

        output_mode = "file"
        resolved_output_path = output_path

    try:
        after_date = _parse_cli_date(args.after)
        before_date = _parse_cli_date(args.before, end_of_day=True)
        msgnum_filters = _parse_msgnum_ranges(args.msgnum_filter)
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
        organize_by_date=getattr(args, "organize_by_date", False),
        organize_by_bbs=args.organize_by_bbs,
        organize_by_author=getattr(args, "organize_by_author", False),
        organize_by_to=getattr(args, "organize_by_to", False),
        organize_by_subject=getattr(args, "organize_by_subject", False),
        include_toc=args.include_toc,
        extract_attachments=args.extractattachments,
        embed_attachments=args.embed_attachments,
        organize_attachments=args.organize_attachments,
        msgnum_filters=msgnum_filters,
        format=output_format,
        separator=args.separator,
        output_mode=output_mode,
        output_path=resolved_output_path,
        encoding=args.encoding,
        regex=args.regex,
        conferences=args.conferences,
        bbs_names=args.bbs_names,
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
        oneline=args.oneline or bool(getattr(args, "oneline_pattern", None)),
        oneline_pattern=getattr(args, "oneline_pattern", None),
        has_attachments=args.has_attachments,
        mine=args.mine,
        on_this_day=args.on_this_day,
        merge_stats=args.merge_stats,
        has_links=getattr(args, "has_links", False),
        my_name=getattr(args, "my_name", None),
        has_emails=getattr(args, "has_emails", False),
        has_phones=getattr(args, "has_phones", False),
        has_ansi=getattr(args, "has_ansi", False),
        body_search=args.body_search,
        exclude_search=args.exclude_search,
        exclude_authors=args.exclude_authors,
        exclude_recipients=args.exclude_recipients,
        exclude_subjects=args.exclude_subjects,
        exclude_conferences=args.exclude_conferences,
        exclude_bbs_names=args.exclude_bbs_names,
        filename_pattern=getattr(args, "filename_pattern", None),
        organize_pattern=getattr(args, "organize_pattern", None),
        min_length=getattr(args, "min_length", None),
        max_length=getattr(args, "max_length", None),
    )

    if args.organize_by_bbs and not args.output_path:
        organize_by_bbs(input_paths, settings, logger)
        sys.exit(0)

    if args.info:
        show_info(input_paths, settings, logger)
        sys.exit(0)

    if args.stats:
        show_stats(input_paths, settings, logger)
        sys.exit(0)

    if args.merge or (len(input_paths) == 1 and not has_directory_input):
        try:
            process_merged_files(input_paths, settings, logger)
        except PROCESSING_EXCEPTIONS as error:
            logger.error(error)
            sys.exit(1)
    else:
        had_errors = process_multiple_files(input_paths, output_path, settings, logger)
        if had_errors:
            sys.exit(1)


if __name__ == "__main__":
    main()
