# pyqwk

pyqwk is a .qwk reader in Python that exports .QWK mail archives to a more readable format, without requiring the use of a .QWK reader. This is useful for data archivists who want to archive .QWK mail archives in a more readable format. .QWK archives were popular back in the Fidonet and BBS days and people may want to archive them now.

## Usage

pyqwk exports the entire `messages.dat` file to a more readable format. It can take either the `messages.dat` file or the `.qwk` file:

- `messages.dat`: The indexes aren't needed, but the only downside is that it doesn't have the names of the subboards the messages are from.
- `.qwk` file: It will use the `CONTROL.DAT` file to retrieve the names of the conferences.

To use pyqwk, follow these steps:

1. Just put qwk.py where you want to run it from. The struct, zipfile, and argparse libraries that it uses are all included in standard python.
2. Run pyqwk with the path to either the `messages.dat` file or the `.qwk` file. For example:

```
python qwk.py messages.dat
```

or

```
python qwk.py my_archive.qwk
```

### Batch Processing

You can process multiple files at once by providing a list of input files and an output directory. The output files will be named after the input files, with the extension changed to `.txt`, `.json`, or `.xml` depending on the selected format.

```
python qwk.py *.qwk output/
```

For each message, the headers aren't exported in the same order they appear in `messages.dat`; they are rearranged to an order that might make more sense to a modern reader. 

## Options

- `--verbose` or `-v`
If this is set, pyqwk will include extra header details: conference information (even when the name can't be found), message numbers, and reference numbers. (default: off)

- `--private` or `-p`
If this is set, pyqwk will include messages marked as private. If you are an archivist, you may want to not include personal messages from people who kindly donated their qwk packets. But if you're archiving your own, use `--private` to include them. (default: off)

- `--noheader` or `-n`
If this is set, pyqwk will leave out the message header. (default: off, meaning message headers will be included)

- `--truncatesignatures` or `-t`
If this is set, pyqwk will truncate each message at the signature. Truncation happens at common signature separators. See the `SIGNATURE_PATTERNS_EXACT` and `SIGNATURE_PATTERNS_STARTSWITH` variables in `qwk.py` for the complete list. (default: off)

- `--cutquoting` or `-c`
If this is set, pyqwk will delete quoted text using common prefixes and quoting characters (such as `>`, `|`, `}`, or the DOS box character `\xb3`). See `RE_QUOTE_PATTERN` and `QUOTE_HEADER_PATTERNS` in `qwk.py` for the exact detection rules. (default: off)

- `--binariesremoval` or `-b`
If this is set, pyqwk will delete binaries (currently removes uuencoded, Base64-encoded, and yEnc blocks). (default: off)

- `--individualfiles` or `-i`
If this is set, pyqwk will put each individual message in its own file according to its SHA1 hash (if you have contributions of qwk packets from multiple people, avoids duplication). (default: off)

- `--redactpii` or `-r`
If this is set, pyqwk will redact PII (Personally Identifiable Information), currently only phone numbers and e-mails. (default: off)

## JSON and XML output formats

When `--format json` or `--format xml` is selected, pyqwk emits structured representations of each processed message. The `header` section mirrors the fields from `messages.dat`, and missing numeric fields such as `msgnum` or `refnum` appear as empty strings.

### JSON example

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
        "text": "<message body with \r\n newlines>"
    }
]
```

### XML example

```xml
<messages>
  <message>
    <header>
      <status>+</status>
      <msgnum>28</msgnum>
      <msgdate>10-04-94</msgdate>
      <msgtime>11:15</msgtime>
      <msgto>ALL</msgto>
      <msgfrom>DIVER</msgfrom>
      <msgsubject>NET/MESSAGE COORDINATION</msgsubject>
      <msgpassword />
      <refnum />
      <numblocks>1</numblocks>
      <msgflag />
      <confnum>3</confnum>
      <lognum>0</lognum>
      <nettag />
    </header>
    <text>&lt;message body with \r\n newlines&gt;</text>
  </message>
</messages>
```

In both formats the `header` fields map directly to the `MessageHeader` dataclass in `qwk.py`, while `text` contains the processed body with DOS-style newlines preserved.

Note: In the current version, when message headers are included (`--noheader` is not set), the formatted header is still present inside the `text` field. The structured `header` section is authoritative for the header values.

## Known Issues

- Some `.qwk` packets from this era use a ZIP compression method that modern Python doesn't know. To work around this issue:

  - Some archive utilities have a tool to repack archives into modern formats. Some even have a method to do it in bulk.
  - Unpack the archive and act on `messages.dat`.

- Apparently, there's a password protection option for messages, but pyqwk skips those messages. 

- `cutquoting` is simplistic
  - Recognizes quoted lines that start with common characters such as `>`, `|`, `}`, or `\xb3` (a DOS box-drawing character), but may not match every quoting style.
  - Has been updated to catch quoting that has been word wrapped, but still might run into trouble. ie, this will be handled, but more complex cases might not.
```
XX> This is actually a pretty long line that has been quoted and then word
wrap
XX> has made "wrap" not recognized as part of a quote.
```

## Contributing

Pull requests are accepted.
