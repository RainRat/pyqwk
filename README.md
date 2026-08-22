# pyqwk

pyqwk converts message archives into modern, readable formats like HTML, Markdown, and SQLite. It supports many file types, including QWK, ZIP, TAR, JSON, CSV, mbox, EML, and more.

## What are QWK and REP files?

QWK files started in the 1980s for Bulletin Board Systems (BBS). Users downloaded messages in a single "packet," read them offline, and then uploaded replies in a `.REP` packet.

Inside these packets, messages are organized into **Conferences**. A Conference is like a modern forum or channel dedicated to a specific topic.

## Features

- **Support many formats:** Import and export between QWK, JSON, JSONL, CSV, XML, RSS, SQLite, mbox, EML, Markdown, HTML, and Plain Text.
- **Group conversations:** Organize replies into threads to follow discussions easily.
- **Clean content:** Automatically remove signatures, old quotes, attachments, and color codes.
- **Protect privacy:** Hide personal information or private messages.
- **Process many files:** Convert several archives at once or merge them into one file.
- **Preview changes:** Use "Dry Run" mode to see results before writing any files.
- **Read messages:** Use the built-in graphical reader to browse archives without converting them.

## Supported Formats

| Format | Import | Export | Notes |
| :--- | :---: | :---: | :--- |
| **QWK / REP** | ✅ | ✅ | Classic BBS packets (.qwk, .rep, .zip, .tar, .tar.gz, .tar.bz2, .tgz, messages.dat, reply.dat) |
| **JSON / JSONL** | ✅ | ✅ | Modern structured data (.json, .jsonl) |
| **HTML** | ✅ | ✅ | Browsable files with conversation grouping and charts (.html, .htm) |
| **Markdown** | ✅ | ✅ | Readable text files (.md, .markdown) |
| **CSV** | ✅ | ✅ | Spreadsheets and databases (.csv) |
| **RSS** | ✅ | ✅ | Feed readers and syndication (.rss) |
| **XML** | ✅ | ✅ | Generic structured data (.xml) |
| **SQLite** | ✅ | ✅ | Relational databases (.db, .sqlite) |
| **mbox / EML / Maildir** | ✅ | ✅ | Email applications (.mbox, .eml, .maildir) |
| **Plain Text** | ✅ | ✅ | Simple readable text (.txt) |

## Prerequisites

### Required
- **Python 3.10** or newer.

### Optional
- **Tkinter:** Needed for the graphical reader. Most Python installations already have it. Linux and macOS users may need to install it:
  - **Ubuntu/Debian:** `sudo apt install python3-tk`
  - **Fedora:** `sudo dnf install python3-tkinter`
  - **Arch Linux:** `sudo pacman -S tk`
  - **macOS (Homebrew):** `brew install python-tk`
- **tqdm:** Adds a progress bar. Install with: `python -m pip install tqdm`
- **unzip:** Helps open older ZIP archives. Install it if `pyqwk` cannot open your file:
  - **Ubuntu/Debian:** `sudo apt install unzip`
  - **Fedora:** `sudo dnf install unzip`
  - **Arch Linux:** `sudo pacman -S unzip`
  - **macOS:** `brew install unzip`
  - **Windows:** `winget install GnuWin32.UnZip`

## Quick Start

Run the tool on any supported archive:

```bash
# Process a single archive
python qwk.py archive.qwk

# Process an entire folder
python qwk.py my_archives/

# Process a compressed TAR archive
python qwk.py messages.tar.gz
```

## Installation

You can install `pyqwk` to use it from any folder.

### Option 1: Install in a Virtual Environment (Recommended)

Using a virtual environment keeps your Python packages organized. It prevents conflicts between different projects on your computer.

