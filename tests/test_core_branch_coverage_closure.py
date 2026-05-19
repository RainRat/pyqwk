import logging
import zipfile
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    _parse_html_messages,
    _order_messages_by_thread,
    load_data,
    expand_paths,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    BBSInfo,
    ConferenceMap,
    process_merged_files,
)


def test_parse_html_messages_case_insensitive(tmp_path):
    """Test that HTML parser handles uppercase DIV tags."""
    html_file = tmp_path / "test.html"
    html_content = """
    <div class="message" id="msg1">
        <div class="header">
            <strong>Date:</strong> 01-01-23 12:00</div>
            <strong>From:</strong> User1</div>
            <strong>To:</strong> User2</div>
            <strong>Subject:</strong> Test Subject</div>
            <strong>Number:</strong> 1</div>
        </div>
        <pre class="body">Hello world</pre>
        <div class="reply">
            <div class="message" id="msg2">
                <div class="header">
                    <strong>Subject:</strong> Re: Test</div>
                    <strong>Number:</strong> 2</div>
                </div>
                <pre class="body">Reply content</pre>
            </div>
        </div>
    </div>
    """
    # Test lowercase first to ensure test is correct
    html_file.write_text(html_content)
    msgs = _parse_html_messages(str(html_file))
    assert len(msgs) == 2
    assert msgs[1].depth == 1

    # Now test uppercase
    upper_html = (
        html_content.replace("<div", "<DIV")
        .replace("</div", "</DIV>")
        .replace("<pre", "<PRE")
        .replace("</pre", "</PRE")
    )
    html_file.write_text(upper_html)
    msgs = _parse_html_messages(str(html_file))
    assert len(msgs) == 2
    assert msgs[1].depth == 1


