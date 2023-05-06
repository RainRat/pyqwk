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

For each message, the headers aren't exported in the same order they appear in `messages.dat`; they are rearranged to an order that might make more sense to a modern reader. 

## Options

- `--verbose` or `-v`
If this is set, pyqwk will include message IDs, which probably aren't useful to a modern reader (default: off)

- `--private` or `-p`
If this is set, pyqwk will include messages marked as private. If you are an archivist, you may want to not include personal messages from people who kindly donated their qwk packets. But if you're archiving your own, use `--private` to include them. (default: off)

- `--noheader` or `-n`
If this is set, pyqwk will leave out the message header. (default: off, meaning message headers will be included)

- `--truncatesignatures` or `-t`
If this is set, pyqwk will truncate each message at the signature (everything after a line that consists only of "---" or starts with "___" and some others) (default: off)

- `--cutquoting` or `-c`
If this is set, pyqwk will delete quoted text (that uses ">" as quoting character). (default: off)

- `--binariesremoval` or `-b`
If this is set, pyqwk will delete binaries (currently only uuencode). (default: off)

- `--individualfiles` or `-i`
If this is set, pyqwk will put each individual message in its own file according to its SHA1 hash (if you have contributions of qwk packets from multiple people, avoids duplication). (default: off)

## Known Issues

- Some `.qwk` packets from this era use a ZIP compression method that modern Python doesn't know. To work around this issue:

  - Some archive utilities have a tool to repack archives into modern formats. Some even have a method to do it in bulk.
  - Unpack the archive and act on `messages.dat`.

- Apparently, there's a password protection option for messages, but pyqwk skips those messages. 

- `cutquoting` is simplistic
  - Only knows quoting character `>`
  - Has been updated to catch quoting that has been word wrapped, but still might run into trouble. ie, this will be handled, but more complex cases might not.
```
XX> This is actually a pretty long line that has been quoted and then word
wrap
XX> has made "wrap" not recognized as part of a quote.
```

## Contributing

Pull requests are accepted.