1. Open your terminal in the `pyqwk` folder.
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment based on your operating system:
   - **Windows (Command Prompt):**
     ```cmd
     venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell):**
     ```powershell
     venv\Scripts\Activate.ps1
     ```
   - **macOS and Linux:**
     ```bash
     source venv/bin/activate
     ```
4. Install the package:
   ```bash
   python -m pip install .
   ```
5. Run `pyqwk` using the command-line command:
   ```bash
   qwk archive.qwk
   ```
6. Or start the graphical reader:
   ```bash
   qwk-gui
   ```

### Option 2: Install System-Wide

If you prefer not to use a virtual environment, you can install the tool directly to your system's Python environment.

1. Open your terminal in the `pyqwk` folder.
2. Install the package:
   ```bash
   python -m pip install .
   ```
3. Run the tool:
   ```bash
   qwk archive.qwk
   ```

*Note: You can also run the reader without installing:*
```bash
python -m pyqwk.gui
```

### Option 3: Install with Poetry (Recommended for Developers)

If you use Poetry to manage your Python projects, you can install and run the tool easily.

1. Open your terminal in the `pyqwk` folder.
2. Install the package and its dependencies:
   ```bash
   poetry install
   ```
3. Run the tool:
   ```bash
   poetry run qwk archive.qwk
   ```
4. Or start the graphical reader:
   ```bash
   poetry run qwk-gui
   ```

## Graphical Reader

Use the built-in reader to browse conferences, search messages, and follow conversations.

**To start the reader:**
```bash
# Open the reader
qwk-gui

# Open a specific file
qwk-gui archive.qwk

# Open several archives at once
qwk-gui archive1.qwk archive2.qwk

# Open all archives in a folder
qwk-gui archives/

# Open a database
qwk-gui messages.db
```

**Key Features:**
- **Search:** Find messages by keyword or use regular expressions. Cycle through matches with **F3** or **Shift + F3**. The reader moves to the next or previous message when you reach the end of the current one.
- **Attachments:** Click attachment links in the header to save files. Use **File > Extract All Attachments...** to save all files from your current view.
- **Filtering:** Narrow your view by BBS, conference, author, recipient, word count, or messages sent "on this day." Use the **Exclude** field to hide messages matching specific keywords. You can also filter for private messages or messages with attachments. Quick toggles help you find messages with links, emails, phones, color codes, or specific word counts.
- **Context Menus:** Right-click a message to copy its details, filter the view, or exclude specific authors and subjects.
- **Exporting:** Save your current filtered view to any format (HTML, Markdown, JSON, etc.).
- **Viewing Options:** Use "Conversations" to group replies into a threaded view. Use "Clean" view to hide signatures, quotes, attachments, and color codes. Use "Remove Colors" to strip only color codes. Use "Hide Personal Info" to redact emails and phone numbers. Use "Embed Attachments" to include images directly in messages.
- **Statistics:** View detailed activity reports. You can also save these reports as HTML files with interactive charts.

**Keyboard Shortcuts:**

**Archive & Stats**
- **Ctrl + O**: Open an archive.
- **Ctrl + S**: Export the current filtered view.
- **Ctrl + I**: View archive statistics and reports.
- **Ctrl + Q**: Exit the application.

**Search & Filters**
- **Ctrl + F** or **/**: Jump to the search bar.
- **Ctrl + E**: Jump to the exclude bar.
- **F3**: Find the next search match.
- **Shift + F3**: Find the previous search match.
- **Enter**: Find the next match when the search bar is focused.
- **Shift + Enter**: Find the previous match when the search bar is focused.
- **Esc**: Clear the search on the first press and all filters on the second press.
- **Ctrl + Shift + X**: Clear all filters instantly.

**Navigation**
- **j** or **n**: Move to the next message.
- **k** or **p**: Move to the previous message.
- **Space** or **PgDn**: Scroll down or move to the next message.
- **Shift + Space**, **BackSpace**, or **PgUp**: Scroll up or move to the previous message.
- **Ctrl + G**: Jump to a specific message number.
- **Ctrl + U**: Go to the referenced parent message.
- **r**: Select a random message.
- **[** or **]**: Move to the previous or next conference.
- **{** or **}**: Move to the previous or next BBS archive.

## Workflow Presets

`pyqwk` includes presets for common tasks. Presets apply several settings at once to save you time.

Use the `-P` or `--preset` option followed by the preset name:

```bash
# Save messages as clean, threaded Markdown files (perfect for blogs)
qwk archive.qwk --preset blog -o my_blog/

