# pyqwk

pyqwk is a tool to convert old `.QWK` mail archives (from the BBS era) into modern formats like Text, HTML, JSON, XML, CSV, mbox, and SQLite.

## Features

- **Multiple Formats:** Export to Text, HTML, JSON, XML, Markdown, CSV, mbox, or SQLite.
- **Conversation Threading:** Group replies together to follow discussions easily.
- **Content Cleaning:** Automatically remove signatures, old quotes, and binary attachments.
- **Privacy:** Redact personal information and handle private messages.
- **Batch Processing:** Convert many archives at once or merge them into a single file.
- **Built-in Reader:** A simple graphical interface to read messages without converting them. It includes search and filtering tools.

## Prerequisites

- **Python 3.10** or newer is required.
- (Optional) **Tkinter** is required for the graphical reader. It is usually included with Python, but Linux users may need to install it separately (for example: `sudo apt install python3-tk`).
- (Optional) Install the **tqdm** package for a progress bar: `pip install tqdm`

## Quick Start

Run the script on any QWK archive:
```bash
python qwk.py archive.qwk
```

## Installation

You can install `pyqwk` to use it from any folder on your computer.

1. Open your terminal in the project folder.
2. Install the package:
   ```bash
   pip install .
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
*Tip: Use `--threaded` to include standard email threading headers for better organization in your mail app.*

**Convert to JSON for your own scripts:**
```bash
qwk archive.qwk --format json -o data.json
```

**Save as Markdown:**
```bash
qwk archive.qwk --format markdown -o messages.md
```

**Show detailed archive statistics:**
```bash
qwk archive.qwk --stats
```

**Process a whole folder of archives:**
```bash
qwk my_archives/ -o output_folder/
```
*Tip: The output folder will be created automatically if it does not exist.*

**Merge multiple archives into one file:**
```bash
qwk archive1.qwk archive2.qwk --merge -o combined.mbox
```

**Clean up messages (removes signatures, quotes, and binaries):**
```bash
qwk archive.qwk --clean -o clean.txt
```

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

*Note for Windows users: If you use symbols like `*` (wildcards) to select multiple files, use PowerShell instead of the standard Command Prompt.*

## Filtering & Searching

**Filter by Conference:**
Find messages in a specific conference by its name or number.
```bash
qwk archive.qwk -C "General Chat"
qwk archive.qwk -C 123
```

**Filter by Person:**
Find messages from or to a specific person.
```bash
qwk archive.qwk --from "Sysop"
qwk archive.qwk --to "Alice"
```

**Keyword Search:**
Search for keywords in the author, subject, and message body.
```bash
qwk archive.qwk --search "BBS"
```

**Filter by Date:**
Find messages from a specific date range (use YYYY-MM-DD).
```bash
qwk archive.qwk --after 2023-01-01 --before 2023-12-31
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
file_data, board_dict = load_data("archive.qwk", logger)

# Loop through all messages
for msg in parse_messages(file_data, None):
    # Clean the message content (remove signatures, quotes, and binaries)
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
| `-F, --format [type]` | Choose format: `text`, `html`, `json`, `xml`, `markdown`, `csv`, `mbox`, `sqlite`. |
| `-T`, `--threaded` | Group replies together into conversations. |
| `-m`, `--merge` | Combine multiple inputs into a single output file. |
| `-S`, `--search [term]` | Search for a keyword in author, subject, and message text. |
| `-C`, `--conference [id]` | Only show messages from this conference name or number. |
| `--clean` | Automatically remove signatures, quotes, binary data, and color codes. |
| `-r, --redact-pii` | Hide personal info like email addresses and phone numbers. |
| `-H, --headers-only` | Extract only message headers and skip the message body. |
| `-E, --encoding [name]` | Set the text character set (default is `cp437`). |
| `-p`, `--private` | Include private messages in the output. |
| `-n`, `--noheader` | Do not include the message header info in the text. |
| -A, --strip-ansi | Remove color codes and other formatting symbols. |
| `--separator [type]` | How to separate messages (`auto`, `none`, `dashes`, `blank`). |
| `-v`, `--verbose` | Show more details like conference names and message numbers. |
| `-q`, `--quiet` | Hide the progress bar and extra info. |
| `-L, --limit [num]` | Stop after processing this many messages. |
| `-I, --info` | Show a summary of the archive and exit. |
| `--stats` | Show detailed statistics about the messages and exit. |

Run `qwk --help` to see all available options.

## Troubleshooting

- **Unsupported Compression:** Some old QWK packets use special ZIP methods. If you get an error, unzip the file manually and run `qwk` on the `messages.dat` file inside.
- **Strange Characters:** If messages show incorrect characters, use the `--encoding` flag (e.g., `--encoding cp850`) to match the original BBS's character set.
- **Compatibility:** You cannot use `--threaded` and `--individual-files` at the same time.

## Contributing

We welcome your contributions! To help develop `pyqwk`:

1. Install the development and testing dependencies:
   ```bash
   pip install pytest pytest-mock
   ```
2. Run the tests to make sure everything is working:
   ```bash
   python -m pytest
   ```
