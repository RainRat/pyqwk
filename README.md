# pyqwk

pyqwk is a Python tool that converts `.QWK` mail archives into readable formats (Text, HTML, JSON, XML). It is designed for archivists and enthusiasts who want to preserve or read messages from the Fidonet and BBS era.

## Installation

You can use `pyqwk` in two ways: running the script directly or installing it as a tool.

**Requirements:** Python 3.10 or newer.

### Option 1: Run Without Installing (Simplest)
1.  Download the `qwk.py` file.
2.  Open your terminal or command prompt.
3.  Run the script:
    ```bash
    python qwk.py [arguments]
    ```

*Tip: If you want a progress bar, install the optional `tqdm` library: `pip install tqdm`.*

### Option 2: Install as a Command
If you want to use the `qwk` command from anywhere:

1.  Clone this repository or download the source code.
2.  Open your terminal in the `pyqwk` folder.
3.  Install the tool:
    ```bash
    pip install .
    ```
4.  Run it using the `qwk` command:
    ```bash
    qwk [arguments]
    ```

## Usage

pyqwk can process:
*   **`.qwk` files:** ZIP archives containing message and control data. This is the preferred format as it includes conference names.
*   **`messages.dat` files:** Raw message data. Conference names will not be available (numbers only).

### Basic Usage

**Print to screen:**
Read a QWK file and show it in the terminal:
```bash
python qwk.py archive.qwk
```
*(If you installed the tool, replace `python qwk.py` with `qwk`)*

**Save to file:**
Convert an archive and save the result:
```bash
python qwk.py archive.qwk -o output.txt
```

### Batch Processing

To process multiple files, provide a list of inputs and specify an output directory with `-o`:
```bash
python qwk.py *.qwk -o output_directory/
```
Output files will use the input filename with the appropriate extension (e.g., `.txt`, `.json`, `.html`).

## Options

| Option | Description |
| :--- | :--- |
| `-o`, `--output` | Output path (file or directory). Defaults to stdout for single files. |
| `--format` | Output format: `text` (default), `html`, `json`, `xml`. |
| `-v`, `--verbose` | Include detailed headers (message numbers, references, conference info). |
| `-p`, `--private` | Include private messages (default: excluded). |
| `-n`, `--noheader` | Exclude the formatted header from the message body. |
| `-T`, `--threaded` | Group messages by thread (replies follow parents). **Incompatible with `-i`.** |
| `-t`, `--truncate-signatures` | Cut off content at common signature markers (e.g., `---`). |
| `-c`, `--cut-quoting` | Remove quoted text (lines starting with `>`, `|`, etc.). |
| `-b`, `--binaries-removal` | Remove binary blocks (uuencoded, Base64, yEnc). |
| `-r`, `--redact-pii` | Redact email addresses and phone numbers. |
| `-i`, `--individual-files` | Save each message as a separate file using its hash as the filename. **Incompatible with `-T`.** |
| `--encoding` | Input character encoding (default: `cp437`). |
| `--separator` | Control how messages are separated in text output (`auto`, `none`, `dashes`, `blank`). |
| `-q`, `--quiet` | Suppress the progress bar. |
| `-l`, `--loglevel` | Set the logging level (e.g., `DEBUG`, `INFO`). |
| `--version` | Show the version number. |

## Output Formats

### Text (Default)
A plain text format where headers are rearranged for readability.
*   **Threaded Mode:** Indents replies by 2 spaces per level.

### HTML
Generates a browsable web page.
*   **Structure:** Messages are wrapped in `<div class="message">`.
*   **Threaded Mode:** Replies are nested within `<div class="reply">` elements.
```bash
python qwk.py archive.qwk --format html -o output.html
```

### JSON and XML
Generates structured data for automated processing.

**JSON Example:**
```json
[
    {
        "header": {
            "status": "+",
            "msgnum": "28",
            "msgdate": "10-04-94",
            "msgtime": "11:15",
            "msgto": "ALL",
            "msgfrom": "DIVER",
            "msgsubject": "NET/MESSAGE COORDINATION",
            "msgpassword": "",
            "refnum": "",
            "numblocks": "1",
            "msgflag": "",
            "confnum": 3,
            "lognum": 0,
            "nettag": ""
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

In both formats the `header` fields map directly to the `MessageHeader` dataclass in `qwk.py`.

## Limitations & Troubleshooting

*   **Threading vs. Individual Files:** You cannot use `--threaded` (`-T`) and `--individual-files` (`-i`) together. The tool will show an error if you try to combine them.
*   **Password Protection:** For security and privacy, password-protected messages are always skipped.
*   **Compression:** Some older `.qwk` packets use ZIP compression methods not supported by Python's `zipfile` library.
    *   *Workaround:* Unzip the archive manually and process the `messages.dat` file directly.
*   **Quoting detection:** The `--cut-quoting` feature uses common prefixes (like `>`) but may miss complex or word-wrapped quotes.

## Contributing

Pull requests are welcome! Please ensure you run tests before submitting:
```bash
pytest
```
