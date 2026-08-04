import os
import json
import fnmatch
from unittest.mock import MagicMock
from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    matches_filters,
    process_merged_files,
)
import pytest


def test_attachment_pattern_filter_logic():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="Author",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    # Message with zip attachment
    msg_with_zip = ParsedMessage(
        text="begin 644 file.zip\n#0V%T\n`\nend\n",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    # Message with gif attachment
    msg_with_gif = ParsedMessage(
        text="begin 644 image.gif\n#0V%T\n`\nend\n",
        msgnum=2,
        refnum=None,
        confnum=1,
        header=header,
    )

    # Message without attachment
    msg_no_attach = ParsedMessage(
        text="Hello world", msgnum=3, refnum=None, confnum=1, header=header
    )

    # Settings with wildcard *.zip
    settings_zip = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        attachment_pattern="*.zip",
    )

    # Settings with substring match "gif"
    settings_gif = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        attachment_pattern="gif",
    )

    # Settings with non-matching pattern "png"
    settings_png = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        attachment_pattern="*.png",
    )

    # Verify Zip pattern matching
    assert matches_filters(msg_with_zip, settings_zip, set()) is True
    assert msg_with_zip.attachments == ["file.zip"]
    assert matches_filters(msg_with_gif, settings_zip, set()) is False
    assert matches_filters(msg_no_attach, settings_zip, set()) is False

    # Verify Gif substring pattern matching
    assert matches_filters(msg_with_gif, settings_gif, set()) is True
    assert msg_with_gif.attachments == ["image.gif"]
    assert matches_filters(msg_with_zip, settings_gif, set()) is False
    assert matches_filters(msg_no_attach, settings_gif, set()) is False

    # Verify PNG pattern matching (none matches)
    assert matches_filters(msg_with_zip, settings_png, set()) is False
    assert matches_filters(msg_with_gif, settings_png, set()) is False
    assert matches_filters(msg_no_attach, settings_png, set()) is False


def test_attachment_pattern_extraction_selective(tmp_path):
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="Author",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    # Message containing both a ZIP and a TXT attachment
    msg = ParsedMessage(
        text=(
            "begin 644 file.zip\n"
            "M04U#\"DY%3U0)\"D5.1#`@\n"
            "`\n"
            "end\n"
            "\n"
            "begin 644 file.txt\n"
            "M2&5L;&\\@,C`P,`H`\n"
            "`\n"
            "end\n"
        ),
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    import pyqwk.core
    # Mock load_data and parse_messages
    def dummy_load_data(*a, **k):
        return bytearray(), {1: "General"}

    def dummy_parse_messages(*a, **k):
        return [msg]

    # Create directories
    output_dir = tmp_path / "output"
    os.makedirs(output_dir, exist_ok=True)

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_dir / "messages.txt"),
        encoding="cp437",
        extract_attachments=True,
        attachment_pattern="*.zip",
        quiet=True,
    )

    # Run processing with mocked loaders to trigger extraction
    with pytest.MonkeyPatch().context() as m:
        m.setattr(pyqwk.core, "load_data", dummy_load_data)
        m.setattr(pyqwk.core, "parse_messages", dummy_parse_messages)
        process_merged_files(["test.qwk"], settings, MagicMock())

    # Check that file.zip was extracted, but NOT file.txt!
    extracted_attachments_dir = output_dir / "attachments"
    assert os.path.exists(extracted_attachments_dir)
    extracted_files = os.listdir(extracted_attachments_dir)
    assert "file.zip" in extracted_files
    assert "file.txt" not in extracted_files


def test_attachment_pattern_cli_integration(monkeypatch, capsys):
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="Author",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    msg1 = ParsedMessage(
        text="begin 644 file.zip\n#0V%T\n`\nend\n",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )
    msg2 = ParsedMessage(
        text="begin 644 file.txt\n#0V%T\n`\nend\n",
        msgnum=2,
        refnum=None,
        confnum=1,
        header=header,
    )

    import pyqwk.core

    monkeypatch.setattr(
        pyqwk.core, "load_data", lambda *a: (bytearray(), {1: "General"})
    )
    monkeypatch.setattr(pyqwk.core, "parse_messages", lambda *a, **k: [msg1, msg2])

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        attachment_pattern="*.zip",
        quiet=True,
    )

    process_merged_files(["test.qwk"], settings, MagicMock())

    captured = capsys.readouterr()
    # file.zip should be printed, file.txt should be filtered out
    assert "begin 644 file.zip" in captured.out
    assert "begin 644 file.txt" not in captured.out


def test_attachment_pattern_substring_fallback():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="Author",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    msg = ParsedMessage(
        text="begin 644 file[abc].zip\n#0V%T\n`\nend\n",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
    )

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        attachment_pattern="file[abc]",
    )

    assert fnmatch.fnmatch("file[abc].zip", "file[abc]") is False
    assert fnmatch.fnmatch("file[abc].zip", "*file[abc]*") is False

    assert matches_filters(msg, settings, set()) is True
