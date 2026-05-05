import os
import tarfile
import tempfile
import logging
import pytest
from unittest.mock import patch, MagicMock
from pyqwk.core import load_data, ConferenceMap, ParsedMessage, MessageHeader, BBSInfo


def create_dummy_header(**kwargs):
    default = {
        "status": " ",
        "msgnum": 1,
        "msgdate": "01-01-25",
        "msgtime": "12:00",
        "msgto": "All",
        "msgfrom": "Author",
        "msgsubject": "Subj",
        "msgpassword": "",
        "refnum": 0,
        "numblocks": 1,
        "msgflag": " ",
        "confnum": 1,
        "lognum": 0,
        "nettag": " ",
    }
    default.update(kwargs)
    return MessageHeader(**default)


def test_tar_extraction_error():
    logger = logging.getLogger("test")
    with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
        # We need is_tarfile to return True, but tarfile.open to fail.
        # But tarfile.is_tarfile might call tarfile.open.
        # Let's patch pyqwk.core.tarfile.open specifically.
        with patch("pyqwk.core.tarfile.is_tarfile", return_value=True):
            with patch(
                "pyqwk.core.tarfile.open",
                side_effect=Exception("Mock extraction error"),
            ):
                with pytest.raises(
                    RuntimeError, match="An error occurred while extracting TAR archive"
                ):
                    load_data(tmp.name, logger)


def test_tar_no_supported_files():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        dummy_file = os.path.join(tmpdir, "dummy.dummy")
        with open(dummy_file, "w") as f:
            f.write("not a message file")

        tar_path = os.path.join(tmpdir, "empty.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(dummy_file, arcname="dummy.dummy")

        with pytest.raises(
            ValueError, match="No supported message files found in TAR archive"
        ):
            load_data(tar_path, logger)


def test_tar_bbs_info_name_merging():
    logger = logging.getLogger("test")

    # We need a real tar file to pass the is_tarfile check
    with tempfile.NamedTemporaryFile(suffix=".tar") as tmp_tar:
        with tarfile.open(tmp_tar.name, "w") as tar:
            # Add a dummy file
            with tempfile.NamedTemporaryFile() as f:
                tar.add(f.name, arcname="dummy.json")

        with patch("pyqwk.core.expand_paths") as mock_expand:
            mock_expand.return_value = ["path1.json", "path2.json"]

            msg1 = ParsedMessage(
                header=create_dummy_header(msgfrom="A"),
                text="T",
                confnum=1,
                msgnum=1,
                refnum=0,
            )
            cmap1 = ConferenceMap()
            cmap1.bbs_info = BBSInfo()
            cmap1.bbs_info.name = ""  # Empty name

            msg2 = ParsedMessage(
                header=create_dummy_header(msgfrom="B"),
                text="T",
                confnum=1,
                msgnum=2,
                refnum=0,
            )
            cmap2 = ConferenceMap()
            cmap2.bbs_info = BBSInfo()
            cmap2.bbs_info.name = "MyBBS"

            with patch("pyqwk.core.load_data") as mock_load:
                # First call returns cmap with no name, second call returns cmap with name
                mock_load.side_effect = [([msg1], cmap1), ([msg2], cmap2)]

                msgs, b_dict = load_data(tmp_tar.name, logger)
                assert b_dict.bbs_info.name == "MyBBS"


def test_tar_classic_qwk_inside():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock MESSAGES.DAT
        msg_dat = os.path.join(tmpdir, "MESSAGES.DAT")
        with open(msg_dat, "wb") as f:
            f.write(b" " * 128)

        tar_path = os.path.join(tmpdir, "classic.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(msg_dat, arcname="MESSAGES.DAT")

        # Mock load_data when called recursively to return bytearray
        with patch("pyqwk.core.load_data") as mock_load:
            cmap = ConferenceMap()
            cmap[1] = "General"
            mock_load.return_value = (bytearray(b" " * 128), cmap)

            # Need to mock parse_messages to return a message
            mock_msg = ParsedMessage(
                header=create_dummy_header(confnum=1),
                text="Hi",
                confnum=1,
                msgnum=1,
                refnum=0,
            )
            with patch("pyqwk.core.parse_messages", return_value=[mock_msg]):
                msgs, b_dict = load_data(tar_path, logger)
                assert len(msgs) == 1
                assert msgs[0].confname == "General"


def test_tar_skip_corrupt_file():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        f1 = os.path.join(tmpdir, "1.json")
        with open(f1, "w") as f:
            f.write('[{"header": {"msgfrom": "A"}, "text": "T"}]')
        f2 = os.path.join(tmpdir, "2.json")
        with open(f2, "w") as f:
            f.write("corrupt")

        tar_path = os.path.join(tmpdir, "skip.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(f1, arcname="1.json")
            tar.add(f2, arcname="2.json")

        # load_data for 2.json will raise an error.
        msgs, b_dict = load_data(tar_path, logger)
        # Should have 1 message from 1.json, 2.json skipped
        assert len(msgs) == 1


def test_tar_no_messages_loaded():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        json1 = os.path.join(tmpdir, "1.json")
        with open(json1, "w") as f:
            f.write("[]")  # Empty list of messages

        tar_path = os.path.join(tmpdir, "empty_msgs.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(json1, arcname="1.json")

        with pytest.raises(
            ValueError, match="No messages could be loaded from TAR archive"
        ):
            load_data(tar_path, logger)


def test_tar_no_data_filter_fallback():
    # Test line 1780
    logger = logging.getLogger("test")

    with patch("pyqwk.core.tarfile") as mock_tar_mod:
        # Simulate Python < 3.12
        if hasattr(mock_tar_mod, "data_filter"):
            del mock_tar_mod.data_filter

        mock_tar = MagicMock()
        mock_tar_mod.open.return_value.__enter__.return_value = mock_tar
        mock_tar_mod.is_tarfile.return_value = True

        # To avoid actually needing a file, we can mock os.path.isfile
        with patch("os.path.isfile", return_value=True):
            # We also need to mock expand_paths and load_data to return something valid so it doesn't fail later
            with patch("pyqwk.core.expand_paths", return_value=["p1"]):
                with patch(
                    "pyqwk.core.load_data",
                    return_value=(
                        [
                            ParsedMessage(
                                header=create_dummy_header(),
                                text="",
                                confnum=1,
                                msgnum=1,
                                refnum=0,
                            )
                        ],
                        ConferenceMap(),
                    ),
                ):
                    load_data("dummy.tar", logger)
                    mock_tar.extractall.assert_called_once()
                    # Verify it was called without 'filter' argument
                    args, kwargs = mock_tar.extractall.call_args
                    assert "filter" not in kwargs
