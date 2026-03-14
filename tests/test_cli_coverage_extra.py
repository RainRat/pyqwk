import sys
import pytest
import logging
from pathlib import Path
from unittest.mock import MagicMock
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
    assert "No supported message archives were found" in caplog.text

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

def test_individual_files_missing_output_path_multiple_inputs(monkeypatch, testdata_dir, capsys):
    input1 = testdata_dir / "test1_qwk.zip"
    input2 = testdata_dir / "test2_qwk.zip"
    # --individual-files but no -o with multiple inputs should still error
    monkeypatch.setattr(sys, "argv", ["qwk", str(input1), str(input2), "--individual-files"])

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "You must provide an output folder when saving messages as individual files." in stderr

def test_individual_files_default_output_path(monkeypatch, testdata_dir, capsys):
    input_file = testdata_dir / "test1_qwk.zip"
    # --individual-files but no -o with single input should succeed and use default folder
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--individual-files", "--dry-run"])

    # Mock process_merged_files to avoid actual dry run logic if needed,
    # but here we just want to see if it reaches the processing stage without exiting
    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", lambda *args: None)
        main()

    # Verify we didn't exit with error

def test_multiple_inputs_without_output_directory(monkeypatch, testdata_dir, capsys):
    input1 = testdata_dir / "test1_qwk.zip"
    input2 = testdata_dir / "test2_qwk.zip"

    # Missing -o option should now default to merging to stdout
    monkeypatch.setattr(sys, "argv", ["qwk", str(input1), str(input2)])

    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        # Mock process_merged_files to avoid actual processing
        mock_merge = MagicMock()
        m.setattr(cli, "process_merged_files", mock_merge)
        main()

        mock_merge.assert_called_once()
        settings = mock_merge.call_args[0][1]
        assert settings.merge is True
        assert settings.output_mode == 'stdout'

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

def test_merge_mode_error(monkeypatch, testdata_dir, caplog):
    from unittest.mock import MagicMock
    input_file = testdata_dir / "messages.dat"
    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--merge"])

    import pyqwk.cli as cli
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", MagicMock(side_effect=OSError("Merge failure")))
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            assert "Merge failure" in caplog.text
