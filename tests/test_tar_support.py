import os
import tarfile
import tempfile
import logging
import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import load_data, ConferenceMap, BBSInfo, ParsedMessage, MessageHeader

def create_msg_header(**kwargs):
    defaults = {
        'status': ' ',
        'msgnum': 1,
        'msgdate': '01-01-24',
        'msgtime': '00:00',
        'msgto': 'To',
        'msgfrom': 'From',
        'msgsubject': 'Subject',
        'msgpassword': '',
        'refnum': 0,
        'numblocks': 1,
        'msgflag': ' ',
        'confnum': 0,
        'lognum': 0,
        'nettag': ''
    }
    defaults.update(kwargs)
    return MessageHeader(**defaults)

def create_parsed_msg(**kwargs):
    header = kwargs.pop('header', None) or create_msg_header()
    defaults = {
        'text': 'Body',
        'msgnum': header.msgnum,
        'refnum': header.refnum,
        'confnum': header.confnum,
        'header': header
    }
    defaults.update(kwargs)
    return ParsedMessage(**defaults)

def test_tar_batch_loading():
    logger = logging.getLogger("test")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a JSON file with one message
        json_content = '[{"header": {"msgfrom": "TarAuthor", "msgsubject": "TarSubj", "confnum": 1}, "text": "TarBody"}]'
        json_filename = "test.json"
        json_path = os.path.join(tmpdir, json_filename)
        with open(json_path, "w") as f:
            f.write(json_content)

        # 2. Create a TAR file containing the JSON
        tar_path = os.path.join(tmpdir, "batch.tar")
        with tarfile.open(tar_path, 'w') as tf:
            tf.add(json_path, arcname=json_filename)

        # Load the TAR
        messages, board_dict = load_data(tar_path, logger)
        assert isinstance(messages, list)
        assert any(m.header.msgfrom.strip() == "TarAuthor" for m in messages)

def test_tar_no_supported_files():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        unsupported_path = os.path.join(tmpdir, "test.txt")
        with open(unsupported_path, "w") as f:
            f.write("unsupported")

        tar_path = os.path.join(tmpdir, "empty.tar")
        with tarfile.open(tar_path, 'w') as tf:
            tf.add(unsupported_path, arcname="test.txt")

        with pytest.raises(ValueError, match="No supported message files found in TAR archive"):
            load_data(tar_path, logger)

def test_tar_no_messages():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create an empty JSON (supported format but no messages)
        json_path = os.path.join(tmpdir, "test.json")
        with open(json_path, "w") as f:
            f.write("[]")

        tar_path = os.path.join(tmpdir, "no_msgs.tar")
        with tarfile.open(tar_path, 'w') as tf:
            tf.add(json_path, arcname="test.json")

        with pytest.raises(ValueError, match="No messages could be loaded from TAR archive"):
            load_data(tar_path, logger)

def test_tar_extraction_error():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "corrupt.tar")
        with open(tar_path, "wb") as f:
            f.write(b"not a tar file")

        # Mock tarfile.open only when called inside the with block,
        # but let tarfile.is_tarfile (which also calls open) work or be mocked.
        with patch("tarfile.is_tarfile", return_value=True):
            with patch("tarfile.open", side_effect=Exception("Corrupt")):
                with pytest.raises(RuntimeError, match="An error occurred while extracting TAR archive"):
                    load_data(tar_path, logger)

def test_tar_data_filter_fallback():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "test.json")
        with open(json_path, "w") as f:
            f.write('[{"header": {"msgfrom": "A", "msgsubject": "S", "confnum": 1}, "text": "B"}]')

        tar_path = os.path.join(tmpdir, "fallback.tar")
        with tarfile.open(tar_path, 'w') as tf:
            tf.add(json_path, arcname="test.json")

        # We want to force the 'else' branch of 'if hasattr(tarfile, "data_filter"):'
        # We mock 'tarfile' in 'pyqwk.core'
        with patch("pyqwk.core.tarfile") as mock_tar:
            mock_tar.is_tarfile.side_effect = tarfile.is_tarfile
            mock_tar.open.side_effect = tarfile.open

            # To make hasattr(mock_tar, 'data_filter') return False:
            if hasattr(mock_tar, 'data_filter'):
                del mock_tar.data_filter

            messages, _ = load_data(tar_path, logger)
            assert len(messages) == 1

