import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from pyqwk.cli import main
from pyqwk.core import resolve_output_format, load_data, parse_messages

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_cli_accepts_qwk_and_rep_formats(monkeypatch, tmp_path):
    output_file = tmp_path / "output.qwk"
    input_file = tmp_path / "dummy.dat"
    input_file.write_bytes(b"Produced by pyqwk" + b" " * 111)

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "qwk", "-o", str(output_file)])
    try:
        with patch("pyqwk.cli.process_merged_files") as mock_process:
            main()
            assert mock_process.called
    except SystemExit as e:
        assert e.code == 0

    output_rep = tmp_path / "output.rep"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "rep", "-o", str(output_rep)])
    try:
        with patch("pyqwk.cli.process_merged_files") as mock_process:
            main()
            assert mock_process.called
    except SystemExit as e:
        assert e.code == 0


def test_cli_individual_files_with_qwk_rep_raises_error(monkeypatch, tmp_path, capsys):
    input_file = tmp_path / "dummy.dat"
    input_file.write_bytes(b"Produced by pyqwk" + b" " * 111)
    output_file = tmp_path / "output_folder"
    output_file.mkdir()

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "qwk", "-i", "-o", str(output_file)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "You cannot use --individual-files with QWK format." in captured.err

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "rep", "-i", "-o", str(output_file)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "You cannot use --individual-files with REP format." in captured.err


def test_cli_missing_output_path_for_binary_formats_raises_error(monkeypatch, tmp_path, capsys):
    input_file = tmp_path / "dummy.dat"
    input_file.write_bytes(b"Produced by pyqwk" + b" " * 111)

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "qwk"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "You cannot export to QWK format without providing an output path." in captured.err

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "rep"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "You cannot export to REP format without providing an output path." in captured.err

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "-F", "sqlite"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "You cannot export to SQLITE format without providing an output path." in captured.err


def test_resolve_output_format_handles_qwk_and_rep():
    assert resolve_output_format("qwk", None, "file") == "qwk"
    assert resolve_output_format("rep", None, "file") == "rep"
    assert resolve_output_format(None, "messages.qwk", "file") == "qwk"
    assert resolve_output_format(None, "replies.rep", "file") == "rep"


def test_gui_export_filetypes_contain_qwk_and_rep():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk'), \
         patch('pyqwk.gui.font'), \
         patch('pyqwk.gui.filedialog.asksaveasfilename') as mock_ask:

        from pyqwk.gui import QwkGuiApp

        mock_ask.return_value = ""  # Return empty string to prevent proceeding with actual export

        app = QwkGuiApp(mock_root)
        app.messages = [MagicMock()]

        app.export_messages()

        assert mock_ask.called
        kwargs = mock_ask.call_args[1]
        filetypes = kwargs.get("filetypes", [])

        has_qwk = any(name == "QWK archives" and ext == "*.qwk" for name, ext in filetypes)
        has_rep = any(name == "REP archives" and ext == "*.rep" for name, ext in filetypes)

        assert has_qwk, "QWK archives option not found in GUI export filetypes"
        assert has_rep, "REP archives option not found in GUI export filetypes"


def test_cli_qwk_export_end_to_end(tmp_path):
    import subprocess
    input_file = ROOT / "testdata" / "messages.dat"
    output_file = tmp_path / "actual.qwk"

    result = subprocess.run([
        sys.executable,
        str(ROOT / "qwk.py"),
        str(input_file),
        "-F", "qwk",
        "-o", str(output_file)
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert output_file.exists()

    # Verify we can load the exported QWK archive back successfully
    import logging
    logger = logging.getLogger("test")
    file_data, board_dict = load_data(str(output_file), logger)
    messages = list(parse_messages(file_data, None))
    assert len(messages) > 0
    assert messages[0].header.msgsubject.strip() == "New User"
