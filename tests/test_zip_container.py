import os
import zipfile
import logging
import pytest
from pyqwk.core import load_data, BLOCK_SIZE, MESSAGES_FILENAME, CONTROL_FILENAME

@pytest.fixture
def logger():
    return logging.getLogger("test_zip")

def test_load_zip_containing_json(tmp_path, logger):
    json_content = '[{"header": {"confnum": 1, "msgfrom": "TestAuthor", "msgsubject": "TestSubject", "msgdate": "01-01-24", "msgtime": "12:00", "status": " "}, "text": "Test message body"}]'
    json_file = tmp_path / "messages.json"
    json_file.write_text(json_content)

    zip_path = tmp_path / "container.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(json_file, "messages.json")

    messages, board_dict = load_data(str(zip_path), logger)

    assert len(messages) == 1
    assert messages[0].header.msgfrom == "TestAuthor"
    assert messages[0].text == "Test message body"
    assert "container.zip/messages.json" in messages[0].source_file

def test_load_zip_containing_nested_qwk(tmp_path, logger):
    # Create a dummy MESSAGES.DAT
    msg_dat = bytearray(BLOCK_SIZE * 2)
    msg_dat[0:BLOCK_SIZE] = "Produced by pyqwk".ljust(BLOCK_SIZE).encode('cp437')

    # 128-byte header
    # status ' ', msgnum 1, date '01-01-24', time '12:00', to 'All', from 'Author', subj 'Subj', pass '', ref 0, blocks 2, flag ' ', conf 1, log 0, net ' '
    # struct.pack('<c7s8s5s25s25s25s12s8s6scHHc', ...)
    import struct
    header = struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        b' ', b'      1', b'01-01-24', b'12:00', b'All'.ljust(25), b'Author'.ljust(25),
        b'Subj'.ljust(25), b''.ljust(12), b'       0', b'     2', b' ', 1, 0, b' '
    )
    msg_dat[BLOCK_SIZE:BLOCK_SIZE+128] = header

    # Create a dummy CONTROL.DAT
    control_content = [b"BBS Name", b"Loc", b"123", b"Sysop", b"1,ID", b"At", b"User", b"", b"", b"", b"0", b"1", b"General"]

    zip_path = tmp_path / "nested_qwk.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("subfolder/MESSAGES.DAT", msg_dat)
        z.writestr("subfolder/CONTROL.DAT", b"\r\n".join(control_content) + b"\r\n")

    file_data, board_dict = load_data(str(zip_path), logger)

    assert isinstance(file_data, bytearray)
    assert 1 in board_dict
    assert board_dict[1] == "General"
    assert board_dict.bbs_info.name == "BBS Name"

def test_load_zip_multiple_formats_priority(tmp_path, logger):
    # ZIP with both JSON and CSV. Should pick the first one (shallowest).
    # We'll put them at different depths to be sure.

    json_content = '[{"header": {"confnum": 1, "msgfrom": "JSON", "msgsubject": "JSON"}, "text": "JSON"}]'
    csv_content = 'confnum,msgfrom,msgsubject,text\n2,CSV,CSV,CSV'

    zip_path = tmp_path / "multi.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("a_json/messages.json", json_content)
        z.writestr("b_csv.csv", csv_content) # Shallowest

    messages, board_dict = load_data(str(zip_path), logger)

    # b_csv.csv is shallowest (0 slashes vs 1 slash)
    assert len(messages) == 1
    assert messages[0].header.msgfrom == "CSV"

def test_load_zip_empty_or_unsupported(tmp_path, logger):
    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("random.txt", "nothing interesting here")

    with pytest.raises(FileNotFoundError, match="No supported message files found"):
        load_data(str(zip_path), logger)
