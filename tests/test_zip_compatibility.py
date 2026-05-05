import unittest
from unittest.mock import patch, MagicMock
import pyqwk.core as core
import os
import tempfile
import zipfile


class TestZipCompatibility(unittest.TestCase):
    def test_load_data_raises_if_messages_dat_missing_in_zip(self):
        """Test that a ZIP with no supported files raises FileNotFoundError."""
        logger = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a ZIP with an unsupported file
            zip_path = os.path.join(tmpdir, "empty.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("readme.bin", "nothing here")

            with self.assertRaises(FileNotFoundError):
                core.load_data(zip_path, logger)

    @patch("subprocess.run")
    def test_load_data_unzip_fallback_called_process_error(self, mock_run):
        """Test that failed unzip fallback raises RuntimeError."""
        logger = MagicMock()
        # Mock unzip returning error
        mock_run.return_value = MagicMock(returncode=2, stderr="fatal error")

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "fail.zip")
            # Create a valid ZIP so extractall is called first
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("test.json", "{}")

            # We need to make extractall fail to trigger the fallback
            with patch("zipfile.ZipFile.extractall", side_effect=NotImplementedError()):
                with self.assertRaises(RuntimeError) as cm:
                    core.load_data(zip_path, logger)
                self.assertIn("unzip failed", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
