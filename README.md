# pyqwk

pyqwk is a tool to convert `.QWK`, `.REP`, `.JSON`, `.CSV`, `.XML`, SQLite, `.mbox`, and `.eml` mail archives into modern formats like Text, HTML, JSON, XML, Markdown, CSV, mbox, EML, and SQLite.

## What are QWK and REP files?

QWK is a file format created in the late 1980s for Bulletin Board Systems (BBS). In the days before the modern internet, it allowed users to download all their new messages in a single "packet." They could then disconnect their phone line, read the messages at their own pace, and write replies without keeping the BBS's phone line busy. Once finished, they would upload their replies back to the BBS in a `.REP` packet.

Today, these files are valuable pieces of digital history. `pyqwk` helps you open both downloaded archives and your own sent replies, converting them into modern, easy-to-read formats.

## Features

- **Multiple Formats:** Export to Text, HTML, JSON, XML, Markdown, CSV, mbox, EML, or SQLite. Import from QWK, REP, JSON, CSV, XML, SQLite, mbox, or EML.
- **Conversation Threading:** Group replies together to follow discussions easily.
- **Content Cleaning:** Automatically remove signatures, old quotes, and attachments like images.
- **Privacy:** Hide personal information and handle private messages.
- **Process many files:** Convert many archives at once or merge them into a single file.
- **Dry Run Mode:** Preview the results of a conversion without writing any files to disk.
- **Built-in Reader:** A simple graphical interface to read messages without converting them. It includes search and filtering tools.

## Prerequisites

### Required
- **Python 3.10** or newer.

### Optional
- **Tkinter**: Needed for the graphical reader. Most Python installations include it. If you use Linux, you may need to install it manually:
  - **Ubuntu/Debian:** `sudo apt install python3-tk`
  - **Fedora:** `sudo dnf install python3-tkinter`
  - **Arch Linux:** `sudo pacman -S tk`
