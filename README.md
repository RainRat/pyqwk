# pyqwk

pyqwk is a simple tool to convert `.QWK` mail archives (from the BBS era) into readable formats like Text, HTML, JSON, and XML.

## Quick Start

1.  **Download** this repository.
2.  **Run the script** (requires Python 3.10+):
    ```bash
    python qwk.py archive.qwk
    ```

*Tip: Run `pip install tqdm` to see a progress bar.*

## Installation (Optional)

You can install `pyqwk` to use the `qwk` command from any folder.

1.  Open your terminal in the project folder.
2.  Install the package:
    ```bash
    pip install .
    ```
3.  Now you can use the command-line tool anywhere:
    ```bash
    qwk archive.qwk
    ```
4.  Or launch the GUI reader:
    ```bash
    qwk-gui
    ```

*Note: If you don't want to install the package, you can run the GUI directly:*
```bash
python -m pyqwk.gui
```

## Library Usage

pyqwk can be imported as a module so you can reuse the parsing logic in your own tools:

```python
from pyqwk.core import load_data, parse_messages, process_message
```

## Usage Examples

**View an archive on screen:**
```bash
python qwk.py archive.qwk
```

**Save as a text file:**
```bash
python qwk.py archive.qwk -o messages.txt
```

**Create a browsable HTML file:**
```bash
python qwk.py archive.qwk --format html -o messages.html
```

**Convert to JSON for programming:**
```bash
python qwk.py archive.qwk --format json -o data.json
```

**Save as an mbox file:**
Perfect for importing into modern email clients.
```bash
python qwk.py archive.qwk --format mbox -o messages.mbox
```

**Export to SQLite database:**
```bash
python qwk.py archive.qwk --format sqlite -o messages.db
```

**Process multiple files:**
Save all converted files into a folder named `output`:
```bash
python qwk.py *.qwk -o output/
```
*Windows Users: Use PowerShell to support the `*.qwk` wildcard.*

## Filtering & Searching

You can filter messages to find exactly what you need.

**Filter by Conference:**
Find messages in a specific conference by name or number.
```bash
python qwk.py archive.qwk -C "General Chat"
python qwk.py archive.qwk -C 123
```

**Filter by Sender:**
Find messages from a specific person.
```bash
python qwk.py archive.qwk --from "Sysop"
```

**Filter by Subject:**
Find messages about a specific topic.
```bash
python qwk.py archive.qwk --subject "Welcome"
```

**Search Body Content:**
Search for a keyword in author, subject, and message body.
```bash
python qwk.py archive.qwk --search "BBS"
```

**Filter by Date:**
Find messages from a specific date range (inclusive). Use the `YYYY-MM-DD` format.
```bash
python qwk.py archive.qwk --after 2023-01-01 --before 2023-12-31
```

**Combine Filters:**
Find messages from "Sysop" in the "Announcements" conference.
```bash
python qwk.py archive.qwk --from "Sysop" -C "Announcements"
```

## Common Options

| Flag | Description |
| :--- | :--- |
| `-o [path]` | Where to save the output. Defaults to screen. |
| `-i` | Save each message as a separate file. |
| `--format [type]` | Output: `text`, `html`, `json`, `xml`, `csv`, `mbox`, `sqlite`. |
| `--encoding [enc]` | Set the input character encoding (default: `cp437`). |
| `-T`, `--threaded` | Group replies together into conversations. |
| `--clean` | Remove "junk" like signatures, quotes, and binary data. |
| `--redact-pii` | Hide personal info like email addresses and phone numbers. |
| `--headers-only` | Extract only headers, skipping the message body. |
| `-p`, `--private` | Include messages marked as private. |
| `-C [conf]` | Filter by conference name or number. |
| `--from [name]` | Filter by sender name. |
| `--subject [text]` | Filter by subject line. |
| `--search [text]` | Search in author, subject, and message body. |
| `--after [date]` | Filter messages on or after this date (`YYYY-MM-DD`). |
| `--before [date]` | Filter messages on or before this date (`YYYY-MM-DD`). |
| `--info` | Show a summary of the archive and exit. |

Run `python qwk.py --help` to see all options.

## Troubleshooting

*   **Unsupported Compression:** Some old QWK packets use special ZIP methods. If you get an error, unzip the file manually and run pyqwk on the `messages.dat` file:
    ```bash
    python qwk.py messages.dat
    ```
*   **Threading:** You cannot use `--threaded` (`-T`) when saving individual files (`-i`).

## Contributing

Pull requests are welcome! Please run tests before submitting:
```bash
pytest
```
