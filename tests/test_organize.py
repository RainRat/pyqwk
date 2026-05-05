import logging
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    matches_filters,
    BBSInfo,
    ConferenceMap,
)


def _make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        merge=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=None,
        encoding="cp437",
        organize=False,
        organize_by_date=False,
        extract_attachments=False,
        include_toc=True,
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def _make_msg(
    msgnum=1,
    confnum=1,
    msgdate="01-01-23",
    msgtime="12:00",
    msgfrom="Author",
    msgto="Recipient",
    msgsubject="Subject",
    text="Body",
    status=" ",
):
    header = MessageHeader(
        status=status,
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=confnum,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text=text, msgnum=msgnum, refnum=None, confnum=confnum, header=header
    )


def test_organize_subfolders(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    msg1 = _make_msg(
        msgnum=1, confnum=1, msgfrom="Bob", msgto="Alice", msgsubject="Hello"
    )
    msg2 = _make_msg(
        msgnum=2, confnum=2, msgfrom="Alice", msgto="Bob", msgsubject="Re: Hello"
    )

    board_dict = {1: "General Chat", 2: "Tech Talk"}
    settings = _make_settings(output_path=str(output_dir), organize=True)
    logger = MagicMock()

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), board_dict)),
        patch("pyqwk.core.parse_messages", return_value=[msg1, msg2]),
    ):
        process_merged_files(["dummy.qwk"], settings, logger)

    assert (output_dir / "001-general_chat" / "001-00001-hello.txt").exists()
    assert (output_dir / "002-tech_talk" / "002-00002-re_hello.txt").exists()


def test_organize_unknown_conference(tmp_path):
    output_dir = tmp_path / "output_unknown"
    output_dir.mkdir()

    msg = _make_msg(msgnum=10, confnum=999, msgsubject="Secret")
    settings = _make_settings(output_path=str(output_dir), organize=True)

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert (output_dir / "999-unknown" / "999-00010-secret.txt").exists()


def test_organize_advanced(tmp_path, mocker):
    output_dir = tmp_path / "export"

    msg1 = _make_msg(
        msgnum=1,
        confnum=1,
        msgdate="01-01-23",
        msgfrom="Bob",
        msgto="Alice",
        msgsubject="Hello",
    )
    msg1.confname = "General"
    msg1.bbs_name = "BBS1"

    msg2 = _make_msg(
        msgnum=2,
        confnum=1,
        msgdate="02-01-23",
        msgfrom="Alice",
        msgto="Bob",
        msgsubject="Re: Hello",
    )
    msg2.confname = "General"
    msg2.bbs_name = "BBS1"

    board_dict = ConferenceMap({1: "General"})
    board_dict.bbs_info = BBSInfo(name="BBS1")

    mocker.patch("pyqwk.core.load_data", return_value=([msg1, msg2], board_dict))

    settings = _make_settings(
        output_path=str(output_dir),
        organize_by_bbs=True,
        organize_by_author=True,
        organize_by_to=True,
        organize=True,
        organize_by_date=True,
    )

    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    # BBS1 -> Bob -> Alice -> 001-general -> 2023 -> 01
    assert (
        output_dir / "bbs1" / "bob" / "alice" / "001-general" / "2023" / "01"
    ).exists()
    # BBS1 -> Alice -> Bob -> 001-general -> 2023 -> 02
    assert (
        output_dir / "bbs1" / "alice" / "bob" / "001-general" / "2023" / "02"
    ).exists()


def test_attachment_prefix_depth(tmp_path, mocker):
    output_dir = tmp_path / "export_prefix"
    text = "Check this out!\r\nbegin 644 test.txt\r\n#0V%T\r\n`\r\nend\r\n"
    msg = _make_msg(text=text, msgsubject="Attach", confnum=1)
    msg.confname = "General"
    msg.bbs_name = "BBS1"

    mocker.patch(
        "pyqwk.core.load_data", return_value=([msg], ConferenceMap({1: "General"}))
    )

    settings = _make_settings(
        output_path=str(output_dir),
        organize_by_bbs=True,
        organize=True,
        extract_attachments=True,
        format="html",
    )

    process_merged_files(["dummy.qwk"], settings, logging.getLogger("test"))

    html_file = list((output_dir / "bbs1" / "001-general").glob("*.html"))[0]
    with open(html_file, "r") as f:
        assert "../../attachments/test.txt" in f.read()
    assert (output_dir / "attachments" / "test.txt").exists()


