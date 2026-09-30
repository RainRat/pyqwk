import os
from pyqwk.cli import main
from pyqwk.core import ProcessingSettings


def test_cli_organize_by_conference_flag(tmp_path, monkeypatch):
    """Test that --organize-by-conference CLI flag sets settings.organize to True."""
    qwk_file = tmp_path / "test.qwk"
    qwk_file.write_bytes(b"dummy qwk content")
    out_dir = tmp_path / "output"

    captured_settings = []

    def mock_process_merged_files(input_paths, settings, logger):
        captured_settings.append(settings)

    monkeypatch.setattr("pyqwk.cli.process_merged_files", mock_process_merged_files)
    monkeypatch.setattr("sys.argv", ["qwk", str(qwk_file), "-i", "--organize-by-conference", "-o", str(out_dir)])

    main()

    assert len(captured_settings) == 1
    assert captured_settings[0].organize is True


def test_cli_organize_by_conf_alias(tmp_path, monkeypatch):
    """Test that --organize-by-conf CLI alias sets settings.organize to True."""
    qwk_file = tmp_path / "test.qwk"
    qwk_file.write_bytes(b"dummy qwk content")
    out_dir = tmp_path / "output"

    captured_settings = []

    def mock_process_merged_files(input_paths, settings, logger):
        captured_settings.append(settings)

    monkeypatch.setattr("pyqwk.cli.process_merged_files", mock_process_merged_files)
    monkeypatch.setattr("sys.argv", ["qwk", str(qwk_file), "-i", "--organize-by-conf", "-o", str(out_dir)])

    main()

    assert len(captured_settings) == 1
    assert captured_settings[0].organize is True
