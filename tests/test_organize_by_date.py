import os
import logging
from pathlib import Path
from pyqwk.core import ProcessingSettings, process_file

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=None,
        encoding="latin1",
        organize_by_date=True,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_organize_by_date(tmp_path: Path):
    logger = logging.getLogger("pyqwk.tests")
    test_data_dir = Path(__file__).resolve().parents[1] / "testdata"
    input_file = test_data_dir / "messages.dat"
    output_dir = tmp_path / "date_org"

    settings = _make_settings(output_path=str(output_dir))

    # messages.dat message has date "07-21-94" -> 1994/07
    process_file(str(input_file), settings, logger)

    expected_dir = output_dir / "1994" / "07"
    assert expected_dir.exists()
    assert expected_dir.is_dir()

    files = list(expected_dir.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith("003-00028")

def test_organize_by_date_and_conf(tmp_path: Path):
    logger = logging.getLogger("pyqwk.tests")
    test_data_dir = Path(__file__).resolve().parents[1] / "testdata"
    input_file = test_data_dir / "messages.dat"
    output_dir = tmp_path / "date_conf_org"

    settings = _make_settings(
        output_path=str(output_dir),
        organize=True
    )

    # messages.dat message has date "07-21-94" and conf 3 ("New User")
    process_file(str(input_file), settings, logger)

    # Expected: 1994 / 07 / 003-unknown
    expected_dir = output_dir / "1994" / "07" / "003-unknown"
    assert expected_dir.exists()
    assert expected_dir.is_dir()

def test_organize_by_date_index_html(tmp_path: Path):
    logger = logging.getLogger("pyqwk.tests")
    test_data_dir = Path(__file__).resolve().parents[1] / "testdata"
    input_file = test_data_dir / "messages.dat"
    output_dir = tmp_path / "date_index"

    settings = _make_settings(
        output_path=str(output_dir),
        format="html"
    )

    process_file(str(input_file), settings, logger)

    index_file = output_dir / "index.html"
    assert index_file.exists()
    content = index_file.read_text()

    # Check that relative path in index is correct
    # It should be 1994/07/filename
    import re
    match = re.search(r'href="([^"]+)"', content)
    assert match
    rel_path = match.group(1)
    assert rel_path.replace("\\", "/").startswith("1994/07/")

def test_organize_by_date_attachments(tmp_path: Path):
    logger = logging.getLogger("pyqwk.tests")
    test_data_dir = Path(__file__).resolve().parents[1] / "testdata"
    # We need a file with attachments.
    # test_binary_detection.py uses some text, but we need it in a file processable by process_file.
    # For simplicity, we can mock the attachment extraction or just check the prefix calculation logic if we trust it.
    # Let's create a dummy file with UUE.

    dummy_qwk = tmp_path / "dummy.qwk"
    # A minimal QWK header + one message with UUE
    # Actually, process_file calls load_data, which handles raw QWK or others.
    # Easiest is to use a .json file as input since pyqwk supports it.

    import json
    msg_data = [{
        "header": {
            "confnum": 1,
            "msgnum": 100,
            "msgdate": "10-25-23",
            "msgtime": "12:00",
            "msgfrom": "Alice",
            "msgto": "Bob",
            "msgsubject": "Test Attach",
            "status": " "
        },
        "text": "Hello\nbegin 644 test.txt\n#0V%T\n`\nend\n",
        "conference": "General"
    }]

    input_json = tmp_path / "test.json"
    input_json.write_text(json.dumps(msg_data))

    output_dir = tmp_path / "attach_org"
    settings = _make_settings(
        output_path=str(output_dir),
        format="html",
        extract_attachments=True
    )

    process_file(str(input_json), settings, logger)

    # Subdir: 2023/10/001-00100-test_attach.html
    # Attachments: attachments/test.txt (relative to output_dir)
    # Relative link in HTML: ../../attachments/test.txt

    msg_file = output_dir / "2023" / "10" / "001-00100-test_attach.html"
    assert msg_file.exists()
    content = msg_file.read_text()
    assert "../../attachments/test.txt" in content.replace("\\", "/")

    attach_file = output_dir / "attachments" / "test.txt"
    assert attach_file.exists()
