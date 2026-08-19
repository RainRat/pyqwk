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
    show_threads,
    show_attachments,
    validate_archive,
    show_validation_report,
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


class ListPresetsAction(argparse.Action):
    """Custom argparse Action to display available workflow presets and exit.

    We inherit from argparse.Action and use nargs=0 so that '--list-presets' can be
    called directly by the user as a flag. By printing the preset definitions and
    calling parser.exit(0) immediately inside __call__, we successfully bypass
    argparse's validation checks for required positional arguments (like 'input_paths').
    This ensures users can run 'qwk --list-presets' alone without needing to supply
    dummy archive files.
    """
    def __init__(self, option_strings, dest, default=None, required=False, help=None):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            default=default,
            required=required,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        presets = {
            "blog": {
                "desc": "Save messages as clean, threaded individual Markdown files.",
                "equiv": "--format markdown --clean --threaded --individual-files"
            },
            "email": {
                "desc": "Save messages as individual EML files.",
                "equiv": "--format eml --individual-files"
            },
            "backup": {
                "desc": "Create a complete SQLite backup with private and unique messages.",
                "equiv": "--format sqlite --private --unique"
            },
            "digest": {
                "desc": "Save a single clean, threaded HTML file with a table of contents.",
                "equiv": "--format html --threaded --clean --toc"
            },
            "forum": {
                "desc": "Save messages as clean, threaded individual HTML files with an index (static discussion board).",
                "equiv": "--format html --clean --threaded --individual-files --toc"
            },
            "feed": {
                "desc": "Save messages as a clean, chronological RSS feed sorted from newest to oldest.",
                "equiv": "--format rss --clean --sort date --reverse"
            },
            "text-archive": {
                "desc": "Save clean text without headers.",
                "equiv": "--format text --clean --noheader"
            }
        }

        use_colors = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

        bold_cyan = "\033[1;36m"
        bold_green = "\033[1;32m"
        dim_gray = "\033[2m"
        reset = "\033[0m"

        header = "Available Workflow Presets:"
        if use_colors:
            header = f"{bold_cyan}{header}{reset}"

        print(header + "\n")
        for name, details in presets.items():
            preset_name = name
            desc = details["desc"]
            equiv = details["equiv"]

            if use_colors:
                preset_name = f"{bold_green}{preset_name}{reset}"
                equiv = f"{dim_gray}{equiv}{reset}"

            print(f"  {preset_name}")
            print(f"    Description: {desc}")
            print(f"    Equivalent:  {equiv}\n")

        parser.exit(0)


