# pyqwk

pyqwk converts message archives into modern, readable formats like HTML, Markdown, and SQLite. It supports many file types, including QWK, ZIP, TAR, JSON, CSV, mbox, EML, and more.

## What are QWK and REP files?

QWK files were created in the 1980s for Bulletin Board Systems (BBS). Users downloaded their messages in a single "packet," read them offline, and then uploaded their replies in a `.REP` packet.

Inside these packets, messages are organized into **Conferences**. You can think of a Conference as a modern forum, channel, or newsgroup dedicated to a specific topic.

pyqwk helps you open these archives and convert them into modern, readable formats.

## Features

- **Supports many formats:** Import and export between QWK, JSON, JSONL, CSV, XML, RSS, SQLite, mbox, EML, Markdown, HTML, and Plain Text.
- **Groups conversations:** Group replies into conversations to follow discussions easily.
- **Cleans content:** Automatically remove signatures, old quotes, attachments, and color codes.
- **Protects privacy:** Hide personal information or private messages.
- **Processes many files:** Convert several archives at once or merge them into one file.
- **Previews changes:** Use "Dry Run" mode to see results before writing any files.
- **Reads messages:** Use the built-in graphical reader to browse archives without converting them.

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
- **Tkinter:** Needed for the graphical reader. Most Python installations already have it. Linux users may need to install it:
  - **Ubuntu/Debian:** `sudo apt install python3-tk`
  - **Fedora:** `sudo dnf install python3-tkinter`
  - **Arch Linux:** `sudo pacman -S tk`
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

Install `pyqwk` to use it from any folder.

1. Open your terminal in the `pyqwk` folder.
2. Install the package:
   ```bash
   python -m pip install .
   ```
3. Use the `qwk` command:
   ```bash
   qwk archive.qwk
   ```
4. Launch the graphical reader:
   ```bash
   qwk-gui
   ```

*Note: You can also run the reader without installing:*
```bash
python -m pyqwk.gui
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
- **Search:** Find messages by keyword or use "Regex" for advanced patterns. You can easily cycle through matches with **F3** or **Shift + F3**, and the reader will automatically move to the next or previous message when you reach the end of the current one. You can also right-click any highlighted text to search for it instantly.
- **Attachments:** Click attachment links in the header to save files. Use **File > Extract All Attachments...** to save all files from your current view.
- **Filtering:** Narrow your view by BBS, conference, author, or recipient. Use the **Exclude** field to hide messages matching specific keywords. You can also filter for private messages or messages with attachments.
- **Context Menus:** Right-click a message to copy its details or filter the view by its author or conference.
- **Exporting:** Save your current filtered view to any format (HTML, Markdown, JSON, etc.).
- **Viewing Options:** Use "Clean" view to hide signatures, quotes, attachments, and color codes. Use "Remove Colors" to strip only ANSI color codes. Use "Embed Attachments" to include images directly in messages.
- **Statistics:** View activity reports and charts. Click chart labels to filter the message list instantly.

**Keyboard Shortcuts:**

**Archive & Stats**
- **Ctrl + O**: Open an archive.
- **Ctrl + S**: Export the current filtered view.
- **Ctrl + I**: View archive statistics and reports.
- **Ctrl + Q**: Exit the application.

**Search & Filters**
- **Ctrl + F** or **/**: Jump to the search bar.
- **F3**: Find the next search match.
- **Shift + F3**: Find the previous search match.
- **Enter**: Find the next match when the search bar is focused.
- **Shift + Enter**: Find the previous match when the search bar is focused.
- **Esc**: Clear the search on the first press and all filters on the second press.

**Navigation**
- **j** or **n**: Move to the next message.
- **k** or **p**: Move to the previous message.
- **Space** or **PgDn**: Scroll down or move to the next message.
- **Shift + Space**, **BackSpace**, or **PgUp**: Scroll up or move to the previous message.
- **Ctrl + G**: Jump to a specific message number.
- **r**: Select a random message.
- **[** or **]**: Move to the previous or next conference.

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

**Find Content:**
```bash
# Only messages with links
qwk archive.qwk --has-links

# Only messages with phone numbers
qwk archive.qwk --has-phones

# Only messages with email addresses
qwk archive.qwk --has-emails

