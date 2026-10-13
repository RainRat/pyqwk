import sys
import pytest
from pyqwk.cli import FORMATS_INFO, main


def test_list_formats_action_plain(capsys, monkeypatch):
    """Test --list-formats outputs supported export formats in plain text when not a TTY."""
    monkeypatch.setattr(sys, "argv", ["qwk", "--list-formats"])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Supported Export Formats:" in captured.out
    for fmt_name in FORMATS_INFO:
        assert fmt_name in captured.out


def test_list_formats_action_tty(capsys, monkeypatch):
    """Test --list-formats outputs formatted export formats with ANSI colors when TTY."""
    monkeypatch.setattr(sys, "argv", ["qwk", "--list-formats"])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "\033[1;36mSupported Export Formats:\033[0m" in captured.out
    for fmt_name in FORMATS_INFO:
        assert fmt_name in captured.out


def test_invalid_format_error_message(capsys, monkeypatch):
    """Test passing an invalid format choice triggers QwkArgumentParser error with FORMATS_INFO."""
    monkeypatch.setattr(sys, "argv", ["qwk", "archive.qwk", "-F", "invalid_fmt"])

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "invalid choice: 'invalid_fmt'" in captured.err
    assert "Supported export formats:" in captured.err
    for fmt_name in FORMATS_INFO:
        assert fmt_name in captured.err
