import os
import tarfile
import tempfile
import logging
import pytest
from pyqwk.core import load_data


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

        # Load the TAR - this should currently fail to find messages or not recognize it
        try:
            messages, board_dict = load_data(tar_path, logger)
            # If it's already supported, this test will pass (but I expect it to fail to find messages)
            assert isinstance(messages, list)
            assert any(m.header.msgfrom.strip() == "TarAuthor" for m in messages)
        except Exception as e:
            pytest.fail(f"TAR loading failed: {e}")


if __name__ == "__main__":
    # Manually run if needed
    test_tar_batch_loading()
