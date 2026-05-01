import logging
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pyqwk.cli import main
from pyqwk.core import load_data

def test_cli_invalid_loglevel(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["qwk", "test.qwk", "--loglevel", "INVALID"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "invalid choice: 'INVALID'" in capsys.readouterr().err

def test_load_data_sidecar_control_dat_corrupt(tmp_path, caplog):
    messages_path = tmp_path / "MESSAGES.DAT"
    control_path = tmp_path / "CONTROL.DAT"

    messages_path.write_bytes(b"Produced by PyQWK")
    control_path.write_bytes(b"Corrupt data") # Too short for _parse_control_dat

    logger = logging.getLogger("pyqwk.test")
    with caplog.at_level(logging.WARNING):
        load_data(str(messages_path), logger)
        assert "Found accompanying CONTROL.DAT but failed to parse it" in caplog.text

@patch('zipfile.is_zipfile', return_value=True)
@patch('zipfile.ZipFile')
@patch('subprocess.run')
@patch('os.listdir')
@patch('os.path.exists')
def test_load_data_unzip_missing_messages(mock_exists, mock_listdir, mock_run, mock_zipfile, mock_is_zipfile):
    # Zipfile fails
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.namelist.return_value = ['messages.dat'] # Avoid FileNotFoundError in zip block
    mock_zip_instance.extractall.side_effect = NotImplementedError()

    # Subprocess run "succeeds"
    mock_run.return_value = MagicMock(returncode=0)

    # But messages file is missing in the "extracted" list
    mock_listdir.return_value = ["random.txt"]
    mock_exists.return_value = False

    logger = logging.getLogger("pyqwk.test")
    # In classic mode, it checks for MESSAGES.DAT
    with pytest.raises(FileNotFoundError, match="found in the zip archive"):
        load_data("dummy.qwk", logger)

@patch('zipfile.is_zipfile', return_value=True)
@patch('zipfile.ZipFile')
@patch('subprocess.run')
@patch('os.listdir')
@patch('os.path.exists')
def test_load_data_unzip_missing_control(mock_exists, mock_listdir, mock_run, mock_zipfile, mock_is_zipfile, caplog):
    # Zipfile fails
    mock_zip_instance = mock_zipfile.return_value.__enter__.return_value
    mock_zip_instance.namelist.return_value = ['messages.dat'] # Avoid FileNotFoundError in zip block
    mock_zip_instance.extractall.side_effect = NotImplementedError()

    # Subprocess run "succeeds"
    mock_run.return_value = MagicMock(returncode=0)

    # Messages exists, but Control is missing
    mock_listdir.return_value = ["MESSAGES.DAT"]

    logger = logging.getLogger("pyqwk.test")

    with patch('builtins.open', mock_open(read_data=b"Produced by PyQWK")):
        with caplog.at_level(logging.WARNING):
            load_data("dummy.qwk", logger)
            assert "CONTROL.DAT not found in the zip archive" in caplog.text
