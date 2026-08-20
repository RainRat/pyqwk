import sys
import pytest
from unittest.mock import patch
from pyqwk.cli import main


def test_missing_input_paths_error_message(capsys):
    """Verify that invoking CLI without arguments provides enhanced usage guidance."""
    with patch.object(sys, "argv", ["qwk"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 2

    captured = capsys.readouterr()
    assert "the following arguments are required: input_paths" in captured.err
    assert "To process or view an archive, pass one or more archive files or directories:" in captured.err
    assert "qwk archive.qwk --oneline" in captured.err
    assert "qwk --list-presets" in captured.err
    assert "qwk --help" in captured.err
