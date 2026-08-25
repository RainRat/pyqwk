import os
import io
import tarfile
import logging
import pytest

from pyqwk.core import (
    _cleanup_temp_files,
    _pack_directory_to_archive,
    _temp_files_to_clean,
    _order_messages_by_thread,
    process_merged_files,
    show_list_bbs,
    show_threads,
    show_list_authors,
    show_list_subjects,
    validate_archive,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    ConferenceMap,
)
from pyqwk.cli import main


@pytest.fixture
def test_logger():
    return logging.getLogger("pyqwk.test")


def test_cleanup_temp_files_nonexistent_path(tmp_path):
    non_existent = str(tmp_path / "does_not_exist.tmp")
    _temp_files_to_clean.append(non_existent)
    try:
        _cleanup_temp_files()
        assert not os.path.exists(non_existent)
    finally:
        if non_existent in _temp_files_to_clean:
            _temp_files_to_clean.remove(non_existent)


def test_pack_directory_to_archive_no_parent_dir_and_tar_bz2(tmp_path, monkeypatch, test_logger):
    monkeypatch.chdir(tmp_path)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "test.txt").write_text("hello")

    # Test .tar.bz2 without parent directory in path
    archive_path_bz2 = "archive.tar.bz2"
    _pack_directory_to_archive(str(src_dir), archive_path_bz2, test_logger)
    assert os.path.exists(archive_path_bz2)

    # Test plain .tar without parent directory in path
    archive_path_tar = "archive.tar"
    _pack_directory_to_archive(str(src_dir), archive_path_tar, test_logger)
    assert os.path.exists(archive_path_tar)


def test_process_merged_files_dry_run_archive_pack(tmp_path, test_logger):
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(tmp_path / "output.zip"),
        encoding="utf-8",
        dry_run=True,
    )

    # Should skip _pack_directory_to_archive because dry_run is True
    process_merged_files([], settings, test_logger)


def test_show_list_bbs_branch_coverage(tmp_path, test_logger, monkeypatch):
    hdr1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-20", msgtime="10:00",
        msgto="All", msgfrom="A", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=None, lognum=0, nettag=""
    )
    msg1 = ParsedMessage(text="1", msgnum=1, refnum=None, confnum=1, header=hdr1)
    object.__setattr__(msg1, "datetime", None)

    hdr2 = MessageHeader(
        status=" ", msgnum=2, msgdate="01-02-20", msgtime="10:00",
        msgto="All", msgfrom="A", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg2 = ParsedMessage(text="2", msgnum=2, refnum=None, confnum=1, header=hdr2)

    hdr3 = MessageHeader(
        status=" ", msgnum=3, msgdate="01-03-20", msgtime="10:00",
        msgto="All", msgfrom="A", msgsubject="Subj", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg3 = ParsedMessage(text="3", msgnum=3, refnum=None, confnum=1, header=hdr3)

    board_dict = ["not", "a", "dict"]  # isinstance(board_dict, dict) -> False

    def mock_load_data(input_path, logger, encoding):
        return [msg1, msg2, msg3], board_dict

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="utf-8"
    )

    show_list_bbs(["dummy.qwk"], settings, test_logger)


def test_order_messages_by_thread_cycle_reported_twice(test_logger):
    hdr1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-20", msgtime="10:00",
        msgto="All", msgfrom="A", msgsubject="Subj 1", msgpassword="",
        refnum=2, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg1 = ParsedMessage(text="1", msgnum=1, refnum=2, confnum=1, header=hdr1)

    hdr2 = MessageHeader(
        status=" ", msgnum=2, msgdate="01-01-20", msgtime="10:01",
        msgto="All", msgfrom="B", msgsubject="Re: Subj 1", msgpassword="",
        refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg2 = ParsedMessage(text="2", msgnum=2, refnum=1, confnum=1, header=hdr2)

    res = _order_messages_by_thread([msg1, msg2])
    assert len(res) == 2


def test_validate_archive_tar_extractfile_returns_none(tmp_path, test_logger, monkeypatch):
    tar_path = tmp_path / "test.tar"
    with tarfile.open(tar_path, "w") as tar:
        hdr = MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-20", msgtime="10:00",
            msgto="All", msgfrom="A", msgsubject="Subj", msgpassword="",
            refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
        )
        record = hdr.to_bytes()
        buf = record.ljust(128, b"\x00")
        ti = tarfile.TarInfo(name="messages.dat")
        ti.size = len(buf)
        tar.addfile(ti, fileobj=io.BytesIO(buf))

    monkeypatch.setattr(tarfile.TarFile, "extractfile", lambda self, member: None)

    res = validate_archive(str(tar_path), test_logger)
    assert res["valid"] is True


def test_show_threads_authors_subjects_filters(tmp_path, test_logger, monkeypatch):
    hdr1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-20", msgtime="10:00",
        msgto="Bob", msgfrom="Alice", msgsubject="Subj 1", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg1 = ParsedMessage(text="1", msgnum=1, refnum=None, confnum=1, header=hdr1, bbs_name="")

    hdr2 = MessageHeader(
        status=" ", msgnum=2, msgdate="01-05-20", msgtime="10:00",
        msgto="Bob", msgfrom="Alice", msgsubject="Subj 1", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg2 = ParsedMessage(text="2", msgnum=2, refnum=None, confnum=1, header=hdr2, bbs_name="MyBBS")

    hdr3 = MessageHeader(
        status=" ", msgnum=3, msgdate="01-03-20", msgtime="10:00",
        msgto="Bob", msgfrom="Alice", msgsubject="Subj 1", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=""
    )
    msg3 = ParsedMessage(text="3", msgnum=3, refnum=None, confnum=1, header=hdr3, bbs_name="")

    def mock_load_data(input_path, logger, encoding):
        return [msg1, msg2, msg3], ConferenceMap()

    monkeypatch.setattr("pyqwk.core.load_data", mock_load_data)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="utf-8", authors=["Alice"]
    )

    out_file = str(tmp_path / "out.txt")
    settings.output_path = out_file

    show_threads(["dummy.qwk"], settings, test_logger)
    show_list_authors(["dummy.qwk"], settings, test_logger)
    show_list_subjects(["dummy.qwk"], settings, test_logger)

    assert os.path.exists(out_file)


def test_cli_explicit_keys_unmatched_short_opt(monkeypatch, tmp_path):
    test_qwk = tmp_path / "test.qwk"
    test_qwk.write_bytes(b"x" * 128)

    monkeypatch.setattr("sys.argv", ["qwk", str(test_qwk), "-q", "-v"])
    main()
