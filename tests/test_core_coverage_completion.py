import xml.etree.ElementTree as ET
import logging
import pytest
from pyqwk.core import load_data, _parse_xml_messages

def test_sqlite_missing_file_error():
    logger = logging.getLogger("test")
    with pytest.raises(ValueError, match="Failed to load SQLite archive: unable to open database file"):
        load_data("non_existent_file.db", logger)

def test_xml_single_message_root():
    root = ET.Element("message")
    header = ET.SubElement(root, "header")
    ET.SubElement(header, "msgfrom").text = "RootUser"
    ET.SubElement(root, "text").text = "RootBody"

    messages = _parse_xml_messages(root)
    assert len(messages) == 1
    assert messages[0].header.msgfrom == "RootUser"
    assert messages[0].text == "RootBody"
