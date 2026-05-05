import xml.etree.ElementTree as ET
import logging
from pathlib import Path
import pytest
from pyqwk.core import (
    load_data,
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
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


def test_xml_export_reimport_symmetry(tmp_path, baseline_path, logger):
    """Test that messages exported to XML can be re-imported and processed."""
    # 1. Export baseline to XML
    xml_path = tmp_path / "archive.xml"
    settings_export = _make_settings(
        format="xml", output_mode="file", output_path=str(xml_path)
    )
    process_merged_files([str(baseline_path)], settings_export, logger)

    assert xml_path.exists()

    # 2. Re-import from XML
    messages, board_dict = load_data(str(xml_path), logger)

    assert isinstance(messages, list)
    assert len(messages) > 0
    assert isinstance(messages[0], ParsedMessage)

    # Check that header data was preserved
    # The first message in baseline is msgnum 28
    assert messages[0].msgnum == 28
    assert messages[0].header.msgnum == 28
    assert messages[0].header.msgfrom.strip() == "GammaO #571 @0*1"

    # 3. Process re-imported data (e.g., convert to HTML)
    html_path = tmp_path / "archive.html"
    settings_html = _make_settings(
        format="html", output_mode="file", output_path=str(html_path)
    )

    # We can use process_merged_files on the xml path directly now
    process_merged_files([str(xml_path)], settings_html, logger)

    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "GammaO #571 @0*1" in html_content
    assert "New User" in html_content  # Subject


def test_xml_import_with_missing_fields(tmp_path, logger):
    """Test XML import handles missing or malformed fields gracefully."""
    root = ET.Element("messages")
    msg_el = ET.SubElement(root, "message")

    header_el = ET.SubElement(msg_el, "header")
    ET.SubElement(header_el, "msgfrom").text = "Test User"
    ET.SubElement(header_el, "confnum").text = "100"

    ET.SubElement(msg_el, "text").text = "Hello world"
    ET.SubElement(msg_el, "conference_name").text = "Test Conf"

    xml_path = tmp_path / "partial.xml"
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    messages, board_dict = load_data(str(xml_path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgfrom == "Test User"
    assert messages[0].confnum == 100
    assert messages[0].text == "Hello world"
    assert 100 in board_dict
    assert board_dict[100] == "Test Conf"


def test_xml_import_with_threading_metadata(tmp_path, logger):
    """Test XML import preserves threading metadata."""
    root = ET.Element("messages")
    msg_el = ET.SubElement(root, "message")

    header_el = ET.SubElement(msg_el, "header")
    ET.SubElement(header_el, "msgsubject").text = "Re: Test"
    ET.SubElement(header_el, "confnum").text = "1"

    ET.SubElement(msg_el, "depth").text = "2"
    ET.SubElement(msg_el, "thread_id").text = "42"
    ET.SubElement(msg_el, "parent_msgnum").text = "10"
    ET.SubElement(msg_el, "text").text = "Reply content"

    xml_path = tmp_path / "threaded.xml"
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    messages, board_dict = load_data(str(xml_path), logger)

    assert len(messages) == 1
    assert messages[0].depth == 2
    assert messages[0].thread_id == "42"
    assert messages[0].parent_msgnum == 10
    assert messages[0].text == "Reply content"


def test_xml_import_invalid_xml(tmp_path, logger):
    """Test that load_data raises ValueError for malformed XML."""
    xml_path = tmp_path / "broken.xml"
    xml_path.write_text("<messages><message>unclosed", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to load XML archive"):
        load_data(str(xml_path), logger)
