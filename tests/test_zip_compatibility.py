import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
import zipfile
import pyqwk.core as core


class TestZipCompatibility(unittest.TestCase):
    def test_load_data_raises_if_messages_dat_missing_in_zip(self):
        logger = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "empty.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("readme.bin", "nothing here")

            with self.assertRaises(FileNotFoundError):
                core.load_data(zip_path, logger)

    @patch("zipfile.is_zipfile", return_value=True)
    @patch("zipfile.ZipFile")
    @patch("subprocess.run")
    @patch("os.listdir")
    def test_load_data_unzip_fallback_reads_messages_and_control(
        self, mock_listdir, mock_run, mock_zipfile, mock_is_zipfile
    ):
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ["MESSAGES.DAT", "CONTROL.DAT"]
        mock_zip_instance.extractall.side_effect = NotImplementedError()

        mock_listdir.return_value = ["MESSAGES.DAT", "CONTROL.DAT"]
        mock_run.return_value = MagicMock(returncode=0)

        mock_messages_data = b"MESSAGES DATA"
        mock_control_data = b"Line1\nLine2\nLine3\nLine4\nLine5\nLine6\nLine7\nLine8\nLine9\nLine10\n0\n"

        def side_effect(path, mode="r", encoding=None):
            m = mock_open().return_value
            if "MESSAGES.DAT" in path.upper():
                m.read.return_value = mock_messages_data
            elif "CONTROL.DAT" in path.upper():
                m.read.return_value = mock_control_data
            return m

        logger = MagicMock()

        with patch("builtins.open", side_effect=side_effect):
            file_data, board_dict = core.load_data("dummy.qwk", logger)

            mock_zip_instance.extractall.assert_called()
            mock_run.assert_called()

            self.assertEqual(file_data, bytearray(mock_messages_data))
            self.assertEqual(board_dict.bbs_info.name, "Line1")

    @patch("zipfile.is_zipfile", return_value=True)
    @patch("zipfile.ZipFile")
    @patch("subprocess.run")
    @patch("os.name", "nt")
    def test_unzip_fail_rc127_raises_windows_tip(
        self, mock_run, mock_zipfile, mock_is_zipfile
    ):
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ["MESSAGES.DAT"]
        mock_zip_instance.extractall.side_effect = NotImplementedError()

        mock_run.return_value = MagicMock(returncode=127, stderr="not found")

        logger = MagicMock()
        with self.assertRaises(RuntimeError) as cm:
            core.load_data("dummy.qwk", logger)

        self.assertIn("unzip.exe", str(cm.exception))
        self.assertIn("return code 127", str(cm.exception))

    @patch("zipfile.is_zipfile", return_value=True)
    @patch("zipfile.ZipFile")
    @patch("subprocess.run")
    @patch("os.name", "nt")
    def test_unzip_missing_executable_raises_windows_tip(
        self, mock_run, mock_zipfile, mock_is_zipfile
    ):
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ["MESSAGES.DAT"]
        mock_zip_instance.extractall.side_effect = NotImplementedError()

        mock_run.side_effect = FileNotFoundError(
            "[WinError 2] The system cannot find the file specified"
        )

        logger = MagicMock()
        with self.assertRaises(RuntimeError) as cm:
            core.load_data("dummy.qwk", logger)

        self.assertIn("winget", str(cm.exception))
        self.assertIn("Git Bash", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
