import os
import sys
import zipfile
import tarfile
import logging
import pytest
from unittest.mock import patch, MagicMock
from pyqwk.cli import main
from pyqwk.core import validate_archive, MessageHeader


def build_qwk_messages_data():
    first_block = b"Produced by pyqwk".ljust(128, b" ")
    hdr = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Hello",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" "
    )
    hdr_bytes = hdr.to_bytes()
    body_bytes = b"Hello Alice\xe3".ljust(128, b" ")
    return first_block + hdr_bytes + body_bytes


def test_cli_validate_all_valid(tmp_path, caplog):
    valid_zip = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("MESSAGES.DAT", build_qwk_messages_data())
        zf.writestr("CONTROL.DAT", b"Test BBS\nCity\n123\nSysop\n0\n0\nDate\n0\n0\n1\n1\nGeneral")

    with patch.object(sys, "argv", ["qwk", str(valid_zip), "--validate"]):
        with pytest.raises(SystemExit) as exc:
            with caplog.at_level(logging.INFO):
                main()
        assert exc.value.code == 0
    assert "File:" in caplog.text
    assert "VALID" in caplog.text


def test_cli_validate_all_valid_with_mock_tty(tmp_path, caplog):
    valid_zip = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("MESSAGES.DAT", build_qwk_messages_data())
        zf.writestr("CONTROL.DAT", b"Test BBS\nCity\n123\nSysop\n0\n0\nDate\n0\n0\n1\n1\nGeneral")

    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = True

    with patch.object(sys, "argv", ["qwk", str(valid_zip), "--validate"]):
        with patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as exc:
                with caplog.at_level(logging.INFO):
                    main()
            assert exc.value.code == 0
    assert "File:" in caplog.text


def test_cli_validate_invalid_file(tmp_path, caplog):
    invalid_zip = tmp_path / "invalid.zip"
    with zipfile.ZipFile(invalid_zip, "w") as zf:
        zf.writestr("MESSAGES.DAT", b"too_short")

    with patch.object(sys, "argv", ["qwk", str(invalid_zip), "--validate"]):
        with pytest.raises(SystemExit) as exc:
            with caplog.at_level(logging.INFO):
                main()
        assert exc.value.code == 1
    assert "INVALID" in caplog.text


def test_cli_validate_multiple_mixed_files(tmp_path, caplog):
    valid_zip = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("MESSAGES.DAT", build_qwk_messages_data())
        zf.writestr("CONTROL.DAT", b"Test BBS\nCity\n123\nSysop\n0\n0\nDate\n0\n0\n1\n1\nGeneral")

    invalid_zip = tmp_path / "invalid.zip"
    with zipfile.ZipFile(invalid_zip, "w") as zf:
        zf.writestr("MESSAGES.DAT", b"too_short")

    with patch.object(sys, "argv", ["qwk", str(valid_zip), str(invalid_zip), "--validate"]):
        with pytest.raises(SystemExit) as exc:
            with caplog.at_level(logging.INFO):
                main()
        assert exc.value.code == 1


def test_validate_archive_non_maildir_directory(tmp_path):
    not_maildir = tmp_path / "not_maildir_dir"
    not_maildir.mkdir()
    res = validate_archive(str(not_maildir), logging.getLogger("test"))
    assert res["valid"] is False
    assert any("Path is a directory but not a valid Maildir" in err for err in res["errors"])


def test_validate_archive_zip_missing_control(tmp_path):
    zip_path = tmp_path / "missing_control.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("MESSAGES.DAT", build_qwk_messages_data())

    res = validate_archive(str(zip_path), logging.getLogger("test"))
    assert res["valid"] is True
    assert any("CONTROL.DAT is missing from the QWK archive" in warn for warn in res["warnings"])


