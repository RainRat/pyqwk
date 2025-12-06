import argparse
import logging
import struct
import sys
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import qwk
import html

from qwk import (
    ProcessingSettings,
    ParsedMessage,
    ProcessedMessage,
    MessageHeader,
    ControlDatFormatError,
    InvalidMessageTypeError,
    _order_messages_by_thread,
    load_data,
    parse_messages,
    process_message,
    process_file,
    _sanitize_xml_string,
    _write_html,
    main,
)


@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"


@pytest.fixture
def expected_output_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages_expected.txt"


@pytest.fixture
def testdata_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata"


def _read_expected(path: Path) -> str:
    text = path.read_text(encoding="latin1")
    return text.replace("\n", "\r\n")


@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger


def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        output_mode="stdout",
        output_path=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)


def _make_cli_namespace(**overrides: object) -> argparse.Namespace:
    base = dict(
        input_paths=[],
        output_path=None,
        stdout=False,
        verbose=False,
        private=False,
        noheader=False,
        truncatesignatures=False,
        cutquoting=False,
        individualfiles=False,
        threaded=False,
        binariesremoval=False,
        redactpii=False,
        quiet=False,
        format="text",
        loglevel="INFO",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_parse_messages_matches_baseline(baseline_path: Path, expected_output_path: Path, logger: logging.Logger) -> None:
    file_data, board_dict = load_data(str(baseline_path), logger)

    assert isinstance(file_data, bytearray)
    assert board_dict == {}

    messages = list(parse_messages(file_data, progress_bar=None))
    expected_message = _read_expected(expected_output_path)
    expected_body = expected_message.split('\r\n\r\n', 1)[1]

    assert len(messages) == 1
    message = messages[0]
    assert isinstance(message, ParsedMessage)
    assert message.text == expected_body
    header_text = message.header.format_text(board_dict, verbose=False)
    assert header_text + message.text == expected_message
    assert message.is_private is False
    assert message.is_password is False
    assert message.msgnum == 28
    assert message.refnum is None
    assert message.confnum == 3


def test_parse_header_record_status_flags() -> None:
    def build_header(status: bytes) -> bytes:
        return struct.pack(
            '<c7s8s5s25s25s25s12s8s6scHHc',
            status,
            b"0000001",
            b"19941005",
            b"12345",
            b"recipient".ljust(25, b' '),
            b"sender".ljust(25, b' '),
            b"subject".ljust(25, b' '),
            b"password".ljust(12, b' '),
            b"refnum".ljust(8, b' '),
            b"000100".ljust(6, b' '),
            b' ',
            1,
            2,
            b' ',
        )

    for status in [b'+', b'*', b'~', b'`']:
        _, is_private, is_password = MessageHeader.from_bytes(build_header(status))
        assert is_private is True
        assert is_password is False

    for status in [b'%', b'^', b'!', b'#', b'$']:
        _, is_private, is_password = MessageHeader.from_bytes(build_header(status))
        assert is_private is True
        assert is_password is True

    for status in [b' ', b'-']:
        _, is_private, is_password = MessageHeader.from_bytes(build_header(status))
        assert is_private is False
        assert is_password is False


def test_parse_header_record_invalid_status_raises() -> None:
    def build_header(status: bytes) -> bytes:
        return struct.pack(
            '<c7s8s5s25s25s25s12s8s6scHHc',
            status,
            b"0000001",
            b"19941005",
            b"12345",
            b"recipient".ljust(25, b' '),
            b"sender".ljust(25, b' '),
            b"subject".ljust(25, b' '),
            b"password".ljust(12, b' '),
            b"refnum".ljust(8, b' '),
            b"000100".ljust(6, b' '),
            b' ',
            1,
            2,
            b' ',
        )

    with pytest.raises(InvalidMessageTypeError) as exc_info:
        MessageHeader.from_bytes(build_header(b'X'))

    assert exc_info.value.message_type == 'X'


def test_invalid_messages_dat_reports_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    invalid_file = tmp_path / "not_messages.dat"
    invalid_file.write_text("This is not a messages.dat file", encoding="latin1")

    monkeypatch.setattr(sys, "argv", ["qwk", str(invalid_file)])
    with caplog.at_level(logging.ERROR, logger="qwk"):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    assert "Input does not start with 'Produced '" in caplog.text


def test_parse_messages_raises_for_truncated_payload(
    baseline_path: Path, logger: logging.Logger
) -> None:
    truncated_data = bytearray(baseline_path.read_bytes()[:-qwk.BLOCK_SIZE])

    with pytest.raises(qwk.MessagesDatFormatError) as exc_info:
        list(parse_messages(truncated_data, progress_bar=None))

    assert "truncated" in str(exc_info.value)


def test_process_message_transforms_content() -> None:
    message = (
        "Intro line\r\n"
        "> quoted text that should be removed\r\n"
        "Another line\r\n"
        "Contact: someone@example.com or 555-123-4567\r\n"
        "-----BEGIN PGP SIGNATURE-----\r\n"
        "Signature block\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=True,
        cut_quoting=True,
        binaries_removal=False,
        redact_pii=True,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
        "Contact: [EMAIL] or [PHONE]\r\n"
    )


def test_process_message_preserves_dates_when_redacting() -> None:
    message = "On 1994-10-05, call 555-123-4567.\r\n"

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=True,
    )

    assert "1994-10-05" in processed
    assert "[PHONE]" in processed