# Only messages with color codes
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
```

**Filter by Message Number:**
```bash
qwk archive.qwk --msgnum 100-200
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
| `-i`, `--individual-files` | Save each message as a separate file. |
| `-F, --format` | Set output format (html, json, markdown, etc.). |
| `-m, --merge` | Combine multiple archives into one file. |
| `-u, --unique` | Remove duplicate messages during a merge. |
| `-T`, `--threaded` | Group replies into conversations. |
| `--clean` | Remove signatures, quotes, attachments, and color codes. |
| `-x, --extract-attachments` | Save attachments to a folder. |
| `--embed-attachments` | Include image attachments directly in HTML files. |
| `--organize-attachments` | Organize extracted attachments into subfolders. |
| `--organize` | Organize individual files into subfolders by conference. |
| `--organize-by-date` | Organize files into folders by year and month. |
| `--organize-by-bbs` | Organize archives into folders named after the BBS. |
| `--organize-by-author` | Organize files into folders by author name. |
| `--organize-by-to` | Organize files into folders by recipient name. |
| `--organize-by-subject` | Organize files by message subject. |
| `--organize-pattern` | Set a custom folder structure for individual files. |
| `--sort` | Sort results by field (date, author, subject, etc.). |
| `-r, --redact-pii` | Hide personal info like emails and phone numbers. |
| `-p, --private` | Include private messages. |
| `--mine` | Show messages sent to or from your user name. |
| `--my-name` | Set your name for the `--mine` filter and QWK exports. |
| `--has-attachments` | Only show messages that have attachments. |
| `--has-links` | Only show messages that contain web links. |
| `--has-emails` | Only show messages that contain email addresses. |
| `--has-phones` | Only show messages that contain phone numbers. |
| `--has-ansi` | Only show messages that contain color codes. |
| `-A, --strip-ansi` | Remove color codes and other formatting symbols. |
| `-H, --headers-only` | Show only the message headers. |
| `-E, --encoding` | Set text encoding (default is `cp437`). |
| `-S, --search` | Search for keywords. |
| `-C, --conference` | Show messages from a specific conference. |
| `--bbs` | Show messages from a specific BBS. |
| `-f, --from` | Show messages from a specific author. |
| `--to` | Show messages to a specific recipient. |
| `-s, --subject` | Show messages with a specific word in the subject. |
| `--body` | Search for keywords specifically in the message body. |
| `--exclude` | Exclude messages matching a keyword in any field. |
| `--exclude-from` | Exclude messages from specific authors. |
| `--exclude-to` | Exclude messages sent to specific recipients. |
| `--exclude-subject` | Exclude messages by subject keywords. |
| `--exclude-conference` | Exclude messages from specific conferences. |
| `--exclude-bbs` | Exclude messages from specific BBSes. |
| `--after` | Show messages sent on or after a date (YYYY-MM-DD). |
| `--before` | Show messages sent on or before a date (YYYY-MM-DD). |
| `--on-this-day` | Show messages from the same month and day. |
| `-N, --msgnum` | Show specific message numbers or ranges. |
| `-L, --limit` | Stop after a specific number of matching messages. |
| `-K, --skip` | Skip a specific number of matching messages. |
| `--regex` | Use regular expressions for search and filters. |
| `--reverse` | Reverse the sorting order. |
| `--min-length` | Show messages with at least this many characters. |
| `--max-length` | Show messages with at most this many characters. |
| `--toc` | Add a table of contents to the output. |
| `-1, --oneline` | Show a one-line summary of each message. |
| `--oneline-pattern` | Set a custom pattern for one-line summaries. |
| `-I, --info` | Show a summary of the archive and exit. |
| `--stats` | Show message statistics and exit. |
| `--merge-stats` | Show a single merged report for multiple archives. |
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
| `{my_name}` | The user name (either from archive information or your override). |

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
| `{length}` | The number of characters in the message. |
| `{size}` | The readable size of the message (e.g., `1.2 KB`). |
| `{flags}` | Short indicators (e.g., `*` for private, `@` for attachments). |
| `{indent}` | Spaces and symbols used for organizing conversations on the screen. |

### Attachments
| Variable | Description |
| :--- | :--- |
| `{attachments}` | A list of all attachment filenames. |
| `{attachment_count}` | The number of files attached to the message. |

## Troubleshooting

- **If a file will not open:** If `pyqwk` cannot open an archive, install `unzip`. If it still fails, unzip the file manually and run `qwk` on the `messages.dat` file inside.
- **If characters look wrong:** If you see incorrect characters, use the `--encoding` flag (for example, `--encoding cp850`).
- **If options do not work together:** Some options cannot be used together, such as `--threaded` and `--individual-files`.

## Contributing

We welcome your contributions!

1. Install development tools:
   ```bash
   pip install -e . pytest pytest-mock pytest-cov
   ```
2. Run tests:
   ```bash
   python -m pytest
   ```
