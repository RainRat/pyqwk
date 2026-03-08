import os
import csv
import logging
import pytest
from pyqwk.core import (
    ProcessingSettings,
    write_messages,
    load_data,
)

def test_csv_export_import_symmetry(tmp_path, message_factory):
    """Test that messages exported to CSV can be read back with metadata intact."""
    csv_path = tmp_path / "test_messages.csv"

    # 1. Create sample messages
    msg1 = message_factory(
        confnum=1,
        msgnum=101,
        refnum=None,
        subject="Test Subject 1",
        text="Hello Bob, this is a test.",
    )
    msg1.header.msgfrom = "Alice"
    msg1.header.msgto = "Bob"
    msg1.confname = "General"

    msg2 = message_factory(
        confnum=2,
        msgnum=202,
        refnum=101,
        subject="Re: Test Subject 1",
        text="Hello Alice, I received your test.",
    )
    msg2.header.msgfrom = "Bob"
    msg2.header.msgto = "Alice"
    msg2.confname = "Support"
    msg2.depth = 1
    msg2.parent_msgnum = 101
    msg2.attachments = ["image.png", "data.zip"]

    messages = [msg1, msg2]

    # 2. Export to CSV
    settings = ProcessingSettings(
        verbose=True,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format='csv',
        separator='none',
        output_mode='file',
        output_path=str(csv_path),
        encoding='utf-8'
    )

    write_messages(messages, str(csv_path), settings)
    assert os.path.exists(csv_path)

    # 3. Import from CSV
    logger = logging.getLogger("test")
    imported_messages, board_dict = load_data(str(csv_path), logger)

    # 4. Verify data integrity
    assert len(imported_messages) == 2

    # Check first message
    m1 = imported_messages[0]
    assert m1.confnum == 1
    assert m1.msgnum == 101
    assert m1.header.msgfrom == "Alice"
    assert m1.header.msgsubject == "Test Subject 1"
    assert m1.text == "Hello Bob, this is a test."
    assert board_dict[1] == "General"

    # Check second message (with hierarchy and attachments)
    m2 = imported_messages[1]
    assert m2.confnum == 2
    assert m2.msgnum == 202
    assert m2.depth == 1
    assert m2.parent_msgnum == 101
    assert m2.attachments == ["image.png", "data.zip"]
    assert board_dict[2] == "Support"

def test_csv_import_malformed(tmp_path):
    """Test handling of empty or missing CSV fields."""
    csv_path = tmp_path / "malformed.csv"

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['confnum', 'msgfrom', 'text'])
        writer.writeheader()
        writer.writerow({'confnum': '10', 'msgfrom': 'System', 'text': 'Body'})

    logger = logging.getLogger("test")
    imported, board = load_data(str(csv_path), logger)

    assert len(imported) == 1
    assert imported[0].confnum == 10
    assert imported[0].header.msgfrom == "System"
    assert imported[0].text == "Body"
