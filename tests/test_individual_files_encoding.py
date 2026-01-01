import logging
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.core import process_file, ProcessingSettings, ParsedMessage, MessageHeader

@pytest.fixture
def logger():
    return logging.getLogger("test_individual_files_encoding")

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
        encoding="cp437",
        conferences=None,
        quiet=True
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_individual_files_text_format_respects_encoding(tmp_path, logger, monkeypatch):
    """
    Verify that when format='text', individual files are written using the
    specified input encoding (e.g. cp437), preserving original byte values
    where possible.
    """
    # 0x82 in CP437 is 'é'. In UTF-8, 'é' is 0xC3 0xA9.
    text_content = "Resumé\r\n"

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='', msgtime='', msgto='', msgfrom='',
        msgsubject='', msgpassword='', refnum=None, numblocks=1,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )

    msg = ParsedMessage(
        text=text_content,
        msgnum=1, refnum=None, confnum=1, header=header
    )

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield msg

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    output_dir = tmp_path / "output_cp437"

    settings = _make_settings(
        format="text",
        encoding="cp437",
        output_path=str(output_dir)
    )

    process_file("dummy.qwk", settings, logger)

    files = list(output_dir.iterdir())
    assert len(files) == 1

    with open(files[0], "rb") as f:
        content = f.read()

    # Expect "Resum" + b'\x82' + ...
    assert b'\x82' in content
    assert b'\xc3\xa9' not in content

def test_individual_files_json_format_forces_utf8(tmp_path, logger, monkeypatch):
    """
    Verify that when format is NOT 'text' (e.g. 'json'), individual files
    are written using UTF-8, ignoring the input encoding setting.
    """
    text_content = "Resumé\r\n"

    header = MessageHeader(
        status=' ', msgnum=1, msgdate='', msgtime='', msgto='', msgfrom='',
        msgsubject='', msgpassword='', refnum=None, numblocks=1,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )

    msg = ParsedMessage(
        text=text_content,
        msgnum=1, refnum=None, confnum=1, header=header
    )

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield msg

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    output_dir = tmp_path / "output_json"

    settings = _make_settings(
        format="json",
        encoding="cp437",
        output_path=str(output_dir)
    )

    process_file("dummy.qwk", settings, logger)

    files = list(output_dir.iterdir())
    assert len(files) == 1

    with open(files[0], "rb") as f:
        content = f.read()

    # Should be UTF-8 encoded
    assert b'\xc3\xa9' in content
    assert b'\x82' not in content