# Save messages as individual EML files (for email clients)
qwk archive.qwk --preset email -o ./emails/

# Back up your archive into a single SQLite database with duplicates removed
qwk archive.qwk --preset backup -o backup.db

# Create a single threaded HTML digest with a table of contents
qwk archive.qwk --preset digest -o digest.html

# Save messages as clean, threaded individual HTML files with an index (static discussion board)
qwk archive.qwk --preset forum -o my_forum_dir/

# Save messages as a clean, chronological RSS feed sorted from newest to oldest
qwk archive.qwk --preset feed -o feed.xml

# Save a simple clean text archive with no headers
qwk archive.qwk --preset text-archive -o archive.txt
```

To list all available presets and their equivalent options directly in your terminal, use:

```bash
qwk --list-presets
```

### Available Presets

| Preset | Action | Equivalent Options |
| :--- | :--- | :--- |
| `blog` | Saves clean, threaded Markdown files. | `--format markdown --clean --threaded --individual-files` |
| `email` | Saves messages as individual EML files. | `--format eml --individual-files` |
| `backup` | Creates a SQLite backup with private and unique messages. | `--format sqlite --private --unique` |
| `digest` | Saves a single clean, threaded HTML file with a table of contents. | `--format html --threaded --clean --toc` |
| `forum` | Saves clean, threaded individual HTML files with an index. | `--format html --clean --threaded --individual-files --toc` |
| `feed` | Saves a clean chronological RSS feed. | `--format rss --clean --sort date --reverse` |
| `text-archive` | Saves clean text without headers. | `--format text --clean --noheader` |

*Note: You can override any preset setting by adding its command-line option.*

## Usage Examples

**Read an archive:**
```bash
qwk archive.qwk
```

**Show a quick summary:**
```bash
# Standard one-line summary
qwk archive.qwk --oneline

