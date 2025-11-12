import logging
import sys
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import (
    ProcessingSettings,
    ParsedMessage,
    ProcessedMessage,
    MessageHeader,
    ControlDatFormatError,
    _format_message_header,
    _order_messages_by_thread,
    load_data,
    parse_messages,
    process_message,
    process_file,
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
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)


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
    header_text = _format_message_header(message.header, board_dict, verbose=False)
    assert header_text + message.text == expected_message
    assert message.is_private is False
    assert message.is_password is False
    assert message.msgnum == 28
    assert message.refnum is None
    assert message.confnum == 3


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
        str(output_dir),
        _make_settings(individual_files=True),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) == 1

    with files[0].open("rb") as f:
        content = f.read().decode("latin1")
    expected_message = _read_expected(expected_output_path)
    assert content == expected_message


def test_process_file_prints_to_stdout(capsys, baseline_path: Path, expected_output_path: Path, logger: logging.Logger) -> None:
    process_file(
        str(baseline_path),
        None,
        _make_settings(),
        logger=logger,
    )

    captured = capsys.readouterr()
    expected_message = _read_expected(expected_output_path)
    assert captured.out == expected_message + "\n"
    assert captured.err == ""


def test_order_messages_by_thread_groups_children() -> None:
    header = MessageHeader(
        status=b'',
        msgnum=b'',
        msgdate=b'',
        msgtime=b'',
        msgto=b'',
        msgfrom=b'',
        msgsubject=b'',
        msgpassword=b'',
        refnum=b'',
        numblocks=b'',
        msgflag=b'',
        confnum=0,
        lognum=0,
        nettag=b'',
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


def test_order_messages_by_thread_logs_circular_reference(caplog: pytest.LogCaptureFixture) -> None:
    header = MessageHeader(
        status=b'',
        msgnum=b'',
        msgdate=b'',
        msgtime=b'',
        msgto=b'',
        msgfrom=b'',
        msgsubject=b'',
        msgpassword=b'',
        refnum=b'',
        numblocks=b'',
        msgflag=b'',
        confnum=0,
        lognum=0,
        nettag=b'',
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


def test_parse_messages_from_qwk_packet(testdata_dir: Path, logger: logging.Logger) -> None:
    file_data, board_dict = load_data(str(testdata_dir / "test2_qwk.zip"), logger)

    messages = list(parse_messages(file_data, progress_bar=None))

    assert len(messages) == 2
    assert {message.is_private for message in messages} == {False}
    assert {message.is_password for message in messages} == {False}
    assert all(
        "Conference: Net140.Tech"
        in _format_message_header(message.header, board_dict, verbose=False)
        for message in messages
    )
    assert all("Conference:" not in message.text for message in messages)


def test_process_file_writes_json(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.json"
    process_file(
        str(baseline_path),
        str(output_path),
        _make_settings(format="json"),
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
    assert message["header"]["msgnum"] == "28"


def test_process_file_writes_xml(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.xml"
    process_file(
        str(baseline_path),
        str(output_path),
        _make_settings(format="xml"),
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


def test_process_file_writes_xml_with_special_characters(
    tmp_path, logger: logging.Logger
) -> None:
    from qwk import _export_xml
    header = MessageHeader(
        status=b' ',
        msgnum=b'1',
        msgdate=b'01-01-90',
        msgtime=b'12:00',
        msgto=b'All',
        msgfrom=b'Test User',
        msgsubject=b'<test>&subject',
        msgpassword=b'',
        refnum=b'0',
        numblocks=b'1',
        msgflag=b' ',
        confnum=1,
        lognum=1,
        nettag=b'',
    )
    message = ProcessedMessage(
        text="This is a test message with < & > special characters.",
        msgnum=1,
        refnum=0,
        confnum=1,
        header=header
    )

    output_path = tmp_path / "test.xml"
    _export_xml([message], str(output_path))

    with open(output_path, "r") as f:
        content = f.read()

    assert "&lt;test&gt;&amp;subject" in content
    assert "This is a test message with &lt; &amp; &gt; special characters." in content


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
