import os
import shutil
import mailbox
import logging
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    load_data,
    write_messages,
    expand_paths,
)

def test_maildir_export_import(tmp_path):
    # 1. Prepare dummy messages
    h1 = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="01-20-24",
        msgtime="10:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Maildir 1",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    m1 = ParsedMessage(text="Hello Alice!", msgnum=101, refnum=None, confnum=1, header=h1)

    h2 = MessageHeader(
        status=" ",
        msgnum=102,
        msgdate="01-21-24",
        msgtime="11:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Re: Test Maildir 1",
        msgpassword="",
        refnum=101,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    m2 = ParsedMessage(text="Hi Bob!", msgnum=102, refnum=101, confnum=1, header=h2)

    messages = [m1, m2]

    # 2. Export to Maildir
    maildir_path = tmp_path / "test.maildir"
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="maildir",
        separator="none",
        output_mode="file",
        output_path=str(maildir_path),
        encoding="utf-8",
        quiet=True,
        merge=False,
    )

    write_messages(messages, str(maildir_path), settings)

    # Verify directory structure
    assert os.path.isdir(maildir_path)
    assert os.path.isdir(maildir_path / "cur")
    assert os.path.isdir(maildir_path / "new")
    assert os.path.isdir(maildir_path / "tmp")

    # Check mailbox count
    mdir = mailbox.Maildir(str(maildir_path))
    assert len(mdir) == 2

    # 3. Import from Maildir
    logger = logging.getLogger("test")
    loaded_messages, board_dict = load_data(str(maildir_path), logger)

    assert len(loaded_messages) == 2

    # Sort by message number to be sure
    loaded_messages.sort(key=lambda x: x.msgnum)

    assert loaded_messages[0].header.msgsubject == "Test Maildir 1"
    assert loaded_messages[0].text.strip() == "Hello Alice!"
    assert loaded_messages[0].msgnum == 101
    assert loaded_messages[0].header.msgfrom == "Bob"

    assert loaded_messages[1].header.msgsubject == "Re: Test Maildir 1"
    assert loaded_messages[1].text.strip() == "Hi Bob!"
    assert loaded_messages[1].msgnum == 102
    assert loaded_messages[1].refnum == 101

def test_expand_paths_maildir(tmp_path):
    # Create a Maildir
    mdir_path = tmp_path / "my.maildir"
    mailbox.Maildir(str(mdir_path), create=True)

    # Create a nested Maildir (to test recursion stop)
    sub_dir = tmp_path / "nested"
    sub_dir.mkdir()
    inner_mdir = sub_dir / "inner.mdir"
    mailbox.Maildir(str(inner_mdir), create=True)

    # Create a regular file
    txt_file = tmp_path / "normal.txt"
    txt_file.write_text("hello")

    # Create a non-maildir directory with a supported file
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    qwk_file = other_dir / "archive.qwk"
    qwk_file.write_text("fake qwk")

    paths = expand_paths([str(tmp_path)])

    # Should find my.maildir, nested/inner.mdir, normal.txt, and other/archive.qwk
    # Important: it should NOT recurse INTO my.maildir/cur etc.

    # Convert to relative for easier assertion
    rel_paths = [os.path.relpath(p, tmp_path) for p in paths]

    assert "my.maildir" in rel_paths
    assert os.path.join("nested", "inner.mdir") in rel_paths
    assert "normal.txt" in rel_paths
    assert os.path.join("other", "archive.qwk") in rel_paths

    # Ensure it didn't pick up subfolders of maildirs
    assert not any("my.maildir/cur" in p for p in rel_paths)
    assert not any("inner.mdir/new" in p for p in rel_paths)
