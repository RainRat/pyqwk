import os
import zipfile
import tempfile
import logging
import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import load_data

def test_zip_merge_bbs_info_overwrite_logic():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "batch.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            f1_path = os.path.join(tmpdir, "1.json")
            with open(f1_path, "w") as f:
                f.write('[{"header": {"msgfrom": "A", "msgsubject": "S", "confnum": 1}, "text": "B"}]')
            zf.write(f1_path, arcname="1.json")

            f2_path = os.path.join(tmpdir, "2.json")
            with open(f2_path, "w") as f:
                f.write('[{"header": {"msgfrom": "A2", "msgsubject": "S2", "confnum": 2}, "text": "B2", "bbs_name": "RealBBS"}]')
            zf.write(f2_path, arcname="2.json")

            for i in range(15):
                zf.writestr(f"dummy{i}.txt", "data")

        messages, board_dict = load_data(zip_path, logger)
        assert board_dict.bbs_info is not None
        assert board_dict.bbs_info.name == "RealBBS"

def test_zip_batch_skips_corrupt_file():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "corrupt.zip")

        good_path = os.path.join(tmpdir, "good.json")
        with open(good_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A", "msgsubject": "S", "confnum": 1}, "text": "B"}]')

        bad_path = os.path.join(tmpdir, "bad.json")
        with open(bad_path, "w") as f:
            f.write('not json')

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(good_path, arcname="good.json")
            zf.write(bad_path, arcname="bad.json")
            for i in range(15):
                zf.writestr(f"dummy{i}.txt", "data")

        with patch('pyqwk.core.logging.Logger.warning') as mock_warn:
            messages, board_dict = load_data(zip_path, logger)
            assert len(messages) == 1
            assert any("Skipping file" in str(args[0]) for args, kwargs in mock_warn.call_args_list)

def test_zip_batch_no_messages_raises_error():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "empty_batch.zip")

        empty_path = os.path.join(tmpdir, "empty.json")
        with open(empty_path, "w") as f:
            f.write('[]')

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(empty_path, arcname="empty.json")
            for i in range(15):
                zf.writestr(f"dummy{i}.txt", "data")

        with pytest.raises(ValueError, match="No messages could be loaded from ZIP archive"):
            load_data(zip_path, logger)

def test_zip_batch_qwk_bytes_recursive():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        status_block = b"Produced by test".ljust(128, b" ")
        msg_header = b" " * 128
        inner_dat = status_block + msg_header

        inner_control = [b"Test BBS", b"City", b"123", b"Sysop", b"Serial", b"0", b"User", b"Date", b"0", b"0", b"1", b"1", b"General"]

        zip_path = os.path.join(tmpdir, "outer_batch.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("packet/MESSAGES.DAT", inner_dat)
            zf.writestr("packet/CONTROL.DAT", b"\r\n".join(inner_control))
            for i in range(15):
                zf.writestr(f"dummy{i}.txt", "data")

        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_msg = MagicMock()
            mock_msg.confnum = 1
            mock_parse.return_value = [mock_msg]

            messages, board_dict = load_data(zip_path, logger)
            assert len(messages) >= 1
            assert mock_msg.confname == "General"
