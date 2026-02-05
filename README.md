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

**Filter by Date:**
Find messages from a specific date range (format: YYYY-MM-DD).
```bash
python qwk.py archive.qwk --after 2023-01-01 --before 2023-12-31
```

**Search Body Content:**
Search for a keyword in author, subject, and message body.
```bash
python qwk.py archive.qwk --search "BBS"
```

**Combine Filters:**
Find messages from "Sysop" in the "Announcements" conference.
```bash
python qwk.py archive.qwk --from "Sysop" -C "Announcements"
```

## Common Options

| Flag | Description |
| :--- | :--- |
| `-o [file/folder]` | Where to save the output. Defaults to screen. |
| `-i` | Save each message as a separate file (cannot use with threaded). |
| `--format [type]` | Output format: `text`, `html`, `json`, `xml`, `csv`, `mbox`, `sqlite`. |
| `-T`, `--threaded` | Group replies together (ideal for reading conversations). |
| `--clean` | Clean up messages by removing signatures, quotes, and binary data. |
| `--redact-pii` | Hide personal information like email addresses and phone numbers. |
| `--headers-only` | Extract only message headers and skip the message body. |
| `--encoding [name]` | Set the input file encoding (default is `cp437`). |
| `-p`, `--private` | Include private messages. |
| `-C [conf]` | Filter by conference name or number. |
| `--from [name]` | Filter by sender name. |
| `--subject [text]` | Filter by subject line. |
| `--search [text]` | Search in author, subject, and body. |
| `--after [date]` | Show messages on or after this date (YYYY-MM-DD). |
| `--before [date]` | Show messages on or before this date (YYYY-MM-DD). |
| `--limit [num]` | Limit the number of messages processed. |
| `--info` | Show a summary of the archive (counts, conferences) and exit. |

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