# Custom summary with specific information
qwk archive.qwk --oneline-pattern "[{confnum}] {author}: {subject}"
```

**Save as a text file:**
```bash
qwk archive.qwk -o messages.txt
```

**Group messages into conversations:**
```bash
qwk archive.qwk --threaded -o messages.txt
```

**Create a browsable HTML file:**
```bash
qwk archive.qwk --format html -o messages.html
```

**Create a self-contained HTML file (includes images):**
```bash
qwk archive.qwk --embed-attachments -o messages.html
```

**Convert to an mbox file (for email apps):**
```bash
qwk archive.qwk --format mbox -o messages.mbox
```

**Save each message as a separate file:**
```bash
qwk archive.qwk --individual-files -o output_folder/
```

**Save separate files directly inside a compressed archive:**
You can save messages as individual files directly into a compressed archive like a ZIP or TAR file:
```bash
qwk archive.qwk --individual-files -o output.zip
```

**Organize files by conference:**
```bash
qwk archive.qwk --individual-files --organize -o output_folder/
```

**Organize files by date:**
```bash
qwk archive.qwk --individual-files --organize-by-date -o output_folder/
```

**Organize files by author:**
```bash
qwk archive.qwk --individual-files --organize-by-author -o output_folder/
```

**Organize files by recipient:**
```bash
qwk archive.qwk --individual-files --organize-by-to -o output_folder/
```

**Organize files by subject:**
```bash
qwk archive.qwk --individual-files --organize-by-subject -o output_folder/
```

**Use a custom folder structure:**
```bash
qwk archive.qwk --individual-files --organize-pattern "{year}/{month}/{author}" -o output_folder/
```

**Use custom filenames:**
```bash
qwk archive.qwk --individual-files --filename-pattern "{date}_{author}_{subject}" -o output_folder/
```

**Merge archives and remove duplicates:**
```bash
qwk archive1.qwk archive2.qwk --merge --unique -o combined.mbox
```

**Clean up messages (removes signatures, quotes, attachments, and color codes):**
```bash
qwk archive.qwk --clean -o clean.txt
```

**Extract attachments to a folder:**
```bash
qwk archive.qwk --extract-attachments -o output/
```

**List all attachments in an archive:**
```bash
qwk archive.qwk --list-attachments
```

**Hide personal information (emails and phones):**
```bash
qwk archive.qwk --redact-pii -o safe.txt
```

**Export to a database (SQLite):**
```bash
qwk archive.qwk --format sqlite -o messages.db
```

**Import from a spreadsheet (CSV):**
```bash
qwk messages.csv -o updated.html
```

**Export to JSONL (for big data and scripts):**
```bash
qwk archive.qwk --format jsonl -o messages.jsonl
```

**Create an RSS feed:**
```bash
qwk archive.qwk --format rss -o feed.xml
```

**Convert between modern formats (mbox to EML):**
```bash
qwk messages.mbox --format eml -o ./emails/
```

**Convert to Maildir:**
```bash
qwk archive.qwk --format maildir -o ./my_maildir/
```

**Check archive integrity (validate file):**
```bash
qwk archive.qwk --validate
```

**List conference areas across archives:**
```bash
qwk archive.qwk --list-conferences
```

**List message authors across archives:**
```bash
qwk archive.qwk --list-authors
```

**List Bulletin Board Systems across archives:**
```bash
qwk archive.qwk --list-bbs
```

**Show conversation threads summary:**
```bash
# Display a summary of all conversation threads
qwk archive.qwk --threads

# Save conversation threads summary as Markdown
qwk archive.qwk --threads --format markdown -o threads.md
```

**Export messages to a classic QWK packet:**
```bash
qwk messages.mbox --format qwk -o output.qwk
```

## Filtering & Searching

**Filter by Conference:**
```bash
qwk archive.qwk -C "General Chat"
```

**Filter by BBS:**
```bash
qwk my_archives/ --bbs "The Digital Horizon"
```

**Keyword Search:**
```bash
qwk archive.qwk --search "BBS"
```

**Filter by Date:**
```bash
# Between two specific dates
qwk archive.qwk --after 2023-01-01 --before 2023-12-31

# Messages from "this day" in any year
qwk archive.qwk --on-this-day
```

**Limit per Conference:**
```bash
# Show only the first 5 messages from each conference
qwk archive.qwk --limit-per-conf 5
```

**Limit per Author:**
```bash
# Show only the first 2 messages from each author
qwk archive.qwk --limit-per-author 2
```

**Limit per Subject:**
```bash
# Show only the first 3 messages from each subject
qwk archive.qwk --limit-per-subject 3
```

**Limit per BBS:**
```bash
# Show only the first 3 messages from each BBS
qwk my_archives/ --limit-per-bbs 3
```

**Find Content:**
```bash
# Show messages with links
qwk archive.qwk --has-links

# Show messages with phone numbers
qwk archive.qwk --has-phones

# Show messages with email addresses
qwk archive.qwk --has-emails

# Show messages with color codes
qwk archive.qwk --has-ansi
```

**Filter by Person:**
```bash
# Messages from or to specific names
qwk archive.qwk --from "Sysop" --to "Alice"

# Messages specifically for you (based on your user name)
qwk archive.qwk --mine
```

**Filter by Length:**
```bash
# At least 1000 characters
qwk archive.qwk --min-length 1000

# At least 2 attachments
qwk archive.qwk --min-attachments 2
```

**Filter by Length (Words):**
```bash
# At least 100 words
qwk archive.qwk --min-words 100

# Between 50 and 500 words
qwk archive.qwk --min-words 50 --max-words 500
```

**Filter by Thread Depth:**
```bash
# Show only original posts (depth 0)
qwk archive.qwk --threaded --max-depth 0