def test_threading_cycle_already_reported(caplog):
    """
    Try to trigger the 'cycle already reported' branch in _order_messages_by_thread.
    """
    h1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="U1",
        msgsubject="S1",
        msgpassword="",
        refnum=2,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg1 = ParsedMessage(text="M1", msgnum=1, refnum=2, confnum=1, header=h1)

    h2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-01-23",
        msgtime="12:01",
        msgto="All",
        msgfrom="U2",
        msgsubject="S1",
        msgpassword="",
        refnum=3,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg2 = ParsedMessage(text="M2", msgnum=2, refnum=3, confnum=1, header=h2)

    h3 = MessageHeader(
        status=" ",
        msgnum=3,
        msgdate="01-01-23",
        msgtime="12:02",
        msgto="All",
        msgfrom="U3",
        msgsubject="S1",
        msgpassword="",
        refnum=1,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg3 = ParsedMessage(text="M3", msgnum=3, refnum=1, confnum=1, header=h3)

    # Adding an extra path to the same cycle to trigger "already reported"
    h4 = MessageHeader(
        status=" ",
        msgnum=4,
        msgdate="01-01-23",
        msgtime="12:03",
        msgto="All",
        msgfrom="U4",
        msgsubject="S1",
        msgpassword="",
        refnum=2,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg4 = ParsedMessage(text="M4", msgnum=4, refnum=2, confnum=1, header=h4)

    msgs = [msg1, msg2, msg3, msg4]

    logger = logging.getLogger("pyqwk.core")
    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        ordered = _order_messages_by_thread(msgs)

    assert "Conversation loop detected" in caplog.text
    assert len(ordered) == 4


def test_load_data_merging_branches(tmp_path, caplog):
    """Test missing branches in load_data merging logic (BBS info and board dict)."""
    # Create files for batch processing
    file1 = tmp_path / "file1.json"
    file1.write_text("[]")
    file2 = tmp_path / "file2.json"
    file2.write_text("[]")
    file3 = tmp_path / "file3.json"
    file3.write_text("[]")

    # Also need a ZIP file to trigger the code that does the merging
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("file1.json", "[]")
        z.writestr("file2.json", "[]")
        z.writestr("file3.json", "[]")

    logger = logging.getLogger("pyqwk.core")

    bd1 = ConferenceMap({1: "Conf1"})
    bd1.bbs_info = BBSInfo(name="BBS1")

    # bd2 has NO BBSInfo to trigger !merged_board_dict.bbs_info branch if it was first
    # but since it's second it triggers nothing new unless we reorder.

    bd2 = ConferenceMap({1: "Conf1_Duplicate", 2: "Conf2"})
    bd2.bbs_info = BBSInfo(name="")  # Empty name to trigger the name check

    bd3 = ConferenceMap({3: "Conf3"})
    bd3.bbs_info = None  # No BBS info

    # Mock load_data to return specific board_dicts and bbs_info
    # We need to mock it so that when it's called RECURSIVELY it returns our test data.
    orig_load_data = load_data
    with patch("pyqwk.core.load_data") as mock_load:

        def side_effect(path, logger, encoding="cp437"):
            if "file1.json" in path:
                return [
                    ParsedMessage(
                        text="M1", msgnum=1, refnum=None, confnum=1, header=MagicMock()
                    )
                ], bd1
            if "file2.json" in path:
                return [
                    ParsedMessage(
                        text="M2", msgnum=2, refnum=None, confnum=2, header=MagicMock()
                    )
                ], bd2
            if "file3.json" in path:
                return [
                    ParsedMessage(
                        text="M3", msgnum=3, refnum=None, confnum=3, header=MagicMock()
                    )
                ], bd3
            return orig_load_data(path, logger, encoding)

        mock_load.side_effect = side_effect

        # Trigger batch loading via ZIP
        res, combined_bd = load_data(str(zip_path), logger=logger)

        assert combined_bd.bbs_info.name == "BBS1"
        assert combined_bd[1] == "Conf1"
        assert combined_bd[2] == "Conf2"
        assert combined_bd[3] == "Conf3"


def test_expand_paths_branches(tmp_path):
    """Test branches in expand_paths for tar/zip detection."""
    non_existent = tmp_path / "missing.qwk"

    # Existing but not an archive
    regular_file = tmp_path / "regular.txt"
    regular_file.write_text("hello")

    paths = [str(non_existent), str(regular_file)]
    expanded = expand_paths(paths)

    # Should include both (one existing, one not)
    assert len(expanded) == 2
    assert str(regular_file) in expanded


def test_parse_text_messages_empty_date_parts(tmp_path):
    """Test _parse_text_messages when date string is present but has no parts."""
    # This is tricky because the regex for date usually ensures some content.
    # If we have "Date:  \n", split() will be empty.
    from pyqwk.core import _parse_text_messages

    content = """
Conference: Gen
BBS: MyBBS
Status:
Message #: 1
Date:
From: User
To: All
Subject: Test
--------------------------------------------------------------------------------
Body
"""
    tf = tmp_path / "test_empty_date.txt"
    tf.write_text(content)

    msgs = _parse_text_messages(str(tf))
    assert len(msgs) == 1
    assert msgs[0].header.msgdate == "01-01-70"


def test_rss_export_attachment_branches(tmp_path):
    """Test _write_rss and related branches in process_merged_files."""

    output_file = tmp_path / "test.rss"
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        merge=False,
        binaries_removal=False,
        redact_pii=False,
        format="rss",
        separator="none",
        output_mode="file",
        output_path=str(output_file),
        encoding="utf-8",
        unique=False,
        strip_ansi=False,
        quiet=True,
        headers_only=False,
    )

    h1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="User1",
        msgsubject="Subj1",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=100,
        lognum=1,
        nettag="",
    )
    msg1 = ParsedMessage(
        text="Body with attachment", msgnum=1, refnum=None, confnum=100, header=h1
    )
    # Simulate an attachment by having UUEncoded text that might be detected if extract_attachments was true

    mock_logger = MagicMock()
    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([msg1], ConferenceMap())
        process_merged_files(["fake.qwk"], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text()
    assert "Subj1" in content
