import logging
import os
from pathlib import Path
import pytest
from pyqwk.core import (
    load_data,
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    expand_paths,
)


@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"


@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger


def _make_settings(**overrides):
    defaults = dict(
        verbose=False,
        private=True,
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
        quiet=True,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)


def test_maildir_export_reimport_symmetry(tmp_path, baseline_path, logger):
    """Test that messages exported to Maildir can be re-imported and processed."""
    # 1. Export baseline to Maildir
    maildir_path = tmp_path / "test_maildir"
    settings_export = _make_settings(
        format="maildir", output_mode="file", output_path=str(maildir_path)
    )
    process_merged_files([str(baseline_path)], settings_export, logger)

    assert maildir_path.exists()
    assert (maildir_path / "cur").is_dir()
    assert (maildir_path / "new").is_dir()
    assert (maildir_path / "tmp").is_dir()

    # 2. Test expand_paths with Maildir
    expanded = expand_paths([str(tmp_path)])
    assert str(maildir_path) in expanded
    # Ensure it doesn't expand into files inside 'cur'
    for p in expanded:
        if p.startswith(str(maildir_path)):
            assert p == str(maildir_path)

    # 3. Re-import from Maildir
    messages, board_dict = load_data(str(maildir_path), logger)

    assert isinstance(messages, list)
    assert len(messages) > 0
    assert isinstance(messages[0], ParsedMessage)

    # Check that header data was preserved (baseline messages.dat has specific content)
    # The first message in testdata/messages.dat is expected to be msgnum 28 based on test_email_import.py
    # However, Maildir doesn't guarantee order, so we search.
    msg28 = next((m for m in messages if m.msgnum == 28), None)
    assert msg28 is not None
    assert msg28.header.msgfrom.strip() == "GammaO #571 @0*1"
    assert msg28.header.msgto.strip() == "All"
    assert msg28.header.msgsubject.strip() == "New User"

    # 4. Process re-imported data (e.g., convert to text)
    settings_text = _make_settings(
        format="text", output_mode="stdout"
    )
    # We can't easily capture stdout here without more complex setup,
    # but we can verify process_merged_files runs without error.
    process_merged_files([str(maildir_path)], settings_text, logger)


def test_maildir_auto_detection_by_extension(tmp_path, baseline_path, logger):
    """Test that .maildir extension triggers Maildir format."""
    maildir_path = tmp_path / "my_archive.maildir"
    settings_export = _make_settings(
        output_mode="file", output_path=str(maildir_path)
    )
    # resolve_output_format should pick 'maildir' based on extension
    from pyqwk.core import resolve_output_format
    fmt = resolve_output_format(None, str(maildir_path), "file")
    assert fmt == "maildir"

    settings_export.format = fmt
    process_merged_files([str(baseline_path)], settings_export, logger)
    assert (maildir_path / "cur").is_dir()
