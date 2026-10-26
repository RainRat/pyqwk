import os
import tarfile
import tempfile
import logging
from unittest.mock import patch, MagicMock
import pytest
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
        with tarfile.open(tar_path, "w") as tf:
            tf.add(json_path, arcname=json_filename)

        try:
            messages, board_dict = load_data(tar_path, logger)
            assert isinstance(messages, list)
            assert any(m.header.msgfrom.strip() == "TarAuthor" for m in messages)
        except Exception as e:
            pytest.fail(f"TAR loading failed: {e}")


def test_tar_extraction_error():
    logger = logging.getLogger("test")
    with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
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

    with tempfile.NamedTemporaryFile(suffix=".tar") as tmp_tar:
        with tarfile.open(tmp_tar.name, "w") as tar:
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
            cmap1.bbs_info.name = ""

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
                mock_load.side_effect = [([msg1], cmap1), ([msg2], cmap2)]

                msgs, b_dict = load_data(tmp_tar.name, logger)
                assert b_dict.bbs_info.name == "MyBBS"


def test_tar_classic_qwk_inside():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        msg_dat = os.path.join(tmpdir, "MESSAGES.DAT")
        with open(msg_dat, "wb") as f:
            f.write(b" " * 128)

        tar_path = os.path.join(tmpdir, "classic.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(msg_dat, arcname="MESSAGES.DAT")

        with patch("pyqwk.core.load_data") as mock_load:
            cmap = ConferenceMap()
            cmap[1] = "General"
            mock_load.return_value = (bytearray(b" " * 128), cmap)

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

        msgs, b_dict = load_data(tar_path, logger)
        assert len(msgs) == 1


def test_tar_no_messages_loaded():
    logger = logging.getLogger("test")
    with tempfile.TemporaryDirectory() as tmpdir:
        json1 = os.path.join(tmpdir, "1.json")
        with open(json1, "w") as f:
            f.write("[]")

        tar_path = os.path.join(tmpdir, "empty_msgs.tar")
        with tarfile.open(tar_path, "w") as tar:
            tar.add(json1, arcname="1.json")

        with pytest.raises(
            ValueError, match="No messages could be loaded from TAR archive"
        ):
            load_data(tar_path, logger)


def test_tar_no_data_filter_fallback():
    logger = logging.getLogger("test")

    with patch("pyqwk.core.tarfile") as mock_tar_mod:
        if hasattr(mock_tar_mod, "data_filter"):
            del mock_tar_mod.data_filter

        mock_tar = MagicMock()
        mock_tar_mod.open.return_value.__enter__.return_value = mock_tar
        mock_tar_mod.is_tarfile.return_value = True

        with patch("os.path.isfile", return_value=True):
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
                    args, kwargs = mock_tar.extractall.call_args
                    assert "filter" not in kwargs
