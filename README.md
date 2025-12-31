# pyqwk

pyqwk is a simple tool to convert `.QWK` mail archives (from the BBS era) into readable formats like Text, HTML, JSON, and XML.

## Quick Start

1.  **Download** the `qwk.py` file.
2.  **Run it** (requires Python 3.10+):
    ```bash
    python qwk.py archive.qwk
    ```

*Tip: Run `pip install tqdm` to see a progress bar.*

## Installation (Optional)

If you want to use the `qwk` command from any folder:

1.  Download this repository.
2.  Open your terminal in the folder.
3.  Install:
    ```bash
    pip install .
    ```
4.  Now you can run:
    ```bash
    qwk archive.qwk
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

**Process multiple files:**
Save all converted files into a folder named `output`:
```bash
python qwk.py *.qwk -o output/
```
*Windows Users: Use PowerShell to support the `*.qwk` wildcard.*

## Common Options

| Flag | Description |
| :--- | :--- |
| `-o [file/folder]` | Where to save the output. Defaults to screen. |
| `--format [type]` | Output format: `text`, `html`, `json`, `xml`. |
| `-T`, `--threaded` | Group replies together (ideal for reading conversations). |
| `--clean` | Remove "junk" like signatures, quotes, and binary data. |
| `-p`, `--private` | Include private messages. |
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