def test_tar_bbs_info_merging_real():
    # Use real files to test merging logic
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "merge.tar")
        with tarfile.open(tar_path, 'w') as tf:
            for i in [1, 2]:
                p = os.path.join(tmpdir, f"file{i}.json")
                with open(p, "w") as f: f.write("[]")
                tf.add(p, arcname=f"file{i}.json")

        m1 = create_parsed_msg(header=create_msg_header(msgfrom="A1"), text="B1")
        m2 = create_parsed_msg(header=create_msg_header(msgfrom="A2"), text="B2")
        bd1 = ConferenceMap()
        bd1.bbs_info = BBSInfo(name="BBS1")
        bd1[1] = "Conf1"
        bd2 = ConferenceMap()
        bd2.bbs_info = BBSInfo(name="BBS2")
        bd2[2] = "Conf2"

        orig_load_data = load_data
        def mocked_load_data(path, *args, **kwargs):
            if path == tar_path:
                return orig_load_data(path, *args, **kwargs)
            if "file1.json" in path:
                return [m1], bd1
            if "file2.json" in path:
                return [m2], bd2
            return orig_load_data(path, *args, **kwargs)

        with patch("pyqwk.core.load_data", side_effect=mocked_load_data):
            messages, board_dict = load_data(tar_path, logger)
            assert len(messages) == 2
            assert board_dict.bbs_info.name == "BBS1"
            assert board_dict[1] == "Conf1"
            assert board_dict[2] == "Conf2"

def test_tar_bbs_info_merging_name_priority():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "merge_priority.tar")
        with tarfile.open(tar_path, 'w') as tf:
            for i in [1, 2]:
                p = os.path.join(tmpdir, f"file{i}.json")
                with open(p, "w") as f: f.write("[]")
                tf.add(p, arcname=f"file{i}.json")

        bd1 = ConferenceMap()
        bd1.bbs_info = BBSInfo(name="") # Empty name
        bd2 = ConferenceMap()
        bd2.bbs_info = BBSInfo(name="BBS2")

        orig_load_data = load_data
        def mocked_load_data(path, *args, **kwargs):
            if path == tar_path:
                return orig_load_data(path, *args, **kwargs)
            if "file1.json" in path:
                return [create_parsed_msg()], bd1
            if "file2.json" in path:
                return [], bd2
            return orig_load_data(path, *args, **kwargs)

        with patch("pyqwk.core.load_data", side_effect=mocked_load_data):
            messages, board_dict = load_data(tar_path, logger)
            assert board_dict.bbs_info.name == "BBS2"

def test_tar_bytearray_handling():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "classic.tar")
        with tarfile.open(tar_path, 'w') as tf:
            p = os.path.join(tmpdir, "MESSAGES.DAT")
            with open(p, "wb") as f: f.write(b"fake data")
            tf.add(p, arcname="MESSAGES.DAT")

        fake_msg = create_parsed_msg(header=create_msg_header(confnum=1), confnum=1)
        bd = ConferenceMap()
        bd[1] = "ClassicConf"

        orig_load_data = load_data
        def mocked_load_data(path, *args, **kwargs):
            if path == tar_path:
                return orig_load_data(path, *args, **kwargs)
            if "MESSAGES.DAT" in path:
                return bytearray(b"fake"), bd
            return orig_load_data(path, *args, **kwargs)

        with patch("pyqwk.core.load_data", side_effect=mocked_load_data):
            with patch("pyqwk.core.parse_messages", return_value=[fake_msg]):
                messages, board_dict = load_data(tar_path, logger)
                assert len(messages) == 1
                assert messages[0].confname == "ClassicConf"

def test_tar_skip_on_error():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = os.path.join(tmpdir, "skip_error.tar")
        with tarfile.open(tar_path, 'w') as tf:
            for i in [1, 2]:
                p = os.path.join(tmpdir, f"file{i}.json")
                with open(p, "w") as f: f.write("[]")
                tf.add(p, arcname=f"file{i}.json")

        m2 = create_parsed_msg(header=create_msg_header(msgfrom="A2"), text="B2")

        orig_load_data = load_data
        def mocked_load_data(path, *args, **kwargs):
            if path == tar_path:
                return orig_load_data(path, *args, **kwargs)
            if "file1.json" in path:
                raise ValueError("Simulated error")
            if "file2.json" in path:
                return [m2], ConferenceMap()
            return orig_load_data(path, *args, **kwargs)

        with patch("pyqwk.core.load_data", side_effect=mocked_load_data):
            with patch.object(logger, 'warning') as mock_warning:
                messages, _ = load_data(tar_path, logger)
                assert len(messages) == 1
                assert messages[0].header.msgfrom == "A2"
                mock_warning.assert_called_once()
                # Use str(e) check instead of direct iteration on error object
                assert "Simulated error" in str(mock_warning.call_args[0][2])
