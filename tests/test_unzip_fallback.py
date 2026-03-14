import unittest
from unittest.mock import patch, MagicMock, mock_open
import pyqwk.core as core

class TestUnzipFallback(unittest.TestCase):
    @patch('zipfile.is_zipfile', return_value=True)
    @patch('zipfile.ZipFile')
    @patch('subprocess.run')
    @patch('os.listdir')
    @patch('os.path.exists')
    def test_load_data_unzip_fallback(self, mock_exists, mock_listdir, mock_run, mock_zipfile, mock_is_zipfile):
        # Setup: Python's zipfile.open raises NotImplementedError (unsupported compression)
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ['MESSAGES.DAT', 'CONTROL.DAT']
        mock_zip_instance.open.side_effect = NotImplementedError("That compression method is not supported")

        # Mock listdir for the temporary directory
        mock_listdir.return_value = ['MESSAGES.DAT', 'CONTROL.DAT']
        mock_exists.return_value = True
        
        # Mock subprocess.run to simulate successful unzip
        mock_run.return_value = MagicMock(returncode=0)

        # Mock reading from the extracted files
        # MESSAGES.DAT needs some data, CONTROL.DAT needs 11+ lines
        mock_messages_data = b"MESSAGES DATA"
        mock_control_data = b"Line1\nLine2\nLine3\nLine4\nLine5\nLine6\nLine7\nLine8\nLine9\nLine10\n0\n"
        
        def side_effect(path, mode='r', encoding=None):
            m = mock_open().return_value
            if 'MESSAGES.DAT' in path.upper():
                m.read.return_value = mock_messages_data
            elif 'CONTROL.DAT' in path.upper():
                m.read.return_value = mock_control_data
            return m

        logger = MagicMock()
        
        with patch('builtins.open', side_effect=side_effect) as mock_file:
            # Run load_data
            file_data, board_dict = core.load_data("dummy.qwk", logger)

            # Assertions
            # 1. zipfile was tried first
            mock_zip_instance.open.assert_called()
            
            # 2. unzip fallback was triggered
            mock_run.assert_called()
            
            # 3. Data was read from extracted files
            self.assertEqual(file_data, bytearray(mock_messages_data))
            self.assertEqual(board_dict.bbs_info.name, "Line1")

    @patch('zipfile.is_zipfile', return_value=True)
    @patch('zipfile.ZipFile')
    @patch('subprocess.run')
    def test_load_data_unzip_failure(self, mock_run, mock_zipfile, mock_is_zipfile):
        # Setup: Python's zipfile fails, and unzip also fails
        mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
        mock_zip_instance.namelist.return_value = ['MESSAGES.DAT']
        mock_zip_instance.open.side_effect = NotImplementedError()

        # Mock unzip failure
        mock_run.return_value = MagicMock(returncode=9, stderr="unzip error message")

        logger = MagicMock()
        
        # Run load_data and expect RuntimeError
        with self.assertRaises(RuntimeError) as cm:
            core.load_data("dummy.qwk", logger)
        
        self.assertIn("unzip failed", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