def test_process_message_redacts_local_numbers() -> None:
    message = "Local contact: 555-1234 or 555 6789.\r\n"

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=False,
        redact_pii=True,
    )

    assert processed == "Local contact: [PHONE] or [PHONE].\r\n"


def test_process_message_removes_yenc_binaries() -> None:
    message = (
        "Intro line\r\n"
        "=ybegin line=128 size=12345 name=test.zip\r\n"
        "yEnc encoded data\r\n"
        "=ypart begin=1 end=1024\r\n"
        "more yEnc data\r\n"
        "=yend size=12345 crc32=12345678\r\n"
        "Another line\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
    )


def test_process_message_removes_base64_binaries() -> None:
    message = (
        "Intro line\r\n"
        "VGhpcyBpcyBhIHRlc3QgbWVzc2FnZSB3aXRoIGEgbG9uZyBtdWx0aS1saW5lIEJhc2U2NCBibG9jaw0K"
        "aW4gdGhlIG1pZGRsZS4NCg==\r\n"
        "Another line\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
    )


def test_process_message_removes_uue_binaries() -> None:
    message = (
        "Intro line\r\n"
        "begin 644 test.txt\r\n"
        "M" + ("A" * 60) + "\r\n"
        "Another line\r\n"
    )

    processed = process_message(
        message,
        truncate_signatures=False,
        cut_quoting=False,
        binaries_removal=True,
        redact_pii=False,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
    )


