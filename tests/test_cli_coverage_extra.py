import sys
import os
import pytest
import logging
from pathlib import Path
from pyqwk.cli import main

@pytest.fixture
def testdata_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata"

def test_no_valid_qwk_files_found(monkeypatch, tmp_path, caplog):
    # Pass an empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    monkeypatch.setattr(sys, "argv", ["qwk", str(empty_dir)])

    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc:
            main()

    assert exc.value.code == 1
    assert "No valid QWK files were found" in caplog.text

def test_individual_files_output_not_a_directory(monkeypatch, tmp_path, testdata_dir, capsys):
    input_file = testdata_dir / "messages.dat"
    # Create a file where a directory is expected
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("not a dir")

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--individual-files", "-o", str(not_a_dir)])

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "The output path must be a folder when saving messages as individual files." in stderr

def test_individual_files_missing_output_path(monkeypatch, testdata_dir, capsys):
    input_file = testdata_dir / "messages.dat"
    # --individual-files but no -o
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--individual-files"])

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "You must provide an output folder when saving messages as individual files." in stderr

def test_multiple_inputs_without_output_directory(monkeypatch, testdata_dir, capsys):
    input1 = testdata_dir / "test1_qwk.zip"
    input2 = testdata_dir / "test2_qwk.zip"

    # Missing -o option
    monkeypatch.setattr(sys, "argv", ["qwk", str(input1), str(input2)])

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "You must provide an output folder when processing more than one file." in stderr

def test_individual_eml_output_not_a_directory(monkeypatch, tmp_path, testdata_dir, capsys):
    input_file = testdata_dir / "messages.dat"
    not_a_dir = tmp_path / "file_eml.txt"
    not_a_dir.write_text("not a dir")

    # --format eml with -o pointing to a file
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--format", "eml", "-o", str(not_a_dir)])

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "The output path must be a folder when saving messages as individual EML files." in stderr

def test_invalid_date_format_error(monkeypatch, testdata_dir, capsys):
    input_file = testdata_dir / "messages.dat"

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--after", "01-01-2023"])

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "The date format for '01-01-2023' is invalid. Please use YYYY-MM-DD." in stderr

def test_info_mode_setup(monkeypatch, testdata_dir):
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--info"])

    # Mock show_info to avoid actual execution which might be complex to mock fully
    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        m.setattr(cli, "show_info", lambda *args: None)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

def test_stats_mode_setup(monkeypatch, testdata_dir):
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--stats"])

    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        m.setattr(cli, "show_stats", lambda *args: None)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

def test_merge_mode_setup(monkeypatch, testdata_dir):
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--merge"])

    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", lambda *args: None)
        # main() for merge doesn't sys.exit(0) explicitly at the end, it just returns
        main()

def test_individual_files_mode_setup(monkeypatch, testdata_dir, tmp_path):
    input_file = testdata_dir / "messages.dat"
    output_dir = tmp_path / "out_indiv"
    output_dir.mkdir()

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--individual-files", "-o", str(output_dir)])

    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        m.setattr(cli, "process_file", lambda *args: None)
        main()
