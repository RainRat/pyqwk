import logging
from pathlib import Path

import pytest

from pyqwk.core import (
    BLOCK_SIZE,
    MessageHeader,
    MessagesDatFormatError,
    ProcessingSettings,
    parse_messages,
    process_merged_files,
    validate_archive,
)


def _header(msgnum: int, numblocks: int, subject: str) -> MessageHeader:
    return MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Sender",
        msgsubject=subject,
        msgpassword="",
        refnum=None,
        numblocks=numblocks,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )


def _record(header: MessageHeader, *body_blocks: bytes) -> bytes:
    content = header.to_bytes()
    for block in body_blocks:
        content += block.ljust(BLOCK_SIZE, b" ")
    return content


def _settings(output_path: Path) -> ProcessingSettings:
    return ProcessingSettings(
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
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
    )


def test_validation_is_strict_while_extraction_keeps_complete_messages(
    tmp_path, caplog
):
    source = tmp_path / "messages.dat"
    complete = _record(_header(1, 2, "Complete"), b"First body\xe3")
    truncated = _record(_header(2, 3, "Truncated"), b"Second body\xe3")
    source.write_bytes(b"Produced by pyqwk".ljust(BLOCK_SIZE, b" ") + complete + truncated)

    logger = logging.getLogger("test_truncated_recovery")
    validation = validate_archive(str(source), logger)

    assert validation["valid"] is False
    assert validation["messages_count"] == 0
    assert any("truncated" in error.lower() for error in validation["errors"])

    output = tmp_path / "recovered.txt"
    with caplog.at_level(logging.WARNING):
        process_merged_files([str(source)], _settings(output), logger)

    rendered = output.read_text(encoding="utf-8")
    assert "First body" in rendered
    assert "Second body" not in rendered
    assert "truncated" in caplog.text.lower()
    assert "1 complete message" in caplog.text


def test_extraction_remains_strict_when_no_complete_message_exists(tmp_path):
    source = tmp_path / "messages.dat"
    source.write_bytes(
        b"Produced by pyqwk".ljust(BLOCK_SIZE, b" ")
        + _record(_header(1, 2, "No body"))
    )

    with pytest.raises(MessagesDatFormatError, match="truncated"):
        process_merged_files(
            [str(source)],
            _settings(tmp_path / "unused.txt"),
            logging.getLogger("test_truncated_recovery"),
        )

    with pytest.raises(MessagesDatFormatError, match="truncated"):
        list(parse_messages(bytearray(source.read_bytes()), None))
