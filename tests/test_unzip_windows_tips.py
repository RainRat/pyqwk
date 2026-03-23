import unittest
from unittest.mock import patch, MagicMock
import pyqwk.core as core

class TestUnzipWindowsTips(unittest.TestCase):
    @patch('zipfile.is_zipfile', return_value=True)
    @patch('zipfile.ZipFile')
    @patch('subprocess.run')
    @patch('os.name', 'nt')
    def test_unzip_fail_rc127_windows_tip(self, mock_run, mock_zipfile, mock_is_zipfile):
        """Test that return code 127 on Windows includes the unzip.exe tip."""
        # Setup: Python's zipfile fails
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ['MESSAGES.DAT']
        mock_zip_instance.open.side_effect = NotImplementedError()

        # Mock unzip failure with return code 127
        mock_run.return_value = MagicMock(returncode=127, stderr="not found")

        logger = MagicMock()
        with self.assertRaises(RuntimeError) as cm:
            core.load_data("dummy.qwk", logger)

        self.assertIn("unzip.exe", str(cm.exception))
        self.assertIn("return code 127", str(cm.exception))

    @patch('zipfile.is_zipfile', return_value=True)
    @patch('zipfile.ZipFile')
    @patch('subprocess.run')
    @patch('os.name', 'nt')
    def test_unzip_missing_windows_tip(self, mock_run, mock_zipfile, mock_is_zipfile):
        """Test that [WinError 2] on Windows includes the unzip.exe tip."""
        # Setup: Python's zipfile fails
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ['MESSAGES.DAT']
        mock_zip_instance.open.side_effect = NotImplementedError()

        # Mock subprocess.run raising FileNotFoundError (simulating missing command)
        mock_run.side_effect = FileNotFoundError("[WinError 2] The system cannot find the file specified")

        logger = MagicMock()
        with self.assertRaises(RuntimeError) as cm:
            core.load_data("dummy.qwk", logger)

        self.assertIn("unzip.exe", str(cm.exception))
        self.assertIn("tool is missing", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
