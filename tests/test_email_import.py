import logging
from pathlib import Path
import pytest
from pyqwk.core import (
    load_data,
    process_merged_files,
    ProcessingSettings,
    ParsedMessage
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

def test_mbox_export_reimport_symmetry(tmp_path, baseline_path, logger):
    """Test that messages exported to MBOX can be re-imported and processed."""
    # 1. Export baseline to MBOX
    mbox_path = tmp_path / "archive.mbox"
    settings_export = _make_settings(
        format="mbox",
        output_mode="file",
        output_path=str(mbox_path)
    )
    process_merged_files([str(baseline_path)], settings_export, logger)

    assert mbox_path.exists()

    # 2. Re-import from MBOX
    messages, board_dict = load_data(str(mbox_path), logger)

    assert isinstance(messages, list)
    assert len(messages) > 0
    assert isinstance(messages[0], ParsedMessage)

    # Check that header data was preserved
    assert messages[0].msgnum == 28
    assert messages[0].header.msgnum == 28
    assert messages[0].header.msgfrom.strip() == "GammaO #571 @0*1"
    # mbox/email extraction might add trailing whitespace or normalize it
    assert messages[0].header.msgto.strip() == "All"
    assert messages[0].header.msgsubject.strip() == "New User"

    # 3. Process re-imported data (e.g., convert to HTML)
    html_path = tmp_path / "archive.html"
    settings_html = _make_settings(
        format="html",
        output_mode="file",
        output_path=str(html_path)
    )

    process_merged_files([str(mbox_path)], settings_html, logger)

    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "GammaO #571 @0*1" in html_content
    assert "New User" in html_content

def test_eml_export_reimport_symmetry(tmp_path, baseline_path, logger):
    """Test that messages exported to EML can be re-imported and processed."""
    # 1. Export baseline to EML (merged EML is double newline separated)
    eml_path = tmp_path / "archive.eml"
    settings_export = _make_settings(
        format="eml",
        output_mode="file",
        output_path=str(eml_path)
    )
    process_merged_files([str(baseline_path)], settings_export, logger)

    assert eml_path.exists()

    # 2. Re-import from EML
    messages, board_dict = load_data(str(eml_path), logger)

    assert isinstance(messages, list)
    assert len(messages) == 1 # load_data for EML returns only one message currently
    assert isinstance(messages[0], ParsedMessage)

    assert messages[0].msgnum == 28
    assert messages[0].header.msgfrom.strip() == "GammaO #571 @0*1"

def test_email_import_with_metadata(tmp_path, logger):
    """Test email import correctly handles X-QWK metadata headers."""
    eml_content = (
        "From: Alice\n"
        "To: Bob\n"
        "Subject: Hello\n"
        "Date: Mon, 1 Jan 2024 10:00:00 +0000\n"
        "X-QWK-Conference: 123\n"
        "X-QWK-Conference-Name: Chat Room\n"
        "X-QWK-Message-Number: 456\n"
        "X-QWK-Status: +\n"
        "X-QWK-Attachments: file1.txt;file2.jpg\n"
        "\n"
        "Body content here.\n"
    )
    eml_path = tmp_path / "test.eml"
    eml_path.write_text(eml_content)

    messages, board_dict = load_data(str(eml_path), logger)

    assert len(messages) == 1
    msg = messages[0]
    assert msg.header.msgfrom == "Alice"
    assert msg.header.msgto == "Bob"
    assert msg.header.msgsubject == "Hello"
    assert msg.confnum == 123
    assert msg.confname == "Chat Room"
    assert msg.msgnum == 456
    assert msg.header.status == "+"
    assert msg.attachments == ["file1.txt", "file2.jpg"]
    assert msg.text.strip() == "Body content here."
    assert board_dict[123] == "Chat Room"
