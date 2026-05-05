from unittest.mock import MagicMock, patch
from pyqwk.core import (
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)


def test_unique_bbs_isolation(tmp_path):
    """Verify that messages with same msgnum but different BBS are not deduplicated."""
    output_path = tmp_path / "output.txt"
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        merge=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        unique=True,
        strip_ansi=False,
        quiet=True,
        headers_only=False,
    )

    # Message 1 from BBS A
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
        text="Message from BBS A",
        msgnum=1,
        refnum=None,
        confnum=100,
        header=h1,
        bbs_name="BBS A",
        bbs_id="A",
    )

    # Message 2 from BBS B with SAME msgnum and confnum
    h2 = MessageHeader(
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
    msg2 = ParsedMessage(
        text="Message from BBS B",
        msgnum=1,
        refnum=None,
        confnum=100,
        header=h2,
        bbs_name="BBS B",
        bbs_id="B",
    )

    mock_logger = MagicMock()

    with patch("pyqwk.core.load_data") as mock_load:
        # Returning both messages in a single "file" stream
        mock_load.return_value = ([msg1, msg2], {})

        process_merged_files(["combined.jsonl"], settings, mock_logger)

    content = output_path.read_text()
    # Both messages should be present
    assert "Message from BBS A" in content
    assert "Message from BBS B" in content
    assert content.count("\n") == 2


def test_unique_content_hash_bbs_isolation(tmp_path):
    """Verify that messages with same content but different BBS are not deduplicated."""
    output_path = tmp_path / "output.txt"
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        merge=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        unique=True,
        strip_ansi=False,
        quiet=True,
        headers_only=False,
    )

    # Message 1 from BBS A (No msgnum, triggers content hashing)
    h1 = MessageHeader(
        status=" ",
        msgnum=None,
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
        text="Same Content",
        msgnum=None,
        refnum=None,
        confnum=100,
        header=h1,
        bbs_name="BBS A",
        bbs_id="A",
    )

    # Message 2 from BBS B with SAME content
    h2 = MessageHeader(
        status=" ",
        msgnum=None,
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
    msg2 = ParsedMessage(
        text="Same Content",
        msgnum=None,
        refnum=None,
        confnum=100,
        header=h2,
        bbs_name="BBS B",
        bbs_id="B",
    )

    mock_logger = MagicMock()

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = ([msg1, msg2], {})
        process_merged_files(["combined.jsonl"], settings, mock_logger)

    content = output_path.read_text()
    # Should contain "Same Content" twice
    assert content.count("Same Content") == 2
