# pyqwk

pyqwk is a Python tool that converts `.QWK` mail archives into readable formats (Text, HTML, JSON, XML). It helps archivists and enthusiasts preserve messages from the Fidonet and BBS era.

## Installation

You can use `pyqwk` in two ways: running the script directly or installing it as a tool.

**Requirements:** Python 3.10 or newer.

### Option 1: Run Script Directly
1.  Download the `qwk.py` file.
2.  Open your terminal.
3.  Run the script:
    ```bash
    python qwk.py [arguments]
    ```

*Tip: For a progress bar, install `tqdm`: `pip install tqdm`.*

### Option 2: Install as a Command
To use the `qwk` command from any folder:

1.  Download the source code (or clone the repository).
2.  Open your terminal and go to the project folder (where `qwk.py` is located).
3.  Install:
    ```bash
    pip install .
    ```
4.  Run:
    ```bash
    qwk [arguments]
    ```

## Usage

pyqwk processes:
*   **`.qwk` files:** ZIP archives (includes conference names).
*   **`messages.dat` files:** Raw message data (numbers only).

### Basic Usage

**Print to screen:**
Read a QWK file and show it in the terminal:
```bash
python qwk.py archive.qwk
```

**Save to file:**
Convert an archive and save the result:
```bash
python qwk.py archive.qwk -o output.txt
```

### Batch Processing

To process multiple files, use a wildcard (like `*.qwk`) and specify an output folder:
```bash
python qwk.py *.qwk -o output_directory/
```
The tool saves each result in that folder, using the original filename and correct extension (e.g., `.txt`, `.json`).

*Note for Windows users: The Command Prompt does not support wildcards like `*.qwk` automatically. Use PowerShell or list files individually.*

## Options

| Option | Description |
| :--- | :--- |
| `-o`, `--output` | Output file or folder. Default: screen (stdout). |
| `--format` | Output format: `text`, `html`, `json`, `xml`. Default: Auto-detected from filename (or `text`). |
| `-v`, `--verbose` | Show detailed headers (numbers, conferences). |
| `-p`, `--private` | Include private messages. |
| `-n`, `--noheader` | Exclude headers from the message body. |
| `-T`, `--threaded` | Group replies by thread. **Incompatible with `-i`.** |
| `-t`, `--truncate-signatures` | Remove text after signature markers (e.g., `---`). |
| `-c`, `--cut-quoting` | Remove quotes (lines starting with `>`, `|`). |
| `-b`, `--binaries-removal` | Remove binary data (uuencoded, Base64, yEnc). |
| `-r`, `--redact-pii` | Hide emails and phone numbers. |
| `-i`, `--individual-files` | Save as separate files (hashed filenames). **Incompatible with `-T`.** |
| `--encoding` | Input text encoding (default: `cp437`). |
| `--separator` | Message separator style (`auto`, `none`, `dashes`, `blank`). |
| `-q`, `--quiet` | Hide progress bar. |
| `-l`, `--loglevel` | Set log level (`DEBUG`, `INFO`). |
| `-C`, `--conference` | Filter by conference name or number (can be used multiple times). |
| `--from` | Filter by author name (can be used multiple times). |
| `--subject` | Filter by subject (can be used multiple times). |
| `--clean` | Enable all cleaning options (`-t`, `-c`, `-b`). |
| `--info` | Show summary (message counts, conferences) and exit. |
| `--version` | Show version number. |

## Output Formats

### Text (Default)
Plain text with readable headers.
*   **Threaded Mode:** Indents replies by 2 spaces.

### HTML
Browsable web page.
*   **Structure:** Messages wrapped in `<div class="message">`.
*   **Threaded Mode:** Nested `<div class="reply">` elements.
```bash
python qwk.py archive.qwk --format html -o output.html
```

### JSON and XML
Structured data for automated processing.

**JSON Example:**
```json
[
    {
        "header": {
            "status": "+",
            "msgnum": "28",
            ...
        },
        "text": "<message body>",
        "depth": 0,
        "thread_id": "28",
        "parent_msgnum": null
    }
]
```

**XML Example:**
```xml
<messages>
  <message>
    <depth>0</depth>
    <thread_id>28</thread_id>
    <header>
      <status>+</status>
      <msgnum>28</msgnum>
      ...
    </header>
    <text>&lt;message body&gt;</text>
  </message>
</messages>
```

## Limitations & Troubleshooting

*   **Threading vs. Individual Files:** You cannot combine `--threaded` (`-T`) and `--individual-files` (`-i`).
*   **Password Protection:** Password-protected messages are always skipped.
*   **Compression:** Some older `.qwk` packets use unsupported ZIP compression.
    *   *Workaround:* Unzip manually and process `messages.dat` directly.
*   **Quoting detection:** The `--cut-quoting` feature uses common prefixes (like `>`) but may miss complex quotes.

## Contributing

Pull requests welcome! Run tests before submitting:
```bash
pytest
```
