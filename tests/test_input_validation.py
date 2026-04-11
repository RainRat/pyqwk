import logging
import zipfile
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import (
    load_data,
    process_merged_files,
    ProcessingSettings,
    MESSAGES_FILENAME
)

@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests.validation")
    logger.addHandler(logging.NullHandler())
    return logger

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_load_data_raises_if_messages_dat_missing_in_zip(
    tmp_path: Path, logger: logging.Logger
) -> None:
    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("OTHER.DAT", "some content")

    with pytest.raises(FileNotFoundError) as exc_info:
        load_data(str(zip_path), logger)

    assert MESSAGES_FILENAME in str(exc_info.value)
    assert "Neither" in str(exc_info.value)
    assert "found in the zip archive" in str(exc_info.value)

def test_process_merged_files_raises_if_stdout_with_output_path(
    tmp_path: Path, logger: logging.Logger
) -> None:
    settings = _make_settings(
        output_mode="stdout",
        output_path=str(tmp_path / "out.txt")
    )

    with pytest.raises(ValueError) as exc_info:
        process_merged_files(["dummy.qwk"], settings, logger)

    assert "Output path cannot be provided when output mode is stdout" in str(exc_info.value)

def test_process_merged_files_raises_if_file_mode_without_output_path(
    logger: logging.Logger
) -> None:
    settings = _make_settings(
        output_mode="file",
        output_path=None,
        individual_files=False
    )

    with pytest.raises(ValueError) as exc_info:
        process_merged_files(["dummy.qwk"], settings, logger)

    assert "output path is required when output mode is file" in str(exc_info.value)

def test_process_merged_files_raises_if_individual_files_without_output_path(
    logger: logging.Logger
) -> None:
    settings = _make_settings(
        individual_files=True,
        output_path=None
    )

    with pytest.raises(ValueError) as exc_info:
        process_merged_files(["dummy.qwk"], settings, logger)

    assert "output path is required when using individual files" in str(exc_info.value)