# Show messages at depth 2 or deeper
qwk archive.qwk --threaded --min-depth 2
```

**Filter by Engagement:**
```bash
# Show messages with at least 5 direct replies
qwk archive.qwk --min-replies 5

# Show messages from large conversations (at least 20 messages)
qwk archive.qwk --min-thread-size 20
```

**Filter by Message Number:**
```bash
qwk archive.qwk --msgnum 100-200
```

**Filter by Referenced Message Number (Reply-To):**
```bash
qwk archive.qwk --reply-to 100-200
```

**Filter by Conversation Thread ID:**
```bash
# Show only messages belonging to thread root message #42
qwk archive.qwk --thread-id 42

# Show messages from a range of threads
qwk archive.qwk --thread-id 100-150
```

**Filter by Attachment Filename Pattern:**
```bash
# Show only messages with attachments matching a wildcard pattern
qwk archive.qwk --attachment-pattern "*.zip"

# Show only messages containing attachments with "image" in the name
qwk archive.qwk --attachment-pattern "image"
```

**Count Matching Messages Only:**
You can output only the integer count of matching messages to the screen. This is very useful for shell scripts and piping:
```bash
# Count how many messages were sent by Alice
qwk archive.qwk --from "Alice" --count-only
```

**Dry Run:**
Preview your changes without writing files:
```bash
qwk archives/ --search "BBS" --dry-run
```

## Library Usage

You can use `pyqwk` as a library in your own Python projects:

```python
import logging
from pyqwk.core import load_data, parse_messages, process_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pyqwk")

# Load the archive
# file_data contains either original bytes (for QWK/REP) or a list of messages
file_data, board_dict = load_data("archive.qwk", logger)

# Parse the bytes if the archive is in an older format
if isinstance(file_data, list):
    messages = file_data
else:
    messages = parse_messages(file_data, None)

# Process messages
for msg in messages:
    # Remove signatures, quotes, and attachments
    clean_text = process_message(
        msg.text,
        truncate_signatures=True,
        cut_quoting=True,
        binaries_removal=True,
        redact_pii=False
    )

    conf_name = board_dict.get(msg.confnum, f"Conference {msg.confnum}")
    print(f"[{conf_name}] From: {msg.header.msgfrom}")
    print(clean_text)