- **tqdm**: Provides a progress bar when processing many messages. Install it with: `python -m pip install tqdm`
- **unzip**: A system tool used to handle older archives with special compression. If `pyqwk` cannot open a file with Python's built-in tools, it will try to use `unzip`.
  - **Ubuntu/Debian:** `sudo apt install unzip`
  - **Fedora:** `sudo dnf install unzip`
  - **Arch Linux:** `sudo pacman -S unzip`
  - **macOS:** `brew install unzip`
  - **Windows:** Install via [Git Bash](https://git-scm.com/downloads) or [GnuWin32](http://gnuwin32.sourceforge.net/packages/unzip.htm).

## Quick Start

Run the script on any supported message archive:
```bash
python qwk.py archive.qwk
python qwk.py replies.rep
python qwk.py archive.json
python qwk.py archive.csv
python qwk.py archive.xml
python qwk.py archive.mbox
python qwk.py archive.eml
python qwk.py messages.db
```

## Installation

You can install `pyqwk` to use it from any folder on your computer.

1. Open your terminal in the project folder.
2. Install the package:
   ```bash
   python -m pip install .
   ```
3. Now you can use the `qwk` command anywhere:
   ```bash
   qwk archive.qwk
   ```
4. Or launch the graphical reader:
   ```bash
   qwk-gui
   ```

*Note: You can also run the reader directly without installing:*
```bash
python -m pyqwk.gui
```

## Graphical Reader

If you prefer a visual interface, you can use the built-in reader. It allows you to browse conferences, search for messages, and follow threaded conversations. It supports all input formats (QWK, REP, JSON, CSV, XML, SQLite, mbox, and EML).

**To start the reader:**
```bash
# Open the reader and select a file from the menu
qwk-gui

# Or open a specific file immediately
qwk-gui archive.qwk
qwk-gui archive.csv
qwk-gui archive.xml
qwk-gui archive.mbox
qwk-gui archive.eml
```

**Key Features:**
- **Search:** Quickly find messages by keyword. Use the **Regex** checkbox to search with advanced patterns (regular expressions). Results are highlighted in the text. You can also highlight any text in a message, right-click, and select **Search for [Selection]** to instantly find related messages.
- **Filtering:** View messages from specific conferences, include private messages, filter by the presence of attachments, or only show messages from/to yourself.
- **Context Menus:** Right-click on any message in the list to copy its metadata (Subject, From, To) or instantly filter the entire archive by that author or conference. You can also right-click in the message text to copy selected sections.
- **Exporting:** Save your current filtered and sorted view to any supported format (HTML, Markdown, JSON, etc.).
- **Viewing Options:** Toggle between **Clean** view (removes formatting), **Hide Personal Info** (hides emails and phone numbers), and **Remove Colors**.
- **Threading:** Group replies together to follow the flow of a conversation.
- **Sorting:** Click on column headers (like "Num" or "Date") to sort the message list.
- **Statistics:** View detailed activity reports, top authors, and temporal distributions for the current archive and filters.

**Keyboard Shortcuts:**
- **Ctrl + O**: Open any supported message archive.
- **Ctrl + S**: Export the current view to a file.
- **Ctrl + I**: View archive statistics.
- **Ctrl + F**: Jump to the search bar.
- **Ctrl + G**: Jump to a specific message number.
- **Ctrl + Q**: Exit the application.
- **j / k** or **n / p**: Move to the next or previous message in the list.
- **Esc**: Clear the search filter and return focus to the message list. This works from anywhere in the application.
- **Enter**: Execute the search immediately and move focus to the message list.

## Usage Examples

**Read an archive on your screen:**
```bash
qwk archive.qwk
```

**Save as a text file:**
```bash
qwk archive.qwk -o messages.txt
```

**Group messages by thread (conversations):**
```bash
qwk archive.qwk --threaded -o messages.txt
```

**Create a browsable HTML file:**
```bash
qwk archive.qwk --format html -o messages.html
```

**Convert to an mbox file (for email apps):**
```bash
qwk archive.qwk --format mbox -o messages.mbox
```
*Tip: Use `--threaded` to help your mail app group messages into conversations.*

**Convert to EML files (individual messages for mail apps):**
```bash
qwk archive.qwk --format eml -o ./output_folder/
```
*Tip: This automatically saves each message as a separate `.eml` file with a human-readable name.*

**Convert to JSON for your own scripts:**
```bash
qwk archive.qwk --format json -o data.json
```

**Show a one-line summary for each message (great for quick scanning):**
```bash
qwk archive.qwk --oneline
```

**Save as Markdown:**
```bash
qwk archive.qwk --format markdown -o messages.md
```

**Save each message as a separate file:**
```bash
qwk archive.qwk --individual-files -o output_folder/
```

**Save each message as a separate file organized by conference:**
```bash
qwk archive.qwk --individual-files --organize -o output_folder/
```
*Tip: This creates subfolders for each conference (e.g., `001-general_chat/`) to keep the output tidy.*

**Show detailed archive statistics:**
```bash
qwk archive.qwk --stats
```

**Show merged statistics for multiple archives:**
```bash
qwk archive1.qwk archive2.qwk --stats --merge-stats
```

**Process a whole folder of archives:**
```bash
qwk my_archives/ -o output_folder/
```
*Tip: The output folder will be created automatically if it does not exist.*

**Organize archives into folders by BBS name:**
```bash
qwk my_archives/ --organize-by-bbs
```
*Tip: This automatically sorts your archives into folders named after the BBS they came from.*

**Merge multiple archives into one file (removing any duplicate messages):**
```bash
qwk archive1.qwk archive2.qwk --merge --unique -o combined.mbox
```

**Clean up messages (removes signatures, quotes, and attachments):**
```bash
qwk archive.qwk --clean -o clean.txt
```

**Extract attachments (like images or files) to a folder:**
```bash
qwk archive.qwk --extract-attachments -o output/
```
*Tip: This finds UUE, Base64, and yEnc files hidden in messages and saves them to an `attachments/` subfolder.*

**Hide personal information (emails and phone numbers):**
```bash
qwk archive.qwk --redact-pii -o safe.txt
```

**Export to a database (SQLite):**
```bash
qwk archive.qwk --format sqlite -o messages.db
```

**Export to a spreadsheet-friendly format (CSV):**
```bash
qwk archive.qwk --format csv -o messages.csv
```

**Import from a CSV file (spreadsheet):**
```bash
qwk messages.csv -o updated.html
```

**Import from an XML file:**
```bash
qwk archive.xml -o messages.html
```

*Note for Windows users: If you use symbols like `*` (wildcards) to select multiple files, use PowerShell instead of the standard Command Prompt.*

## Filtering & Searching

**Filter by Conference:**
Find messages in a specific conference by its name or number.
```bash
qwk archive.qwk -C "General Chat"
qwk archive.qwk -C 123
```

**Filter by BBS:**
Find messages from a specific BBS by its name or ID.
```bash
qwk my_archives/ --bbs "The Digital Horizon"
qwk my_archives/ --bbs "DIGIHORZ"
```

**Filter by Person:**
Find messages from or to a specific person.
```bash
qwk archive.qwk --from "Sysop"
qwk archive.qwk --to "Alice"
```

**Keyword Search:**
Search for keywords in the author, recipient, subject, and message body. Results are highlighted in the terminal for easy identification.
```bash
qwk archive.qwk --search "BBS"
```

**Regular Expression Search:**
Search using advanced patterns (regex) by adding the `--regex` flag.
```bash
qwk archive.qwk --search "BBS|Board" --regex
```

**Processing in Chunks:**
Skip a number of messages or limit the total results. This is useful for processing large archives in chunks.
```bash
# Skip the first 100 messages and process the next 50
qwk archive.qwk --skip 100 --limit 50
```

**Rich Terminal Output:**
When viewing messages in your terminal, pyqwk automatically uses colors to make them easier to read. Message headers are bolded, and search terms are highlighted using inverted colors. This only applies to terminal output; file exports remain clean.

**Sorting Results:**
You can sort the output by various fields such as date, author, or subject.
```bash
# Show the 10 most recent messages
qwk archive.qwk --sort date --reverse --limit 10
```

**Filter by Date:**
Find messages from a specific date range (use YYYY-MM-DD).
```bash
qwk archive.qwk --after 2023-01-01 --before 2023-12-31
```

**Filter by Message Number:**
Find specific messages or ranges of messages by their BBS number.
```bash
qwk archive.qwk --msgnum 100
qwk archive.qwk --msgnum 100-200
qwk archive.qwk --msgnum 10,20,50-100
```

**Filter by Attachments:**
Only show messages that contain attachments (UUE, yEnc, Base64).
```bash
qwk archive.qwk --has-attachments
```

**Filter Your Own Messages:**
Only show messages from or to your user name (as defined in the archive's information).
```bash
qwk archive.qwk --mine
```

**Filter by Anniversary (On This Day):**
Only show messages sent on this same month and day in any year. This is a great way to explore what was happening on the BBS in previous years.
```bash
qwk archive.qwk --on-this-day
```

**Dry Run:**
Preview exactly how many messages match your filters and how many files will be created without actually making any changes.
```bash
qwk archives/ --search "BBS" --dry-run
```

## Library Usage

You can use `pyqwk` in your own Python projects:

```python
import logging
from pyqwk.core import load_data, parse_messages, process_message

# Configure logging to see progress and warnings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pyqwk")

# Load the archive and conference list
# file_data can be a bytearray (for QWK/REP) or a list of messages (for JSON/CSV/etc.)
file_data, board_dict = load_data("archive.qwk", logger)

# Determine if we need to parse raw data or use pre-parsed messages
if isinstance(file_data, list):
    messages = file_data
else:
    messages = parse_messages(file_data, None)

# Loop through all messages
for msg in messages:
    # Clean the message content (remove signatures, quotes, and attachments)
    clean_text = process_message(
        msg.text,
        truncate_signatures=True,
        cut_quoting=True,
        binaries_removal=True,
        redact_pii=False
    )

    # Get the conference name from the board dictionary
    conf_name = board_dict.get(msg.confnum, f"Conference {msg.confnum}")

    print(f"[{conf_name}] From: {msg.header.msgfrom}")
    print(f"Subject: {msg.header.msgsubject}")
    print(clean_text)
    print("-" * 40)
```

## Common Options

| Flag | Description |
| :--- | :--- |
| `-o`, `--output [path]` | Where to save the output. Prints to terminal by default. |
| `-i`, `--individual-files` | Save each message as a separate file. |
| `--organize` | Organize individual files into subfolders by conference. |
| `--organize-by-bbs` | Organize archives into folders named after the BBS. |
| `-F, --format [type]` | Choose format: `text`, `html`, `json`, `xml`, `markdown`, `csv`, `mbox`, `eml`, `sqlite`. |
| `-j`, `--json` | A shortcut for `--format json`. |
| `-T`, `--threaded` | Group replies together into conversations. |
| `-1`, `--oneline` | Show each message as a single-line summary (Conference, Date, From, To, Subject). |
| `--toc` | Include a table of contents and a summary of the archive in the output. |
| `-m`, `--merge` | Combine multiple inputs into a single output file. |
| `-u`, `--unique` | Only include unique messages (removes duplicates when merging archives). |
| `-S`, `--search [term]` | Search for a keyword in author, recipient, subject, and message text. |
| `--regex` | Use regular expressions for searching and filtering. |
| `-C`, `--conference [id]` | Only show messages from this conference name or number (can be used multiple times). |
| `--bbs [name/id]` | Only show messages from this BBS name or ID (can be used multiple times). |
| `--clean` | Automatically remove signatures, quotes, attachments, and color codes. |
| `-x, --extract-attachments` | Extract attachments (UUE, Base64, yEnc) to an `attachments/` folder. |
| `-t, --truncate-signatures` | Stop reading a message when a signature is found. |
| `-c, --cut-quoting` | Remove text quoted from earlier messages. |
| `-b, --binaries-removal` | Remove attachments such as images or programs. |
| `-r, --redact-pii` | Hide personal information like email addresses and phone numbers. |
| `-H, --headers-only` | Show only message headers and skip the message text. |
| `-E, --encoding [name]` | Set the text format (default is `cp437`). |
| `-p`, `--private` | Include private messages in the output. |
| `-f, --from [name]` | Only show messages from this author (can be used multiple times). |
| `--to [name]` | Only show messages to this recipient (can be used multiple times). |
| `-s, --subject [text]` | Only show messages with this word in the subject (can be used multiple times). |
| `--after [date]` | Only show messages from this date or later (YYYY-MM-DD). |
| `--before [date]` | Only show messages from this date or earlier (YYYY-MM-DD). |
| `-N, --msgnum [list]` | Only show messages with these numbers (e.g., '100', '200-300', '10,20,50-100'). |
| `-n, --noheader` | Do not include the message header information in the text. |
| `-A, --strip-ansi` | Remove color codes and other formatting symbols. |
| `--separator [type]` | How to separate messages (`auto`, `none`, `dashes`, `blank`). |
| `-v`, `--verbose` | Show more details like conference names and message numbers. |
| `-q`, `--quiet` | Hide the progress bar and extra information. |
| `--dry-run` | Preview actions without writing files to disk. |
| `-l, --loglevel [level]` | Set how much detail to show in logs (DEBUG, INFO, WARNING, ERROR, CRITICAL). |
| `-L, --limit [num]` | Stop after processing this many messages. |
| `-K, --skip [num]` | Skip the first this many matching messages. |
| `--sort [field]` | Sort results by: `date`, `author`, `to`, `subject`, `num`, `conference`, or `bbs`. |
| `--reverse` | Reverse the order of the output. |
| `--has-attachments` | Only show messages that contain attachments (UUE, yEnc, Base64). |
| `--mine` | Only show messages from or to your user name. |
| `--on-this-day` | Only show messages sent on this same month and day in any year. |
| `-I, --info` | Show a summary of the archive and exit. Use `--format json` for JSON output. |
| `--stats` | Show detailed statistics about the messages and exit. Use `--format json` for JSON output. |
| `--merge-stats` | Show a single merged report when analyzing multiple archives with `--stats`. |
| `-V, --version` | Show the version number and exit. |

Run `qwk --help` to see all available options.

## Troubleshooting

- **Unsupported Compression:** Some old QWK or REP packets use special ZIP methods. If you get an error, unzip the file manually and run `qwk` on the `messages.dat` (or `reply.dat`) file inside.
- **Strange Characters:** If messages show incorrect characters, use the `--encoding` flag (e.g., `--encoding cp850`) to match the original BBS's text format.
- **Option Conflict:** Some options cannot be used together. You will get an error if you try to use:
  - `--threaded` and `--individual-files`
  - `--oneline` and `--individual-files`
  - `--threaded` and `--format eml`

## Contributing

We welcome your contributions! To help develop `pyqwk`:

1. Install the development and testing dependencies:
   ```bash
   pip install -e . pytest pytest-mock pytest-cov
   ```
2. Run the tests to make sure everything is working:
   ```bash
   python -m pytest
   ```
