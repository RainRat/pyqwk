import os
import tarfile
import tempfile
import logging
import pytest
from pyqwk.core import load_data, ParsedMessage, MessageHeader

def test_load_data_tar_batch(tmp_path):
    """Verify that load_data can correctly extract and merge messages from a TAR archive."""
    logger = logging.getLogger("test_tar")

    # Create some dummy message files
    msg1_content = '{"header": {"msgsubject": "Subject 1", "msgfrom": "Author 1", "confnum": 1}, "text": "Body 1"}'
    msg2_content = '{"header": {"msgsubject": "Subject 2", "msgfrom": "Author 2", "confnum": 2}, "text": "Body 2"}'

    msg1_file = tmp_path / "msg1.json"
    msg1_file.write_text(msg1_content)

    msg2_file = tmp_path / "msg2.json"
    msg2_file.write_text(msg2_content)

    # Create a TAR archive containing these files
    tar_path = tmp_path / "test.tar"
    with tarfile.open(tar_path, "w") as tar:
        tar.add(msg1_file, arcname="msg1.json")
        tar.add(msg2_file, arcname="msg2.json")

    # Load data from the TAR archive
    messages, board_dict = load_data(str(tar_path), logger)

    # Verify the results
    assert isinstance(messages, list)
    assert len(messages) == 2

    subjects = {m.header.msgsubject for m in messages}
    assert "Subject 1" in subjects
    assert "Subject 2" in subjects

    assert board_dict[1] == "Conference 1"
    assert board_dict[2] == "Conference 2"

def test_load_data_tgz_batch(tmp_path):
    """Verify that load_data can correctly handle compressed TAR archives (.tar.gz)."""
    logger = logging.getLogger("test_tgz")

    msg_content = '{"header": {"msgsubject": "Compressed", "msgfrom": "Author", "confnum": 10}, "text": "Body"}'
    msg_file = tmp_path / "msg.json"
    msg_file.write_text(msg_content)

    tgz_path = tmp_path / "test.tar.gz"
    with tarfile.open(tgz_path, "w:gz") as tar:
        tar.add(msg_file, arcname="msg.json")

    messages, board_dict = load_data(str(tgz_path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgsubject == "Compressed"
    assert board_dict[10] == "Conference 10"
