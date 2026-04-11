import logging
from unittest.mock import patch
import pytest
from dataclasses import replace

from pyqwk.core import (process_merged_files,
    show_info,
    ProcessingSettings,
    BBSInfo,
    ConferenceMap,
    _write_markdown_index
)

@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )

def test_index_bbs_name_coverage(tmp_path, logger, default_settings):
    """Test that BBS name is included in the index title when present."""
    output_dir = tmp_path / "index_meta"
    settings = replace(
        default_settings,
        individual_files=True,
        format='html',
        output_mode='file',
        output_path=str(output_dir)
    )

    # Mock BBS info
    bbs_info = BBSInfo()
    bbs_info.name = "Coverage BBS"

    board_dict = ConferenceMap()
    board_dict.bbs_info = bbs_info
    board_dict[1] = "General"

    # Create a minimal messages.dat content (Produced header + 1 message)
    import struct
    header = struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        b' ', b"1".ljust(7, b' '), b"01-01-90", b"12:00",
        b"To".ljust(25, b' '), b"From".ljust(25, b' '), b"Subj".ljust(25, b' '),
        b"".ljust(12, b' '), b"0".ljust(8, b' '),
        b"1".ljust(6, b' '), # 1 total block
        b' ', 1, 1, b' '
    )
    mock_data = bytearray(b'Produced '.ljust(128, b' ') + header)

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (mock_data, board_dict)
        process_merged_files(['mock.qwk'], settings, logger)

    index_path = output_dir / "index.html"
    assert index_path.exists()
    content = index_path.read_text()
    assert "Coverage BBS Message Archive" in content

def test_show_info_location_coverage(capsys, logger, default_settings):
    """Test that BBS Location is displayed in show_info if present."""
    bbs_info = BBSInfo()
    bbs_info.name = "Test BBS"
    bbs_info.location = "Saskatoon, SK"

    board_dict = ConferenceMap()
    board_dict.bbs_info = bbs_info

    import struct
    header = struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        b' ', b"1".ljust(7, b' '), b"01-01-90", b"12:00",
        b"To".ljust(25, b' '), b"From".ljust(25, b' '), b"Subj".ljust(25, b' '),
        b"".ljust(12, b' '), b"0".ljust(8, b' '),
        b"1".ljust(6, b' '),
        b' ', 1, 1, b' '
    )
    mock_data = bytearray(b'Produced '.ljust(128, b' ') + header)

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (mock_data, board_dict)
        show_info(['mock.qwk'], default_settings, logger)

    captured = capsys.readouterr()
    assert "Location: Saskatoon, SK" in captured.out

def test_markdown_index_escaping(tmp_path):
    """Verify that subjects with Markdown brackets are escaped in the index."""
    output_dir = tmp_path / "md_esc"
    output_dir.mkdir()

    by_conf = {
        (1, "General"): [
            {
                'conf_num': 1,
                'conf_name': 'General',
                'subject': 'Subject [with] brackets',
                'from': 'User',
                'to': 'All',
                'date': '01-01-23',
                'msgnum': 1,
                'path': 'msg1.md'
            }
        ]
    }

    _write_markdown_index(by_conf, "Archive", str(output_dir))

    index_path = output_dir / "README.md"
    content = index_path.read_text()
    # If not escaped, it would be [Subject [with] brackets](msg1.md)
    # If escaped correctly, it should be [Subject \[with\] brackets](msg1.md)
    assert "[Subject \\[with\\] brackets](msg1.md)" in content