```

## Common Options

| Flag | Description |
| :--- | :--- |
| `-o`, `--output` | Save results to a file or folder. |
| `-v, --verbose` | Show more details like conference names and message numbers. |
| `-q, --quiet` | Hide the progress bar and other information. |
| `-l, --loglevel` | Set the log detail level (DEBUG, INFO, WARNING, ERROR, CRITICAL). |
| `-V, --version` | Show the version number and exit. |
| `-i`, `--individual-files` | Save each message as a separate file. This also creates a browsable index for HTML and Markdown. |
| `-F, --format` | Set the output format (html, json, markdown, etc.). |
| `-j, --json` | Shortcut for `--format json`. |
| `-J, --jsonl` | Shortcut for `--format jsonl`. |
| `-P, --preset` | Apply predefined parameter combinations for common workflows (blog, email, backup, digest, forum, feed, text-archive). |
| `--list-presets` | List all available presets, their descriptions, and equivalent command-line options, then exit. |
| `--list-conferences` | List all conference areas across input archives and exit. |
| `--list-authors` | List all message authors with message counts and active date ranges, then exit. |
| `--list-bbs` | List all Bulletin Board Systems (BBS) across input archives with conference/message counts and active date ranges, then exit. |
| `--separator` | Set how to separate messages in the output file (auto, none, dashes, blank). |
| `-m, --merge` | Combine multiple archives into one file. |
| `-u, --unique` | Remove duplicate messages during a merge. |
| `-T`, `--threaded` | Group replies into threads. |
| `--clean` | Remove signatures, quotes, attachments, and color codes. |
| `-t, --truncate-signatures` | Stop reading a message when a signature is found. |
| `-c, --cut-quoting` | Remove quoted text from earlier messages. |
| `-b, --binaries-removal` | Remove attachments like images or programs from the message text. |
| `-x, --extract-attachments` | Save attachments to a folder. |
| `--list-attachments` | Show a summary of all attachments found across processed archives and exit. |
| `--embed-attachments` | Include image attachments directly in HTML files. |
| `--organize-attachments` | Organize extracted attachments into subfolders. |
| `--organize` | Organize files into folders by conference. |
| `--organize-by-date` | Organize files into folders by date (YYYY/MM). |
| `--organize-by-bbs` | Organize archives into folders named after the BBS. If used with -o, organizes the export folder instead. |
| `--organize-by-author` | Organize files into folders by author name. |
| `--organize-by-to` | Organize files into folders by recipient name. |
| `--organize-by-subject` | Organize files into folders by message subject. |
| `--organize-pattern` | Set a custom folder structure for individual files. |
| `--filename-pattern` | Set a custom filename pattern for individual files (e.g., `{date}_{author}_{subject}`). |
| `-O, --sort` | Sort results by field (date, author, to, subject, num, conference, bbs, length, size, random, words, attachments, replies, or thread_size). |
| `-r, --redact-pii` | Hide personal info like emails and phone numbers. |
| `-p, --private` | Include private messages. |
| `--mine` | Show messages sent to or from your user name. |
| `--my-name`, `--user` | Set your name for the `--mine` filter and QWK exports. |
| `--has-attachments` | Show messages that contain attachments. |
| `--has-links` | Show messages that contain links. |
| `--has-emails` | Show messages that contain email addresses. |
| `--has-phones` | Show messages that contain phone numbers. |
| `--has-ansi` | Show messages that contain color codes. |
| `--has-msg-links` | Show messages that contain internal message links (e.g., 'msg #123'). |
| `-A, --strip-ansi` | Remove color codes and other formatting symbols. |
| `-H, --headers-only` | Show the message details (metadata) without the body. |
| `-n, --noheader` | Hide message details (headers) in the output text. |
| `-E, --encoding` | Set the text encoding (default is `cp437`). |
| `-S, --search` | Show messages with specific keywords in any common field: Author, To, Subject, Body, Conference, BBS, BBS ID, Source File, and Attachments. Supports partial matches. |
| `-C, --conference` | Show messages from a specific conference (name or number). Supports partial matches. |
| `-B, --bbs` | Show messages from a specific BBS (name or ID). Supports partial matches. |
| `-f, --from` | Show messages from a specific author. Supports partial matches. |
| `--to` | Show messages to a specific recipient. Supports partial matches. |
| `-s, --subject` | Show messages with specific keywords in the subject. Supports partial matches. |
| `--body` | Show messages with specific keywords in the body. Supports partial matches. |
| `--attachment-pattern` | Show only messages with attachments matching a wildcard pattern (e.g., `*.zip`, `image.gif`, or `png`). |
| `--thread-id` | Show only messages belonging to specific conversation thread IDs (the root message number of a thread). |
| `-X, --exclude` | Hide messages with specific keywords in any common field: Author, To, Subject, Body, Conference, BBS, BBS ID, Source File, and Attachments. Supports partial matches. |
| `--exclude-from` | Hide messages from a specific author. Supports partial matches. |
| `--exclude-to` | Hide messages sent to a specific recipient. Supports partial matches. |
| `--exclude-subject` | Hide messages with specific keywords in the subject. Supports partial matches. |
| `--exclude-conference` | Hide messages from a specific conference. Supports partial matches. |
| `--exclude-bbs` | Hide messages from a specific BBS. Supports partial matches. |
| `--after` | Show messages sent on or after a date (YYYY-MM-DD). |
| `--before` | Show messages sent on or before a date (YYYY-MM-DD). |
| `--limit-per-conf` | Limit the number of matching messages per conference. |
| `--limit-per-author` | Limit the number of matching messages per author. |
| `--limit-per-subject` | Limit the number of matching messages per subject. |
| `--limit-per-to` | Limit the number of matching messages per recipient. |
| `--limit-per-bbs` | Limit the number of matching messages per BBS. |
| `--tail` | Show the last NUM matching messages. Alias: `--last`. |
| `--on-this-day` | Show messages from the same month and day. |
| `-N, --msgnum` | Show specific message numbers or ranges. |
| `-R, --reply-to`, `--refnum` | Show messages that are a reply to specific reference/message numbers or ranges. |
| `-L, --limit` | Stop after NUM matching messages. |
| `-K, --skip` | Skip the first NUM matching messages. |
| `--regex` | Use regular expressions for search and filters. |
| `--reverse` | Reverse the sorting order. |
| `--count-only` | Output only the integer count of matching messages to the screen and exit. |
| `--min-length` | Show messages with at least NUM characters. |
| `--max-length` | Show messages with at most NUM characters. |
| `--min-words` | Show messages with at least NUM words. |
| `--min-attachments` | Show messages with at least NUM attachments. |
| `--max-words` | Show messages with at most NUM words. |
| `--max-attachments` | Show messages with at most NUM attachments. |
| `--min-depth` | Show messages with a thread depth of at least NUM. |
| `--max-depth` | Show messages with a thread depth of at most NUM. |
| `--min-replies` | Show messages with at least NUM direct replies. |
| `--max-replies` | Show messages with at most NUM direct replies. |
| `--min-thread-size` | Show messages belonging to a conversation with at least NUM messages. |
| `--max-thread-size` | Show messages belonging to a conversation with at most NUM messages. |
| `--toc` | Add a table of contents to the output. |
| `-1, --oneline` | Show a one-line summary (Conf, Date, From, To, Flags, Subject). Use with --verbose to include the message number. |
| `--oneline-pattern` | Set a custom pattern for one-line summaries. |
| `-I, --info` | Show a summary of the archive and exit. |
| `--stats` | Show message statistics and exit. |
| `--merge-stats` | Show a single merged report for multiple archives. |
| `--threads` | Show a summary of all conversation threads and exit. |
| `--validate` | Validate archive integrity and metadata completeness, then exit. |
| `--dry-run` | Preview actions without writing files. |

Run `qwk --help` for all options.

## Custom Pattern Variables

You can use custom patterns with `--oneline-pattern` (for summaries on the screen) and `--filename-pattern` (for naming individual files).

### Basic Information
| Variable | Description |
| :--- | :--- |
| `{author}` | The name of the person who sent the message. |
| `{to}` | The name of the recipient. |
| `{subject}` | The original subject line. |
| `{subject_clean}` | The subject line without "Re:" or "Fwd:" prefixes. |
| `{body}` | The full text of the message body. |
| `{body_clean}` | The message body with all whitespace collapsed into single spaces. |
| `{confname}` | The name of the conference (if known). |
| `{confnum}` | The number of the conference. |
| `{confname_or_num}` | The conference name, or its number if the name is missing. |
| `{msgnum}` | The unique message number. |
| `{snippet}` | The first line of the message body. |
| `{url_count}` | The number of web links found in the message. |
| `{email_count}` | The number of email addresses found in the message. |
| `{phone_count}` | The number of phone numbers found in the message. |
| `{msg_link_count}` | The number of message references found in the text. |
| `{my_name}` | The user name (either from archive information or your override). |
| `{urls}` | A comma-separated list of web links found in the message. |
| `{emails}` | A comma-separated list of email addresses found in the message. |
| `{phones}` | A comma-separated list of phone numbers found in the message. |
| `{msg_links}` | A list of message numbers referenced in the text. |

### Dates & Times
| Variable | Description |
| :--- | :--- |
| `{date}` | The date in `MM-DD-YY` format. |
| `{time}` | The time in `HH:MM` format. |
| `{year}`, `{month}`, `{day}` | Individual date parts (e.g., `2023`, `10`, `12`). |
| `{hour}`, `{minute}`, `{second}` | Individual time parts. |
| `{iso_date}`, `{iso_time}` | Date and time in standard ISO format. |

### BBS & Source
| Variable | Description |
| :--- | :--- |
| `{bbs_name}` | The name of the BBS where the message originated. |
| `{bbs_id}` | The short ID of the BBS. |
| `{source_file}` | The name of the archive file that contained the message. |

### Technical Details
| Variable | Description |
| :--- | :--- |
| `{msgid}` | A unique identifier for the message (`conf.msg@bbs`). |
| `{refnum}` | The message number being replied to. |
| `{status}` | The status code (e.g., `*` for private). |
| `{msgflag}` | Technical flags from the message header. |
| `{is_private}` | Returns `true` or `false`. |
| `{is_reply}` | Returns `true` if the message is a reply. |
| `{thread_id}` | A unique ID for the conversation thread. |
| `{parent_msgnum}` | The message number of the post being replied to. |
| `{depth}` | The depth of the message in the conversation (0 for original posts). |
| `{length}` | The number of characters in the message. |
| `{word_count}` | The number of words in the message text. |
| `{size}` | The readable size of the message (e.g., `1.2 KB`). |
| `{flags}` | Short indicators (e.g., `*` for private, `@` for attachments). |
| `{indent}` | Spaces and symbols used for organizing conversations on the screen. |
| `{reply_count}` | The number of direct replies to this message. |
| `{thread_size}` | The total number of messages in this conversation. |

### Attachments
| Variable | Description |
| :--- | :--- |
| `{attachments}` | A list of all attachment filenames. |
| `{attachment_count}` | The number of files attached to the message. |

## Troubleshooting

- **If a file will not open:** If `pyqwk` cannot open an archive, install `unzip`. If it still fails, unzip the file manually and run `qwk` on the `messages.dat` file inside.
- **If characters look wrong:** If you see incorrect characters, use the `--encoding` flag (for example, `--encoding cp850`).
- **If options do not work together:** Some options cannot be used together:
  - You cannot use `--oneline` and `--individual-files` at the same time.
  - You cannot use `--threaded` with `eml` or `maildir` formats.
- **If you get folder errors:** When you save messages as individual files, or when you use the `eml` or `maildir` formats, the output path (`-o` or `--output`) must be a folder or a compressed archive (such as `.zip`, `.tar.gz`, `.tar.bz2`, or `.tgz`). If you provide a regular file path (like `.txt` or `.html`) for these multi-file formats, the tool will show an error.

## Contributing

We welcome your contributions!

You can set up your development environment and run tests using standard Python tools or Poetry.

### Using Standard Python Tools

1. Install development tools:
   ```bash
   python -m pip install -e . pytest pytest-mock pytest-cov
   ```
2. Run tests:
   ```bash
   python -m pytest
   ```

### Using Poetry (Alternative)

1. Install dependencies and development tools:
   ```bash
   poetry install
   ```
2. Run tests:
   ```bash
   poetry run pytest
   ```

### Headless Testing

If you are running the test suite on a headless Linux system (such as in a CI/CD environment or a remote server without an active display), you must run tests using `xvfb-run`.

This requires the `xvfb` (X virtual framebuffer) system package to be installed on your operating system.

**Prerequisites:**

Install the system package based on your Linux distribution:
- **Ubuntu/Debian:** `sudo apt install xvfb`
- **Fedora/RHEL:** `sudo dnf install xorg-x11-server-Xvfb`
- **Arch Linux:** `sudo pacman -S xorg-server-xvfb`

1. Install the headless Python dependencies:
   ```bash
   python -m pip install mss Pillow
   ```
2. Run the tests:
   ```bash
   xvfb-run -a python3 -m pytest
   ```
