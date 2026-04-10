import os
import pytest
from pyqwk.core import (
    ParsedMessage, MessageHeader, ProcessingSettings, process_merged_files,
    BBSInfo, ConferenceMap
)
import logging

def test_organize_advanced(tmp_path, mocker):
    # Setup mock data
    header1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Hello",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=""
    )
    msg1 = ParsedMessage(
        text="Hello Alice!", msgnum=1, refnum=None, confnum=1,
        header=header1, confname="General", bbs_name="BBS1"
    )

    header2 = MessageHeader(
        status=" ", msgnum=2, msgdate="02-01-23", msgtime="13:00",
        msgto="Bob", msgfrom="Alice", msgsubject="Re: Hello",
        msgpassword="", refnum=1, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=""
    )
    msg2 = ParsedMessage(
        text="Hi Bob!", msgnum=2, refnum=1, confnum=1,
        header=header2, confname="General", bbs_name="BBS1"
    )

    # Mock load_data to return our messages
    def mock_load_data(path, logger, encoding='cp437'):
        board_dict = ConferenceMap({1: "General"})
        board_dict.bbs_info = BBSInfo(name="BBS1")
        return [msg1, msg2], board_dict

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load_data)

    output_dir = tmp_path / "export"
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format="text", separator="none", output_mode="file",
        output_path=str(output_dir), encoding="cp437",
        organize_by_bbs=True, organize_by_author=True, organize_by_to=True,
        organize=True, organize_by_date=True
    )

    logger = logging.getLogger("test")
    process_merged_files(["dummy.qwk"], settings, logger)

    # Verify directory structure
    # Hierarchy: BBS -> Author -> Recipient -> Conference -> Year -> Month

    # Msg 1: BBS1 -> Bob -> Alice -> 001-general -> 2023 -> 01
    msg1_path = output_dir / "bbs1" / "bob" / "alice" / "001-general" / "2023" / "01"
    assert msg1_path.exists()
    assert any("hello" in f.name.lower() for f in msg1_path.iterdir())

    # Msg 2: BBS1 -> Alice -> Bob -> 001-general -> 2023 -> 02
    msg2_path = output_dir / "bbs1" / "alice" / "bob" / "001-general" / "2023" / "02"
    assert msg2_path.exists()
    assert any("re_hello" in f.name.lower() for f in msg2_path.iterdir())

def test_attachment_prefix_depth(tmp_path, mocker):
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Attach",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=""
    )
    # Message with UUE attachment
    text = "Check this out!\r\nbegin 644 test.txt\r\n#0V%T\r\n`\r\nend\r\n"
    msg = ParsedMessage(
        text=text, msgnum=1, refnum=None, confnum=1,
        header=header, confname="General", bbs_name="BBS1"
    )

    mocker.patch("pyqwk.core.load_data", return_value=([msg], ConferenceMap({1: "General"})))

    output_dir = tmp_path / "export"
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=True, threaded=False, merge=False,
        binaries_removal=False, redact_pii=False, strip_ansi=False,
        format="html", separator="none", output_mode="file",
        output_path=str(output_dir), encoding="cp437",
        organize_by_bbs=True, organize=True,
        extract_attachments=True
    )

    logger = logging.getLogger("test")
    process_merged_files(["dummy.qwk"], settings, logger)

    # Hierarchy: bbs1 -> 001-general (2 levels)
    # Attachment prefix should be "../../attachments/"

    msg_dir = output_dir / "bbs1" / "001-general"
    assert msg_dir.exists()
    html_file = list(msg_dir.glob("*.html"))[0]
    with open(html_file, "r") as f:
        content = f.read()
        assert "../../attachments/test.txt" in content

    assert (output_dir / "attachments" / "test.txt").exists()