def test_process_file_writes_individual_files(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_dir = tmp_path / "messages"
    process_file(
        str(baseline_path),
        _make_settings(
            individual_files=True,
            output_mode="file",
            output_path=str(output_dir),
        ),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) == 1

    with files[0].open("rb") as f:
        content = f.read().decode("latin1")
    expected_message = _read_expected(expected_output_path)
    assert content == expected_message


def test_process_file_requires_directory_for_individual_files(
    tmp_path, baseline_path: Path, logger: logging.Logger
) -> None:
    invalid_output = tmp_path / "not_a_directory.txt"
    invalid_output.write_text("content", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        process_file(
            str(baseline_path),
            _make_settings(
                individual_files=True,
                output_mode="file",
                output_path=str(invalid_output),
            ),
            logger=logger,
        )

    assert "directory" in str(exc_info.value)


def test_process_file_prints_to_stdout(capsys, baseline_path: Path, expected_output_path: Path, logger: logging.Logger) -> None:
    process_file(
        str(baseline_path),
        _make_settings(),
        logger=logger,
    )

    captured = capsys.readouterr()
    expected_message = _read_expected(expected_output_path)
    assert captured.out == expected_message + "\n"
    assert captured.err == ""


def test_order_messages_by_thread_groups_children() -> None:
    header = MessageHeader(
        status="",
        msgnum=None,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject="",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag="",
        confnum=0,
        lognum=0,
        nettag="",
    )
    messages = [
        ProcessedMessage("child-before-parent\r\n", msgnum=2, refnum=1, confnum=1, header=header),
        ProcessedMessage("root-one\r\n", msgnum=1, refnum=None, confnum=1, header=header),
        ProcessedMessage("nested-child\r\n", msgnum=3, refnum=2, confnum=1, header=header),
        ProcessedMessage("orphan\r\n", msgnum=4, refnum=99, confnum=1, header=header),
        ProcessedMessage("root-two\r\n", msgnum=5, refnum=None, confnum=1, header=header),
        ProcessedMessage("conf-two-root\r\n", msgnum=6, refnum=None, confnum=2, header=header),
        ProcessedMessage("conf-two-child\r\n", msgnum=7, refnum=6, confnum=2, header=header),
    ]

    ordered = _order_messages_by_thread(messages)

    assert [message.text.strip() for message in ordered] == [
        "root-one",
        "child-before-parent",
        "nested-child",
        "orphan",
        "root-two",
        "conf-two-root",
        "conf-two-child",
    ]


def test_order_messages_by_thread_handles_missing_parent() -> None:
    header = MessageHeader(
        status="",
        msgnum=None,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject="",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag="",
        confnum=0,
        lognum=0,
        nettag="",
    )

    messages = [
        ProcessedMessage("root\r\n", msgnum=1, refnum=None, confnum=1, header=header),
        ProcessedMessage("orphan-missing-parent\r\n", msgnum=3, refnum=99, confnum=1, header=header),
        ProcessedMessage("child-of-root\r\n", msgnum=2, refnum=1, confnum=1, header=header),
    ]

    ordered = _order_messages_by_thread(messages)

    assert [message.text.strip() for message in ordered] == [
        "root",
        "child-of-root",
        "orphan-missing-parent",
    ]


def test_order_messages_by_thread_logs_circular_reference(caplog: pytest.LogCaptureFixture) -> None:
    header = MessageHeader(
        status="",
        msgnum=None,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject="",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag="",
        confnum=0,
        lognum=0,
        nettag="",
    )
    messages = [
        ProcessedMessage("first\r\n", msgnum=1, refnum=3, confnum=1, header=header),
        ProcessedMessage("second\r\n", msgnum=2, refnum=1, confnum=1, header=header),
        ProcessedMessage("third\r\n", msgnum=3, refnum=2, confnum=1, header=header),
    ]

    with caplog.at_level(logging.WARNING, logger="qwk"):
        ordered = _order_messages_by_thread(messages)

    assert [message.msgnum for message in ordered] == [1, 2, 3]
    assert "Circular reference detected" in caplog.text


@pytest.mark.parametrize(
    "archive_name, expected_boarddict",
    [
        (
            "test1_qwk.zip",
            {
                1: "General Mess",
                2: "FidoNet NetM",
                3: "Net140.Tech",
                4: "Pnw.Tech",
                5: "Stoon.Sysop",
            },
        ),
        (
            "test2_qwk.zip",
            {
                1: "General Mess",
                2: "FidoNet NetM",
                3: "Net140.Tech",
                4: "Pnw.Tech",
                5: "Stoon.Sysop",
            },
        ),
    ],
)
def test_load_data_reads_all_conferences_from_control_dat(
    archive_name: str, expected_boarddict: dict[int, str], testdata_dir: Path, logger: logging.Logger
) -> None:
    file_data, boarddict = load_data(str(testdata_dir / archive_name), logger)

    assert isinstance(file_data, bytearray)
    assert boarddict == expected_boarddict


def test_load_data_raises_for_invalid_conference_number(
    tmp_path: Path, testdata_dir: Path, logger: logging.Logger
) -> None:
    zip_path = tmp_path / "invalid_control.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(testdata_dir / "messages.dat", "MESSAGES.DAT")
        control_lines = [
            b"Benden Weyr, Pern, Sagittarius Sector",
            b"",
            b"(306) 382-5746",
            b"Ken Read",
            b"0 ,Benden",
            b"09-04-1994,19:25:58",
            b"CHRIS STUBBS",
            b"",
            b"0",
            b"0",
            b"0",
            b"NOT_A_NUMBER",
            b"Test Conference",
        ]
        control_content = b"\r\n".join(control_lines) + b"\r\n"
        zf.writestr("CONTROL.DAT", control_content)

    with pytest.raises(ControlDatFormatError) as exc_info:
        load_data(str(zip_path), logger)

    assert "Invalid conference number" in str(exc_info.value)


def test_load_data_reports_truncated_control_dat(
    tmp_path: Path, testdata_dir: Path, logger: logging.Logger
) -> None:
    zip_path = tmp_path / "truncated_control.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(testdata_dir / "messages.dat", "MESSAGES.DAT")
        control_lines = [
            b"Benden Weyr, Pern, Sagittarius Sector",
            b"",
            b"(306) 382-5746",
            b"Ken Read",
            b"0 ,Benden",
            b"09-04-1994,19:25:58",
            b"CHRIS STUBBS",
            b"",
            b"0",
            b"0",
            b"1",
            b"1",
            b"Test Conference",
        ]
        control_content = b"\r\n".join(control_lines) + b"\r\n"
        zf.writestr("CONTROL.DAT", control_content)

    with pytest.raises(ControlDatFormatError) as exc_info:
        load_data(str(zip_path), logger)

    message = str(exc_info.value)
    assert "missing conference entry 1" in message
    assert "expected 2 entries" in message
    assert "found 1" in message


def test_parse_messages_from_qwk_packet(testdata_dir: Path, logger: logging.Logger) -> None:
    file_data, board_dict = load_data(str(testdata_dir / "test2_qwk.zip"), logger)

    messages = list(parse_messages(file_data, progress_bar=None))

    assert len(messages) == 2
    assert {message.is_private for message in messages} == {False}
    assert {message.is_password for message in messages} == {False}
    assert all(
        "Conference: Net140.Tech"
        in message.header.format_text(board_dict, verbose=False)
        for message in messages
    )
    assert all("Conference:" not in message.text for message in messages)


def test_process_file_writes_json(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.json"
    process_file(
        str(baseline_path),
        _make_settings(format="json", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 1
    message = data[0]
    assert "header" in message
    assert "text" in message
    expected_message = _read_expected(expected_output_path)
    assert message["text"] == expected_message
    assert message["header"]["msgnum"] == 28


def test_process_file_preserves_thread_order_in_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, logger: logging.Logger
) -> None:
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="",
        msgtime="",
        msgto="",
        msgfrom="",
        msgsubject="",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    parsed_messages = [
        ParsedMessage(
            text="child",
            is_private=False,
            is_password=False,
            msgnum=2,
            refnum=1,
            confnum=1,
            header=header,
        ),
        ParsedMessage(
            text="parent",
            is_private=False,
            is_password=False,
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
        ),
    ]

    def fake_load_data(path: str, logger_param: logging.Logger) -> tuple[bytearray, dict[int, str]]:
        return bytearray(), {}

    def fake_parse_messages(file_data: bytearray, progress_bar: object):
        yield from parsed_messages

    monkeypatch.setattr(qwk, "load_data", fake_load_data)
    monkeypatch.setattr(qwk, "parse_messages", fake_parse_messages)

    output_path = tmp_path / "threaded.json"

    process_file(
        "ignored.dat",
        _make_settings(
            threaded=True,
            format="json",
            no_header=True,
            output_mode="file",
            output_path=str(output_path),
        ),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert [message["text"] for message in data] == ["parent\r\n", "child\r\n"]


def test_process_file_writes_xml(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.xml"
    process_file(
        str(baseline_path),
        _make_settings(format="xml", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        content = f.read()

    assert '<messages>' in content
    assert '<message>' in content
    assert '<header>' in content
    assert '<msgnum>28' in content
    expected_message = _read_expected(expected_output_path)
    assert expected_message.replace('\r\n', '\n') in content


def test_process_file_writes_html(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.html"
    process_file(
        str(baseline_path),
        _make_settings(format="html", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    content = output_path.read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content
    assert '<div class="message">' in content
    assert '<div class="header">' in content
    assert '<pre class="body">' in content

    # Header fields
    assert "<strong>From:</strong> GammaO #571 @0*1" in content
    assert "<strong>To:</strong> All" in content
    assert "<strong>Subject:</strong> New User" in content

    # Body content (should be separate from header)
    assert "Hello this is my first day" in content

    # Ensure ASCII header is NOT in the body (by checking for the separator line)
    # The separator line is heavily used in ASCII header but shouldn't be in HTML body for this message
    assert "-" * 80 not in content


def test_process_file_writes_xml_with_special_characters(
    tmp_path, logger: logging.Logger
) -> None:
    from qwk import _write_xml
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate='01-01-90',
        msgtime='12:00',
        msgto='All',
        msgfrom='Test User',
        msgsubject='<test>&subject',
        msgpassword='',
        refnum=None,
        numblocks=1,
        msgflag=' ',
        confnum=1,
        lognum=1,
        nettag='',
    )
    message = ProcessedMessage(
        text="This is a test message with < & > special characters.",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header
    )

    output_path = tmp_path / "test.xml"
    _write_xml([message], str(output_path))

    with open(output_path, "r") as f:
        content = f.read()

    assert "&lt;test&gt;&amp;subject" in content
    assert "This is a test message with &lt; &amp; &gt; special characters." in content


def test_write_html_escapes_and_wraps_messages(tmp_path: Path) -> None:
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate='01-01-90',
        msgtime='12:00',
        msgto='All',
        msgfrom='Test User',
        msgsubject='Test Subject',
        msgpassword='',
        refnum=None,
        numblocks=1,
        msgflag=' ',
        confnum=1,
        lognum=1,
        nettag='',
    )
    message = ProcessedMessage(
        text="<b>Hello & welcome></b>",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header,
    )

    output_path = tmp_path / "test.html"
    _write_html([message], str(output_path))

    content = output_path.read_text(encoding="utf-8")

    assert '<div class="message">' in content
    assert '<div class="header">' in content
    assert '<pre class="body">' in content
    assert "<strong>Subject:</strong> Test Subject" in content
    assert "&lt;b&gt;Hello &amp; welcome&gt;&lt;/b&gt;" in content


def test_sanitize_xml_string_preserves_whitespace_and_drops_invalid() -> None:
    raw_text = "Line1\tLine2\nLine3\r\n\x1b[31mRed\x00"

    sanitized = _sanitize_xml_string(raw_text)

    assert "\t" in sanitized
    assert "\n" in sanitized
    assert "\r" in sanitized
    assert "\x1b" not in sanitized
    assert "\x00" not in sanitized


def test_process_multiple_files_creates_multiple_outputs(
    tmp_path, testdata_dir: Path, logger: logging.Logger
) -> None:
    output_dir = tmp_path / "messages"
    input_paths = [
        str(testdata_dir / "test1_qwk.zip"),
        str(testdata_dir / "test2_qwk.zip"),
    ]

    from qwk import process_multiple_files

    process_multiple_files(
        input_paths,
        str(output_dir),
        _make_settings(),
        logger=logger,
    )

    files = sorted(list(output_dir.iterdir()))
    assert len(files) == 2
    assert files[0].name == "test1_qwk.txt"
    assert files[1].name == "test2_qwk.txt"


def test_load_data_logs_warning_if_control_dat_is_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, testdata_dir: Path
) -> None:
    # Create a zip file without CONTROL.DAT
    zip_path = tmp_path / "no_control.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(testdata_dir / "messages.dat", "MESSAGES.DAT")

    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.StreamHandler())  # Make sure logs are captured

    with caplog.at_level(logging.WARNING):
        load_data(str(zip_path), logger)

    assert "CONTROL.DAT not found" in caplog.text


def test_cli_rejects_stdout_with_output_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], baseline_path: Path
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", str(baseline_path), "-o", "output.txt", "--stdout"],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "not allowed with argument -o/--output" in stderr


def test_cli_requires_output_directory_for_multiple_inputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], testdata_dir: Path
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", str(testdata_dir / "test1_qwk.zip"), str(testdata_dir / "test2_qwk.zip"), "--stdout"],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "Output directory is required when processing multiple files." in stderr


def test_cli_allows_positional_output_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, baseline_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    output_path = tmp_path / "output.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", str(baseline_path), str(output_path)],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "Output directory is required when processing multiple files." in stderr


def test_cli_allows_positional_output_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, testdata_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    output_dir = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            str(testdata_dir / "test1_qwk.zip"),
            str(testdata_dir / "test2_qwk.zip"),
            str(output_dir),
        ],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "Output directory is required when processing multiple files." in stderr


def test_cli_rejects_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch, baseline_path: Path
) -> None:
    namespace = _make_cli_namespace(input_paths=[str(baseline_path)], loglevel="NOPE")
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: namespace)

    with pytest.raises(ValueError):
        main()


def test_cli_reports_missing_file(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    missing_path = tmp_path / "missing.dat"
    logging.basicConfig(level=logging.ERROR, force=True)
    namespace = _make_cli_namespace(input_paths=[str(missing_path)])
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: namespace)

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "No such file or directory" in stderr


def test_cli_handles_mixed_batch_inputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    baseline_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    missing_path = tmp_path / "missing.dat"
    logging.basicConfig(level=logging.ERROR, force=True)
    namespace = _make_cli_namespace(
        input_paths=[str(baseline_path), str(missing_path)],
        output_path=str(output_dir),
    )
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: namespace)

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1

    stderr = capsys.readouterr().err
    assert str(missing_path) in stderr

    expected_output = output_dir / "messages.txt"
    assert expected_output.exists()


def test_cli_batch_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    testdata_dir: Path,
) -> None:
    output_dir = tmp_path / "output"
    input_paths = [
        str(testdata_dir / "test1_qwk.zip"),
        str(testdata_dir / "test2_qwk.zip"),
    ]
    logging.basicConfig(level=logging.ERROR, force=True)
    namespace = _make_cli_namespace(
        input_paths=input_paths,
        output_path=str(output_dir),
    )
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: namespace)

    main()

    files = sorted(list(output_dir.iterdir()))
    assert len(files) == 2
    assert files[0].name == "test1_qwk.txt"
    assert files[1].name == "test2_qwk.txt"
