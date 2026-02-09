# pyqwk

pyqwk is a tool to convert old `.QWK` mail archives (from the BBS era) into modern formats including Text, HTML, JSON, XML, CSV, mbox, and SQLite.

## Features

- **Multiple Formats:** Export to Text, HTML, JSON, XML, Markdown, CSV, mbox, or SQLite.
- **Conversation Threading:** Group replies together to follow discussions easily.
- **Content Cleaning:** Automatically remove signatures, old quotes, and binary attachments.
- **Privacy:** Redact personal information and handle private messages.
- **Batch Processing:** Convert many archives or entire folders at once, or merge them into a single file.
- **Built-in GUI:** A simple graphical interface for reading messages without conversion.

## Quick Start

1. **Run the script** (requires Python 3.10 or newer):
   ```bash
   python qwk.py archive.qwk
   ```

*Tip: Install the `tqdm` package (`pip install tqdm`) to see a progress bar during processing.*

## Installation

You can install `pyqwk` to use it from any folder.

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

*Note: You can also run the GUI directly without installing:*
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

**Convert to JSON for your own scripts:**
```bash
qwk archive.qwk --format json -o data.json
```

**Save as Markdown:**
```bash
qwk archive.qwk --format markdown -o messages.md
```

**Process a whole folder of archives:**
```bash
qwk my_archives/ -o output_folder/
```

**Merge multiple archives into one file (with cross-archive threading):**
```bash
qwk archive1.qwk archive2.qwk --merge -o combined.mbox
```

*Note for Windows users: If you use wildcards like `*.qwk`, use PowerShell instead of the standard Command Prompt.*

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

**Search Body Content:**
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

# Load the archive
file_data, board_dict = load_data("archive.qwk", logger)

for msg in parse_messages(file_data, None):
    # Clean the message content
    clean_text = process_message(
        msg.text,
        truncate_signatures=True,
        cut_quoting=True,
        binaries_removal=True,
        redact_pii=False
    )

    print(f"From: {msg.header.msgfrom}")
    print(f"Subject: {msg.header.msgsubject}")
    print(clean_text)
```

## Common Options

| Flag | Description |
| :--- | :--- |
| `-o`, `--output [path]` | Where to save the output. Prints to terminal by default. |
| `-i`, `--individual-files` | Save each message as a separate file. |
| `--format [type]` | Choose format: `text`, `html`, `json`, `xml`, `markdown`, `csv`, `mbox`, `sqlite`. |
| `-T`, `--threaded` | Group replies together into conversations. |
| `-m`, `--merge` | Merge multiple inputs into a single output file. |
| `--clean` | Remove signatures, quotes, and binary data automatically. |
| `--redact-pii` | Hide personal info like email addresses and phone numbers. |
| `--headers-only` | Extract only message headers and skip the message body. |
| `--encoding [name]` | Set the input text encoding (default is `cp437`). |
| `-p`, `--private` | Include private messages in the output. |
| `-n`, `--noheader` | Do not include the message header info in the text. |
| `-v`, `--verbose` | Show more details like conference names and message numbers. |
| `-q`, `--quiet` | Hide the progress bar and extra info. |
| `--limit [num]` | Stop after processing this many messages. |
| `--info` | Show a summary of the archive and exit. |

Run `qwk --help` to see all available options.

## Troubleshooting

- **Unsupported Compression:** Some old QWK packets use special ZIP methods. If you get an error, unzip the file manually and run `qwk` on the `messages.dat` file inside.
- **Strange Characters:** If messages show incorrect characters, use the `--encoding` flag (e.g., `--encoding cp850`) to match the original BBS's character set.
- **Compatibility:** You cannot use `--threaded` and `--individual-files` at the same time.

## Contributing

We welcome your contributions! Please run tests before submitting a pull request:
```bash
pytest
```
