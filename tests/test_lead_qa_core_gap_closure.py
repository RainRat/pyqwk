import logging
import xml.etree.ElementTree as ET
import pytest
from pyqwk.core import load_data

def test_sqlite_import_non_existent_file(tmp_path):
    logger = logging.getLogger("pyqwk.tests")
    db_path = tmp_path / "non_existent.db"

    with pytest.raises(ValueError, match="Failed to load SQLite archive: unable to open database file"):
        load_data(str(db_path), logger)

def test_xml_import_single_message_root(tmp_path):
    logger = logging.getLogger("pyqwk.tests")

    root = ET.Element("message")
    header_el = ET.SubElement(root, "header")
    ET.SubElement(header_el, "msgfrom").text = "Root Author"
    ET.SubElement(header_el, "confnum").text = "1"
    ET.SubElement(root, "text").text = "Root text"

    xml_path = tmp_path / "single_root.xml"
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    messages, _ = load_data(str(xml_path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgfrom == "Root Author"
    assert messages[0].text == "Root text"
