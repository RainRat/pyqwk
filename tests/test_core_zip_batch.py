import os
import zipfile
import tempfile
import logging
from pyqwk.core import load_data, ParsedMessage, MessageHeader

def test_zip_multi_format_loading():
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a JSON file with one message
        json_path = os.path.join(tmpdir, "test.json")
        with open(json_path, "w") as f:
            f.write('[{"header": {"msgfrom": "Author1", "msgsubject": "Subj1", "confnum": 1}, "text": "Body1"}]')

        # 2. Create a CSV file with one message
        csv_path = os.path.join(tmpdir, "test.csv")
        with open(csv_path, "w") as f:
            f.write('"msgfrom","msgsubject","confnum","text"\n"Author2","Subj2","2","Body2"\n')

        # 3. Create a ZIP file containing both
        zip_path = os.path.join(tmpdir, "batch.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(json_path, arcname="messages.json")
            zf.write(csv_path, arcname="folder/messages.csv")

        # Load the ZIP
        messages, board_dict = load_data(zip_path, logger)

        assert isinstance(messages, list)
        assert len(messages) == 2

        # Verify message content
        authors = {m.header.msgfrom.strip() for m in messages}
        assert "Author1" in authors
        assert "Author2" in authors

        subjects = {m.header.msgsubject.strip() for m in messages}
        assert "Subj1" in subjects
        assert "Subj2" in subjects

def test_zip_single_qwk_dat_compatibility():
    # Verify that a ZIP containing only messages.dat still returns original bytes for compatibility
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        dat_content = b"Produced by test".ljust(128) + b"x" * 128
        dat_path = os.path.join(tmpdir, "messages.dat")
        with open(dat_path, "wb") as f:
            f.write(dat_content)

        zip_path = os.path.join(tmpdir, "packet.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(dat_path, arcname="MESSAGES.DAT")

        data, board_dict = load_data(zip_path, logger)

        assert isinstance(data, bytearray)
        assert data == bytearray(dat_content)

def test_zip_merges_bbs_info():
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a JSON file with BBS name
        json_path = os.path.join(tmpdir, "test.json")
        with open(json_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A", "msgsubject": "S", "confnum": 1}, "text": "B", "bbs_name": "MyBBS"}]')

        # 2. Create another JSON file
        json2_path = os.path.join(tmpdir, "test2.json")
        with open(json2_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A2", "msgsubject": "S2", "confnum": 2}, "text": "B2"}]')

        zip_path = os.path.join(tmpdir, "mergebbs.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(json_path, arcname="1.json")
            zf.write(json2_path, arcname="2.json")

        messages, board_dict = load_data(zip_path, logger)

        assert board_dict.bbs_info is not None
        assert board_dict.bbs_info.name == "MyBBS"
        assert len(messages) == 2
