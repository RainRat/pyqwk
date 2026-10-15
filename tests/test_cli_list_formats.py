import pytest
import sys
from pyqwk.cli import QwkArgumentParser, FORMATS_INFO


def test_list_formats_flag(capsys, monkeypatch):
    """Test that qwk --list-formats displays available formats and exits with 0."""
    monkeypatch.setattr(sys, "argv", ["qwk", "--list-formats"])
    parser_holder = []

    # Mock stdout.isatty to False for plain text check
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    try:
        from pyqwk.cli import main
        main()
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    out = captured.out
    assert "Supported Export Formats:" in out
    for fmt_name in FORMATS_INFO:
        assert fmt_name in out


def test_list_formats_tty_colors(capsys, monkeypatch):
    """Test that qwk --list-formats displays ANSI color escapes when stdout is a TTY."""
    monkeypatch.setattr(sys, "argv", ["qwk", "--list-formats"])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    try:
        from pyqwk.cli import main
        main()
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    out = captured.out
    assert "\033[1;36mSupported Export Formats:\033[0m" in out


def test_invalid_format_error_message(capsys):
    """Test that passing an invalid format choice provides rich format details in error output."""
    parser = QwkArgumentParser(prog="qwk")
    parser.add_argument(
        "-F",
        "--format",
        choices=list(FORMATS_INFO.keys()),
    )

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["-F", "invalid_format"])

    assert exc.value.code != 0
    captured = capsys.readouterr()
    err = captured.err
    assert "Supported export formats:" in err
    assert "html" in err
    assert "markdown" in err
    assert "sqlite" in err
