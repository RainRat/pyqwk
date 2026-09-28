import pytest
from pyqwk.cli import QwkArgumentParser

def test_missing_input_paths_error_message(capsys):
    parser = QwkArgumentParser(prog="qwk")
    parser.add_argument("input_paths", nargs="+")

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "the following arguments are required: input_paths" in captured.err
    assert "To process or view an archive, pass one or more archive files or directories:" in captured.err
    assert "qwk archive.qwk --oneline" in captured.err
    assert "qwk --list-presets" in captured.err