def main() -> None:
    template_variables = (
        "template variables:\n"
        "  Basic Information:\n"
        "    {author}, {to}, {subject}, {subject_clean}, {body}, {body_clean},\n"
        "    {confname}, {confnum}, {confname_or_num}, {msgnum}, {snippet},\n"
        "    {url_count}, {email_count}, {phone_count}, {msg_link_count}, {my_name},\n"
        "    {urls}, {emails}, {phones}, {msg_links}\n"
        "  Dates & Times:\n"
        "    {date}, {time}, {year}, {month}, {day}, {hour}, {minute}, {second},\n"
        "    {iso_date}, {iso_time}\n"
        "  BBS & Source:\n"
        "    {bbs_name}, {bbs_id}, {source_file}\n"
        "  Technical Details:\n"
        "    {msgid}, {refnum}, {status}, {msgflag}, {is_private}, {is_reply},\n"
        "    {length}, {word_count}, {size}, {flags}, {indent}, {thread_id},\n"
        "    {parent_msgnum}, {depth}, {reply_count}, {thread_size}\n"
        "  Attachments:\n"
        "    {attachments}, {attachment_count}"
    )

    parser = argparse.ArgumentParser(
        description="Convert BBS message archives into modern formats like HTML, Markdown, and SQLite.",
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

  # Show replies to message #42
  qwk archive.qwk --reply-to 42

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
        help="Save results to a file or folder. If omitted, messages print to the screen.",
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
        help="Save attachments to a folder.",
        action="store_true",
    )
    content_group.add_argument(
        "--embed-attachments",
        dest="embed_attachments",
        help="Include image attachments directly in the HTML output.",
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
        help="Show the message details (metadata) without the body.",
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
            "qwk",
            "rep",
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
        help="Group replies into conversations. When used with --individual-files, messages are saved in thread order.",
        action="store_true",
    )
    format_group.add_argument(
        "-1",
        "--oneline",
        help="Show a one-line summary (Conf, Date, From, To, Flags, Subject). Use with --verbose to include the message number.",
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
        "--validate",
        action="store_true",
        help="Validate the structural integrity and metadata completeness of the archives and exit.",
    )
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

    search_group = parser.add_argument_group("Search & Field Filters")
    search_group.add_argument(
        "-C",
        "--conference",
        dest="conferences",
        action="append",
        help="Show messages from a specific conference (name or number). Supports partial matches.",
    )
    search_group.add_argument(
        "-B",
        "--bbs",
        dest="bbs_names",
        action="append",
        help="Show messages from a specific BBS (name or ID). Supports partial matches.",
    )
    search_group.add_argument(
        "-f",
        "--from",
        dest="authors",
        action="append",
        help="Show messages from a specific author. Supports partial matches.",
    )
    search_group.add_argument(
        "--to",
        dest="recipients",
        action="append",
        help="Show messages to a specific recipient. Supports partial matches.",
    )
    search_group.add_argument(
        "-s",
        "--subject",
        dest="subjects",
        action="append",
        help="Show messages with specific keywords in the subject. Supports partial matches.",
    )
    search_group.add_argument(
        "-S",
        "--search",
        dest="search_term",
        help=(
            "Show messages with specific keywords in any common field:\n"
            "Author, To, Subject, Body, Conference, BBS, BBS ID, Source File, and Attachments.\n"
            "Supports partial matches."
        ),
    )
    search_group.add_argument(
        "--body",
        dest="body_search",
        help="Show messages with specific keywords in the body. Supports partial matches.",
    )
    search_group.add_argument(
        "--attachment-pattern",
        dest="attachment_pattern",
        help="Show only messages with attachments matching a wildcard pattern (e.g., '*.zip', 'image.gif', or 'png').",
    )
    search_group.add_argument(
        "--thread-id",
        dest="thread_id_filter",
        help="Show only messages belonging to specific conversation thread IDs (the root message number of the thread, e.g., '42', '100-150', or '10,20').",
    )

    exclude_group = parser.add_argument_group("Exclusion Filters")
    exclude_group.add_argument(
        "-X",
        "--exclude",
        dest="exclude_search",
        help=(
            "Hide messages with specific keywords in any common field:\n"
            "Author, To, Subject, Body, Conference, BBS, BBS ID, Source File, and Attachments.\n"
            "Supports partial matches."
        ),
    )
    exclude_group.add_argument(
        "--exclude-from",
        dest="exclude_authors",
        action="append",
        help="Hide messages from a specific author. Supports partial matches.",
    )
    exclude_group.add_argument(
        "--exclude-to",
        dest="exclude_recipients",
        action="append",
        help="Hide messages sent to a specific recipient. Supports partial matches.",
    )
    exclude_group.add_argument(
        "--exclude-subject",
        dest="exclude_subjects",
        action="append",
        help="Hide messages with specific keywords in the subject. Supports partial matches.",
    )
    exclude_group.add_argument(
        "--exclude-conference",
        dest="exclude_conferences",
        action="append",
        help="Hide messages from a specific conference. Supports partial matches.",
    )
    exclude_group.add_argument(
        "--exclude-bbs",
        dest="exclude_bbs_names",
        action="append",
        help="Hide messages from a specific BBS. Supports partial matches.",
    )

    date_content_group = parser.add_argument_group("Date & Content Filters")
    date_content_group.add_argument(
        "--after",
        help="Show messages sent on or after this date (YYYY-MM-DD).",
        default=None,
    )
    date_content_group.add_argument(
        "--before",
        help="Show messages sent on or before this date (YYYY-MM-DD).",
        default=None,
    )
    date_content_group.add_argument(
        "--on-this-day",
        help="Show messages sent on this same month and day in any year.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--mine",
        help="Show messages sent to or from your user name.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--my-name",
        "--user",
        dest="my_name",
        help="Set your name for the --mine filter and QWK exports.",
    )
    date_content_group.add_argument(
        "--has-attachments",
        help="Show messages that contain attachments.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--has-links",
        help="Show messages that contain links.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--has-emails",
        help="Show messages that contain email addresses.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--has-phones",
        help="Show messages that contain phone numbers.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--has-ansi",
        help="Show messages that contain color codes.",
        action="store_true",
    )
    date_content_group.add_argument(
        "--has-msg-links",
        help="Show messages that contain internal message links (e.g., 'msg #123').",
        action="store_true",
    )
    date_content_group.add_argument(
        "--regex",
        action="store_true",
        help="Use regular expressions (advanced patterns) for searching and filtering.",
    )

    quality_group = parser.add_argument_group("Size & Quality Filters")
    quality_group.add_argument(
        "--limit-per-to",
        metavar="NUM",
        help="Limit the number of matching messages per recipient.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--min-length",
        metavar="NUM",
        help="Show messages with at least NUM characters.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--min-replies",
        metavar="NUM",
        help="Show messages with at least NUM direct replies.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--min-thread-size",
        metavar="NUM",
        help="Show messages belonging to a conversation with at least NUM messages.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--limit-per-bbs",
        metavar="NUM",
        help="Limit the number of matching messages per BBS.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--max-replies",
        metavar="NUM",
        help="Show messages with at most NUM direct replies.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--max-thread-size",
        metavar="NUM",
        help="Show messages belonging to a conversation with at most NUM messages.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--limit-per-author",
        metavar="NUM",
        help="Limit the number of matching messages per author.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--limit-per-subject",
        metavar="NUM",
        help="Limit the number of matching messages per subject.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--limit-per-conf",
        metavar="NUM",
        help="Limit the number of matching messages per conference.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--min-attachments",
        metavar="NUM",
        help="Show messages with at least NUM attachments.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--min-words",
        metavar="NUM",
        help="Show messages with at least NUM words.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--max-attachments",
        metavar="NUM",
        help="Show messages with at most NUM attachments.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "--max-words",
        metavar="NUM",
        help="Show messages with at most NUM words.",
        type=int,
        default=None,
    )
    quality_group.add_argument(
        "-R",
        "--reply-to",
        "--refnum",
        dest="refnum_filter",
        help="Show messages that are a reply to specific reference/message numbers or ranges (e.g., '100', '200-300', or '10,20,50-100').",
    )
    quality_group.add_argument(
        "--max-length",
        metavar="NUM",
        help="Show messages with at most NUM characters.",
        type=int,
        default=None,
    )
    sorting_limit_group = parser.add_argument_group("Sorting & Result Limits")
    sorting_limit_group.add_argument(
        "-O",
        "--sort",
        help="Sort results by field (date, author, to, subject, num, conference, bbs, length, size, random, words, attachments, replies, or thread_size).",
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
            "words",
            "attachments",
            "replies",
            "thread_size",
        ],
        default=None,
    )
    sorting_limit_group.add_argument(
        "--reverse",
        help="Reverse the order of the results.",
        action="store_true",
    )
    sorting_limit_group.add_argument(
        "-L",
        "--limit",
        metavar="NUM",
        help="Stop after NUM matching messages.",
        type=int,
        default=None,
    )
    sorting_limit_group.add_argument(
        "--tail",
        "--last",
        metavar="NUM",
        help="Show the last NUM matching messages.",
        type=int,
        default=None,
    )
    sorting_limit_group.add_argument(
        "-K",
        "--skip",
        metavar="NUM",
        help="Skip the first NUM matching messages.",
        type=int,
        default=None,
    )
    sorting_limit_group.add_argument(
        "-u",
        "--unique",
        help="Remove duplicate messages during a merge.",
        action="store_true",
    )
    sorting_limit_group.add_argument(
        "-N",
        "--msgnum",
        dest="msgnum_filter",
        help="Show specific message numbers or ranges (e.g., '100', '200-300', or '10,20,50-100').",
    )
    sorting_limit_group.add_argument(
        "--count-only",
        action="store_true",
        help="Output only the integer count of matching messages to stdout and exit.",
    )

    preset_group = parser.add_argument_group("Workflow Presets")
    preset_group.add_argument(
        "-P",
        "--preset",
        choices=["blog", "email", "backup", "digest", "forum", "feed", "text-archive"],
        help=(
            "Apply predefined parameter combinations for common workflows:\n"
            "  blog: Save messages as clean, threaded individual Markdown files.\n"
            "  email: Save messages as individual EML files.\n"
            "  backup: Create a complete SQLite backup with private and unique messages.\n"
            "  digest: Save a single clean, threaded HTML file with a table of contents.\n"
            "  forum: Save messages as clean, threaded individual HTML files with an index (static discussion board).\n"
            "  feed: Save messages as a clean, chronological RSS feed sorted from newest to oldest.\n"
            "  text-archive: Save clean text without headers."
        ),
    )
    preset_group.add_argument(
        "--list-presets",
        action=ListPresetsAction,
        help="List all available workflow presets, their descriptions, and equivalent command-line options, then exit.",
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
        "--threads",
        action="store_true",
        help="Show a summary of all conversation threads and exit. You can save this to a file with -o.",
    )
    parser.add_argument(
        "--list-attachments",
        action="store_true",
        help="Show a list of all attachments found across processed archives and exit. You can save this to a file with -o.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the version number and exit.",
    )
    args = parser.parse_args()

    # Apply presets if specified
    if getattr(args, "preset", None):
        presets = {
            "blog": {
                "format": "markdown",
                "clean": True,
                "threaded": True,
                "individualfiles": True,
            },
            "email": {
                "format": "eml",
                "individualfiles": True,
            },
            "backup": {
                "format": "sqlite",
                "private": True,
                "unique": True,
            },
            "digest": {
                "format": "html",
                "threaded": True,
                "clean": True,
                "include_toc": True,
            },
            "forum": {
                "format": "html",
                "clean": True,
                "threaded": True,
                "individualfiles": True,
                "include_toc": True,
            },
            "feed": {
                "format": "rss",
                "clean": True,
                "sort": "date",
                "reverse": True,
            },
            "text-archive": {
                "format": "text",
                "clean": True,
                "noheader": True,
            },
        }

        # Determine which arguments were explicitly passed on the command line.
        # This is a critical workaround: standard argparse does not distinguish between
        # a default value defined on the parser and an option explicitly passed by the user
        # (both end up as plain attributes in the parsed Namespace).
        # To allow explicit CLI arguments to override preset settings (while avoiding having
        # implicit parser defaults unintentionally overwrite presets), we manually inspect sys.argv
        # to identify options actually typed by the user and populate 'explicit_keys'.
        explicit_keys = set()
        for action in parser._actions:
            for opt in action.option_strings:
                if opt.startswith("--"):
                    if any(arg == opt or arg.startswith(opt + "=") for arg in sys.argv):
                        explicit_keys.add(action.dest)
                        break
                elif opt.startswith("-"):
                    # Short option, e.g., '-F' or '-t'
                    char = opt[1:]
                    for arg in sys.argv:
                        if arg.startswith("-") and not arg.startswith("--"):
                            if arg == opt or arg.startswith(opt + "="):
                                explicit_keys.add(action.dest)
                                break
                            elif char in arg[1:] and not arg[1:].isdigit():
                                explicit_keys.add(action.dest)
                                break
                    if action.dest in explicit_keys:
                        break

        preset_config = presets.get(args.preset, {})
        for key, val in preset_config.items():
            if key not in explicit_keys:
                setattr(args, key, val)

    if args.oneline and args.individualfiles:
        parser.error(
            "You cannot use --oneline and --individual-files at the same time. "
            "Please choose --oneline for a quick summary, or --individual-files to save each message separately."
        )

    numeric_level = getattr(logging, args.loglevel)

    use_colors = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    handler = logging.StreamHandler()
    handler.setFormatter(LogFormatter(use_colors=use_colors))
    logging.basicConfig(level=numeric_level, handlers=[handler])

    logger = logging.getLogger(__name__)

    # Preprocess standard input '-'
    from pyqwk.core import check_and_handle_stdin
    args.input_paths = check_and_handle_stdin(args.input_paths, logger)

    has_directory_input = any(os.path.isdir(p) for p in args.input_paths)
    input_paths = expand_paths(args.input_paths)
    output_path = args.output_path

    if not input_paths:
        logger.error(
            "No supported message archives were found in the paths you provided."
        )
        sys.exit(1)

    is_archive_out = False
    if output_path:
        is_archive_out = output_path.lower().endswith((".zip", ".tar", ".tar.gz", ".tar.bz2", ".tgz"))

    if args.organize_by_bbs:
        output_mode = "file"
        resolved_output_path = None
    elif args.info or args.stats:
        output_mode = "stdout"
        resolved_output_path = None
    elif getattr(args, "threads", False) or getattr(args, "list_attachments", False):
        output_mode = "stdout" if not output_path else "file"
        resolved_output_path = output_path
    elif args.individualfiles:
        if output_path is None:
            if len(args.input_paths) == 1 and not has_directory_input:
                output_path = os.path.splitext(os.path.basename(args.input_paths[0]))[0]
                logger.info(
                    "No output path provided. Using default folder: %s/", output_path
                )
            else:
                parser.error(
                    "Please specify an output folder using the -o or --output option when saving messages as individual files."
                )
        if os.path.exists(output_path) and not os.path.isdir(output_path) and not is_archive_out:
            parser.error(
                f"The output path '{output_path}' must be a folder when saving messages as individual files. "
                "Please provide a path to a folder."
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

    if output_format in ("qwk", "rep") and args.individualfiles:
        parser.error(f"You cannot use --individual-files with {output_format.upper()} format.")

    if output_format in ("sqlite", "qwk", "rep") and not output_path:
        parser.error(f"You cannot export to {output_format.upper()} format without providing an output path.")

    if args.threaded and output_format in ("eml", "maildir"):
        parser.error(
            f"You cannot use --threaded with {output_format.upper()} format. "
            f"These formats save messages as individual files, which do not support conversational threading. "
            "Please remove the --threaded option."
        )

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
            and not is_archive_out
        ):
            parser.error(
                f"The output path '{output_path}' must be a folder when saving messages in {output_format.upper()} format. "
                "Please provide a path to a folder."
            )

        output_mode = "file"
        resolved_output_path = output_path

    try:
        after_date = _parse_cli_date(args.after)
        before_date = _parse_cli_date(args.before, end_of_day=True)
        msgnum_filters = _parse_msgnum_ranges(args.msgnum_filter)
        refnum_filters = _parse_msgnum_ranges(getattr(args, "refnum_filter", None))
        thread_id_filters = _parse_msgnum_ranges(getattr(args, "thread_id_filter", None))
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
        refnum_filters=refnum_filters,
        thread_id_filters=thread_id_filters,
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
        has_msg_links=getattr(args, "has_msg_links", False),
        body_search=args.body_search,
        exclude_search=args.exclude_search,
        exclude_authors=args.exclude_authors,
        exclude_recipients=args.exclude_recipients,
        exclude_subjects=args.exclude_subjects,
        exclude_conferences=args.exclude_conferences,
        exclude_bbs_names=args.exclude_bbs_names,
        filename_pattern=getattr(args, "filename_pattern", None),
        organize_pattern=getattr(args, "organize_pattern", None),
        tail=getattr(args, "tail", None),
        min_length=getattr(args, "min_length", None),
        max_length=getattr(args, "max_length", None),
        min_words=getattr(args, "min_words", None),
        max_words=getattr(args, "max_words", None),
        limit_per_conf=getattr(args, "limit_per_conf", None),
        limit_per_author=getattr(args, "limit_per_author", None),
        limit_per_subject=getattr(args, "limit_per_subject", None),
        limit_per_bbs=getattr(args, "limit_per_bbs", None),
        limit_per_to=getattr(args, "limit_per_to", None),
        min_attachments=getattr(args, "min_attachments", None),
        max_attachments=getattr(args, "max_attachments", None),
        min_depth=getattr(args, "min_depth", None),
        max_depth=getattr(args, "max_depth", None),
        min_replies=getattr(args, "min_replies", None),
        max_replies=getattr(args, "max_replies", None),
        min_thread_size=getattr(args, "min_thread_size", None),
        max_thread_size=getattr(args, "max_thread_size", None),
        attachment_pattern=getattr(args, "attachment_pattern", None),
        count_only=getattr(args, "count_only", False),
    )

    if getattr(args, "count_only", False):
        try:
            process_merged_files(input_paths, settings, logger)
            sys.exit(0)
        except PROCESSING_EXCEPTIONS as error:
            logger.error(error)
            sys.exit(1)

    if getattr(args, "validate", False):
        valid_all = show_validation_report(input_paths, settings, logger, validator=validate_archive)
        sys.exit(0 if valid_all else 1)

    if args.organize_by_bbs and not args.output_path:
        organize_by_bbs(input_paths, settings, logger)
        sys.exit(0)

    if args.info:
        show_info(input_paths, settings, logger)
        sys.exit(0)

    if args.stats:
        show_stats(input_paths, settings, logger)
        sys.exit(0)

    if getattr(args, "threads", False):
        show_threads(input_paths, settings, logger)
        sys.exit(0)

    if getattr(args, "list_attachments", False):
        show_attachments(input_paths, settings, logger)
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
