import pytest
from unittest.mock import patch, MagicMock
from pyqwk.core import expand_paths, load_data, _write_maildir
import os
import mailbox

def test_expand_paths_direct_maildir(tmp_path):
    """Test expand_paths with a direct Maildir path (covers lines 58-59)."""
    maildir_path = tmp_path / "test.maildir"
    maildir_path.mkdir()
    (maildir_path / "cur").mkdir()
    (maildir_path / "new").mkdir()
    (maildir_path / "tmp").mkdir()

    expanded = expand_paths([str(maildir_path)])
    assert str(maildir_path) in expanded
    assert len(expanded) == 1

def test_load_data_maildir_failure(tmp_path):
    """Test load_data with a failing Maildir (covers lines 2033-2034)."""
    maildir_path = tmp_path / "invalid.maildir"
    maildir_path.mkdir()
    (maildir_path / "cur").mkdir()
    (maildir_path / "new").mkdir()
    (maildir_path / "tmp").mkdir()

    with patch("mailbox.Maildir", side_effect=Exception("Mocked failure")):
        with pytest.raises(ValueError, match="Failed to load Maildir: Mocked failure"):
            load_data(str(maildir_path), MagicMock())

def test_write_maildir_no_output_path():
    """Test _write_maildir with output_path=None (covers line 4711)."""
    with pytest.raises(ValueError, match="Output path is required for Maildir export."):
        _write_maildir([], None)