def test_organize_by_date_only(tmp_path):
    output_dir = tmp_path / "output_date"
    output_dir.mkdir()

    msg = _make_msg(msgdate="05-20-24", msgsubject="Test", confnum=1)
    msg.confname = "General"

    settings = _make_settings(output_path=str(output_dir), organize_by_date=True)

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert (output_dir / "2024" / "05" / "001-00001-test.txt").exists()


def test_organize_by_conf_and_date(tmp_path):
    output_dir = tmp_path / "output_both"
    output_dir.mkdir()

    msg = _make_msg(msgdate="05-20-24", msgsubject="Test", confnum=1)
    msg.confname = "General"

    settings = _make_settings(
        output_path=str(output_dir), organize=True, organize_by_date=True
    )

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert (output_dir / "001-general" / "2024" / "05" / "001-00001-test.txt").exists()


def test_relative_attachment_prefix_nested(tmp_path):
    output_dir = tmp_path / "output_attach_nested"
    output_dir.mkdir()

    msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
    msg = _make_msg(text=msg_text, msgdate="05-20-24", confnum=1)
    msg.confname = "General"

    settings = _make_settings(
        output_path=str(output_dir),
        organize=True,
        organize_by_date=True,
        extract_attachments=True,
        format="html",
    )

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    expected_file = (
        output_dir / "001-general" / "2024" / "05" / "001-00001-subject.html"
    )
    with open(expected_file, "r") as f:
        assert 'href="../../../attachments/file.txt"' in f.read()


def test_relative_attachment_prefix_date_only(tmp_path):
    output_dir = tmp_path / "output_attach_date"
    output_dir.mkdir()

    msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
    msg = _make_msg(text=msg_text, msgdate="05-20-24", confnum=1)
    msg.confname = "General"

    settings = _make_settings(
        output_path=str(output_dir),
        organize_by_date=True,
        extract_attachments=True,
        format="markdown",
    )

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    expected_file = output_dir / "2024" / "05" / "001-00001-subject.md"
    with open(expected_file, "r") as f:
        assert "(../../attachments/file.txt)" in f.read()


def test_organize_by_date_dry_run(tmp_path):
    output_dir = tmp_path / "output_dry"
    output_dir.mkdir()

    msg = _make_msg(msgdate="05-20-24", confnum=1)
    msg.confname = "General"

    settings = _make_settings(
        output_path=str(output_dir), organize_by_date=True, dry_run=True
    )

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert not (output_dir / "2024" / "05").exists()


def test_extract_attachments_dry_run(tmp_path):
    output_dir = tmp_path / "output_attach_dry"
    output_dir.mkdir()

    msg_text = "begin 644 file.txt\n#0V%T\n`\nend\n"
    msg = _make_msg(text=msg_text, confnum=1)

    settings = _make_settings(
        output_path=str(output_dir), extract_attachments=True, dry_run=True
    )

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert not (output_dir / "attachments").exists()


def test_extract_attachments_none_found(tmp_path):
    output_dir = tmp_path / "output_no_attach"
    output_dir.mkdir()

    msg = _make_msg(text="Just some text", confnum=1)
    settings = _make_settings(output_path=str(output_dir), extract_attachments=True)

    with (
        patch("pyqwk.core.load_data", return_value=(bytearray(), {1: "General"})),
        patch("pyqwk.core.parse_messages", return_value=[msg]),
    ):
        process_merged_files(["dummy.qwk"], settings, MagicMock())

    assert not (output_dir / "attachments").exists()


def test_matches_filters_password_protected():
    msg = _make_msg(status="%")  # Password protected
    settings = _make_settings(private=True)
    assert matches_filters(msg, settings, set()) is False