def test_validate_archive_zip_misaligned_messages(tmp_path):
    zip_path = tmp_path / "misaligned.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("MESSAGES.DAT", b"not_128_multiple_misaligned")

    res = validate_archive(str(zip_path), logging.getLogger("test"))
    assert res["valid"] is False
    assert any("is not a multiple of 128 bytes" in err for err in res["errors"])


def test_validate_archive_zip_corrupt(tmp_path):
    zip_path = tmp_path / "corrupt_zip.zip"
    zip_path.write_text("not a zip file at all")

    res = validate_archive(str(zip_path), logging.getLogger("test"))
    assert res["valid"] is False
    assert any("ZIP archive read error" in err or "Unsupported or corrupted" in err for err in res["errors"])


def test_validate_archive_zip_batch_recursive(tmp_path):
    zip_path = tmp_path / "batch.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("msg.json", '[{"header": {"msgfrom": "Bob", "msgto": "Alice", "msgsubject": "Test", "msgnum": 1}, "text": "Hi"}]')

    res = validate_archive(str(zip_path), logging.getLogger("test"))
    assert "warnings" in res


def test_validate_archive_tar_good(tmp_path):
    tar_path = tmp_path / "valid.tar"
    with tarfile.open(tar_path, "w") as tf:
        msg_file = tmp_path / "MESSAGES.DAT"
        msg_file.write_bytes(build_qwk_messages_data())
        tf.add(msg_file, arcname="MESSAGES.DAT")

        ctrl_file = tmp_path / "CONTROL.DAT"
        ctrl_file.write_bytes(b"Test BBS\nCity\n123\nSysop\n0\n0\nDate\n0\n0\n1\n1\nGeneral")
        tf.add(ctrl_file, arcname="CONTROL.DAT")

    res = validate_archive(str(tar_path), logging.getLogger("test"))
    assert res["valid"] is True


def test_validate_archive_tar_missing_control(tmp_path):
    tar_path = tmp_path / "missing_control.tar"
    with tarfile.open(tar_path, "w") as tf:
        msg_file = tmp_path / "MESSAGES.DAT"
        msg_file.write_bytes(build_qwk_messages_data())
        tf.add(msg_file, arcname="MESSAGES.DAT")

    res = validate_archive(str(tar_path), logging.getLogger("test"))
    assert res["valid"] is True
    assert any("CONTROL.DAT is missing from the QWK archive" in warn for warn in res["warnings"])


def test_validate_archive_tar_misaligned_messages(tmp_path):
    tar_path = tmp_path / "misaligned.tar"
    with tarfile.open(tar_path, "w") as tf:
        msg_file = tmp_path / "MESSAGES.DAT"
        msg_file.write_bytes(b"not_128_bytes_misaligned_tar")
        tf.add(msg_file, arcname="MESSAGES.DAT")

    res = validate_archive(str(tar_path), logging.getLogger("test"))
    assert res["valid"] is False
    assert any("is not a multiple of 128 bytes" in err for err in res["errors"])


def test_validate_archive_tar_corrupt(tmp_path):
    tar_path = tmp_path / "corrupt.tar"
    tar_path.write_text("not a tar file at all")

    res = validate_archive(str(tar_path), logging.getLogger("test"))
    assert res["valid"] is False


def test_validate_archive_tar_batch_recursive(tmp_path):
    tar_path = tmp_path / "batch.tar"
    with tarfile.open(tar_path, "w") as tf:
        msg_file = tmp_path / "msg.json"
        msg_file.write_text('[{"header": {"msgfrom": "Bob", "msgto": "Alice", "msgsubject": "Test", "msgnum": 1}, "text": "Hi"}]')
        tf.add(msg_file, arcname="msg.json")

    res = validate_archive(str(tar_path), logging.getLogger("test"))
    assert "warnings" in res


def test_validate_archive_unsupported_compressed(tmp_path):
    unsupported_path = tmp_path / "unsupported.tgz"
    unsupported_path.write_text("some random bytes")

    res = validate_archive(str(unsupported_path), logging.getLogger("test"))
    assert res["valid"] is False
