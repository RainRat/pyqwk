# pyqwk

pyqwk converts message archives into modern, readable formats like HTML, Markdown, and SQLite. It supports many file types, including QWK, ZIP, JSON, CSV, mbox, EML, and more.

## What are QWK and REP files?

QWK files were created in the 1980s for Bulletin Board Systems (BBS). Users downloaded their messages in a single "packet," read them offline, and then uploaded their replies in a `.REP` packet.

pyqwk helps you open these archives and convert them into modern, readable formats.

## Features

- **Support many formats:** Import and export between QWK, JSON, HTML, Markdown, mbox, and more.
- **Group conversations:** Use "threading" to group replies and follow discussions easily.
- **Clean content:** Automatically remove signatures, old quotes, and attachments.
- **Protect privacy:** Hide personal information or private messages.
- **Process many files:** Convert several archives at once or merge them into one file.
- **Preview changes:** Use "Dry Run" mode to see results before writing any files.
- **Read messages:** Use the built-in graphical reader to browse archives without converting them.

## Prerequisites

### Required
- **Python 3.10** or newer.

### Optional
- **Tkinter:** Needed for the graphical reader. Most Python installations already have it. Linux users may need to install it:
  - **Ubuntu/Debian:** `sudo apt install python3-tk`
  - **Fedora:** `sudo dnf install python3-tkinter`
  - **Arch Linux:** `sudo pacman -S tk`
- **tqdm:** Adds a progress bar. Install with: `python -m pip install tqdm`
- **unzip:** Helps open older archives. Install it if `pyqwk` cannot open your file:
  - **Ubuntu/Debian/Fedora:** `sudo apt install unzip` or `sudo dnf install unzip`
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
- **Search:** Find messages by keyword or use "Regex" for advanced patterns. Cycle through matches with **F3** or **Shift + F3**. You can also right-click any highlighted text to search for it instantly.
- **Attachments:** Click attachment links in the header to save files. Use **File > Extract All Attachments...** to save all files from your current view.
- **Filtering:** Narrow your view by BBS, conference, author, or recipient. You can also filter for private messages or messages with attachments.
- **Context Menus:** Right-click a message to copy its details or filter the view by its author or conference.
- **Exporting:** Save your current filtered view to any format (HTML, Markdown, JSON, etc.).
- **Viewing Options:** Use "Clean" view to hide signatures and quotes. Use "Remove Colors" to strip ANSI color codes.
- **Statistics:** View activity reports and charts. Click chart labels to filter the message list instantly.

**Keyboard Shortcuts:**
- **Ctrl + O**: Open an archive.
- **Ctrl + S**: Export the current view.
- **Ctrl + I**: View statistics.
- **Ctrl + F**: Jump to the search bar.
- **Ctrl + G**: Jump to a message number.
- **Ctrl + Q**: Exit.
- **F3 / Enter**: Next search match.
- **Shift + F3 / Shift + Enter**: Previous search match.
- **j / n**: Next message.
- **k / p**: Previous message.
- **Esc**: Clear search (first press) and filters (second press).

## Usage Examples

**Read an archive:**
```bash
qwk archive.qwk
```

**Save as a text file:**
```bash
qwk archive.qwk -o messages.txt
```

**Group messages by thread:**
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

**Use custom filenames:**
```bash
qwk archive.qwk --individual-files --filename-pattern "{date}_{author}_{subject}" -o output_folder/
```

**Merge archives and remove duplicates:**
```bash
qwk archive1.qwk archive2.qwk --merge --unique -o combined.mbox
```

**Clean up messages (removes signatures and quotes):**
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

## Filtering & Searching

**Filter by Conference:**
```bash
qwk archive.qwk -C "General Chat"
```

**Filter by BBS:**
```bash
qwk my_archives/ --bbs "The Digital Horizon"
```

**Filter by Person:**
```bash
qwk archive.qwk --from "Sysop" --to "Alice"
```

**Keyword Search:**
```bash
qwk archive.qwk --search "BBS"
```

**Filter by Date:**
```bash
qwk archive.qwk --after 2023-01-01 --before 2023-12-31
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

Use `pyqwk` in your own Python projects:

```python
import logging
from pyqwk.core import load_data, parse_messages, process_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pyqwk")

# Load the archive
# file_data can be raw data or a list of messages
file_data, board_dict = load_data("archive.qwk", logger)

# Parse raw data if needed
if isinstance(file_data, list):
    messages = file_data
else:
    messages = parse_messages(file_data, None)

# Process messages
for msg in messages:
    # Remove signatures and quotes
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
| `-i`, `--individual-files` | Save each message as a separate file. |
| `-F, --format` | Set output format (html, json, markdown, etc.). |
| `-T`, `--threaded` | Group replies into conversations. |
| `--clean` | Remove signatures, quotes, and attachments. |
| `-x, --extract-attachments` | Save attachments to a folder. |
| `-r, --redact-pii` | Hide emails and phone numbers. |
| `-E, --encoding` | Set text encoding (default is `cp437`). |
| `-S, --search` | Search for keywords. |
| `--stats` | Show message statistics and exit. |
| `--dry-run` | Preview actions without writing files. |

Run `qwk --help` for all options.

## Troubleshooting

- **Unsupported Compression:** If `pyqwk` cannot open an archive, install `unzip`. If it still fails, unzip the file manually and run `qwk` on the `messages.dat` file inside.
- **Incorrect Text:** If you see incorrect characters, use the `--encoding` flag (for example, `--encoding cp850`).
- **Conflicting Options:** Some options cannot be used together, such as `--threaded` and `--individual-files`.

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
