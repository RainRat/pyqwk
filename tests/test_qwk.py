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

import pyqwk.core as qwk
import html

from pyqwk.core import (
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
    _write_xml,
    _write_html,
)
from pyqwk.cli import main


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
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        conferences=None,
        authors=None,
        recipients=None,
        subjects=None,
        search_term=None,
        after=None,
        before=None,
        limit=None,
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
        clean=False,
        quiet=False,
        headers_only=False,
        format="text",
        separator="auto",
        loglevel="INFO",
        encoding="cp437",
        conferences=None,
        authors=None,
        recipients=None,
        subjects=None,
        search_term=None,
        after=None,
        before=None,
        limit=None,
        info=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_parse_messages_matches_baseline(baseline_path: Path, expected_output_path: Path, logger: logging.Logger) -> None:
    file_data, board_dict = load_data(str(baseline_path), logger, encoding='latin1')

    assert isinstance(file_data, bytearray)
    assert board_dict == {}

    messages = list(parse_messages(file_data, progress_bar=None, encoding='latin1'))
    expected_message = _read_expected(expected_output_path)
    expected_body = expected_message.split('\r\n\r\n', 1)[1]

    assert len(messages) == 1
    message = messages[0]
    assert isinstance(message, ParsedMessage)
    assert message.text == expected_body
    header_text = message.header.format_text(board_dict, verbose=False)
    assert header_text + message.text == expected_message
    assert message.header.is_private is False
    assert message.header.is_password is False
    assert message.msgnum == 28
    assert message.refnum is None
    assert message.confnum == 3




def test_invalid_messages_dat_reports_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    invalid_file = tmp_path / "not_messages.dat"
    invalid_file.write_text("This is not a messages.dat file", encoding="latin1")

    monkeypatch.setattr(sys, "argv", ["qwk", str(invalid_file)])
    with caplog.at_level(logging.ERROR, logger="pyqwk.core"):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    assert "Input too short" in caplog.text


def test_parse_messages_raises_for_truncated_payload(
    baseline_path: Path, logger: logging.Logger
) -> None:
    truncated_data = bytearray(baseline_path.read_bytes()[:-qwk.BLOCK_SIZE])

    with pytest.raises(qwk.MessagesDatFormatError) as exc_info:
        list(parse_messages(truncated_data, progress_bar=None))

    assert "truncated" in str(exc_info.value)




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
        content = f.read().decode("utf-8")
    expected_message = _read_expected(expected_output_path)
    # Individual files should NOT have the leading separator (dashes)
    separator = ("-" * 80) + "\r\n"
    assert content == expected_message.replace(separator, "", 1)


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

    assert "folder" in str(exc_info.value)


def test_process_file_prints_to_stdout(capsys, baseline_path: Path, expected_output_path: Path, logger: logging.Logger) -> None:
    process_file(
        str(baseline_path),
        _make_settings(quiet=True),
        logger=logger,
    )

    captured = capsys.readouterr()
    expected_message = _read_expected(expected_output_path)
    assert captured.out == expected_message
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

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
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
    file_data, boarddict = load_data(str(testdata_dir / archive_name), logger, encoding='latin1')

    assert isinstance(file_data, bytearray)
    assert boarddict == expected_boarddict


def test_load_data_skips_invalid_conference_number(
    tmp_path: Path,
    testdata_dir: Path,
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
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

    with caplog.at_level(logging.WARNING):
        _, board_dict = load_data(str(zip_path), logger, encoding='latin1')
        _, board_dict = load_data(str(zip_path), logger, encoding='latin1')

    assert "Invalid conference number" in caplog.text
    # The entry should be skipped, so board_dict should be empty (since there was only 1 entry and it was invalid)
    assert board_dict == {}


def test_load_data_warns_truncated_control_dat(
    tmp_path: Path,
    testdata_dir: Path,
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
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

    with caplog.at_level(logging.WARNING):
        _, board_dict = load_data(str(zip_path), logger)

    assert "CONTROL.DAT is truncated" in caplog.text
    # Should have parsed the first conference (1: Test Conference)
    assert 1 in board_dict
    assert board_dict[1] == "Test Conference"


def test_parse_messages_from_qwk_packet(testdata_dir: Path, logger: logging.Logger) -> None:
    file_data, board_dict = load_data(str(testdata_dir / "test2_qwk.zip"), logger, encoding='latin1')

    messages = list(parse_messages(file_data, progress_bar=None, encoding='latin1'))

    assert len(messages) == 2
    assert {message.header.is_private for message in messages} == {False}
    assert {message.header.is_password for message in messages} == {False}
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
    # Structured output should NOT contain the separator line
    separator = ("-" * 80) + "\r\n"
    assert separator not in message["text"]
    assert message["text"] == expected_message.replace(separator, "", 1)
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
            msgnum=2,
            refnum=1,
            confnum=1,
            header=header,
        ),
        ParsedMessage(
            text="parent",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
        ),
    ]

    def fake_load_data(path: str, logger_param: logging.Logger, encoding: str = 'cp437') -> tuple[bytearray, dict[int, str]]:
        return bytearray(), {}

    def fake_parse_messages(file_data: bytearray, progress_bar: object, encoding: str = 'cp437', headers_only: bool = False):
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
    # Structured output should NOT contain the separator line
    separator = ("-" * 80) + "\r\n"
    expected_content = expected_message.replace(separator, "", 1).replace('\r\n', '\n')
    assert expected_content in content
    assert ("-" * 80) not in content


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
    from pyqwk.core import _write_xml
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


def test_xml_output_sanitizes_invalid_chars(tmp_path: Path) -> None:
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='', msgtime='', msgto='', msgfrom='',
        msgsubject='Subject\x00Invalid', msgpassword='', refnum=None, numblocks=1,
        msgflag=' ', confnum=1, lognum=1, nettag=''
    )
    # \x1b is ESC, invalid in XML 1.0
    text = "Valid text\x1bInvalid"
    message = ProcessedMessage(
        text=text, msgnum=1, refnum=None, confnum=1, header=header
    )

    output_path = tmp_path / "sanitized.xml"
    _write_xml([message], str(output_path))

    content = output_path.read_text(encoding="utf-8")

    assert "Valid text" in content
    assert "Invalid" in content # The word "Invalid"
    assert "\x1b" not in content
    assert "\x00" not in content


def test_process_multiple_files_creates_multiple_outputs(
    tmp_path, testdata_dir: Path, logger: logging.Logger
) -> None:
    output_dir = tmp_path / "messages"
    input_paths = [
        str(testdata_dir / "test1_qwk.zip"),
        str(testdata_dir / "test2_qwk.zip"),
    ]

    from pyqwk.core import process_multiple_files

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
        load_data(str(zip_path), logger, encoding='latin1')

    assert "CONTROL.DAT not found" in caplog.text




def test_cli_requires_output_directory_for_multiple_inputs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], testdata_dir: Path
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", str(testdata_dir / "test1_qwk.zip"), str(testdata_dir / "test2_qwk.zip")],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "Output folder is required when processing multiple files." in stderr


def test_cli_treats_multiple_positional_args_as_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, baseline_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    output_path = tmp_path / "output.txt"
    # This simulates passing two files: baseline_path and output.txt (as a second input)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", str(baseline_path), str(output_path)],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "Output folder is required when processing multiple files." in stderr


def test_cli_treats_extra_positional_args_as_inputs_requiring_output_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, testdata_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    output_dir = tmp_path / "output"
    # This simulates passing three inputs, the last one being the intended output dir but treated as input
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
    assert "Output folder is required when processing multiple files." in stderr


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

def test_process_file_noheader_combined_has_separator(
    capsys: pytest.CaptureFixture[str], baseline_path: Path, logger: logging.Logger
) -> None:
    process_file(
        str(baseline_path),
        _make_settings(no_header=True),
        logger=logger,
    )

    captured = capsys.readouterr()
    # Should contain dashes separator even though no header
    assert ("-" * 80) in captured.out
    # Should not contain "Subject:" (header field)
    assert "Subject:" not in captured.out


def test_process_file_separator_blank(
    capsys: pytest.CaptureFixture[str], baseline_path: Path, logger: logging.Logger
) -> None:
    process_file(
        str(baseline_path),
        _make_settings(separator="blank"),
        logger=logger,
    )

    captured = capsys.readouterr()
    assert ("-" * 80) not in captured.out

def test_cli_rejects_threaded_with_individual_files(
    monkeypatch: pytest.MonkeyPatch, baseline_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logging.basicConfig(level=logging.ERROR, force=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", str(baseline_path), "--threaded", "--individual-files", "-o", "outdir"],
    )

    with pytest.raises(SystemExit):
        main()

    stderr = capsys.readouterr().err
    assert "Threading is not compatible with individual files output." in stderr


def test_cli_allows_noheader_with_structured_formats(
    monkeypatch: pytest.MonkeyPatch, baseline_path: Path, tmp_path: Path
) -> None:
    logging.basicConfig(level=logging.INFO, force=True)
    for fmt in ["json", "xml", "html"]:
        output_path = tmp_path / f"output.{fmt}"
        monkeypatch.setattr(
            sys,
            "argv",
            ["prog", str(baseline_path), "--noheader", "--format", fmt, "-o", str(output_path)],
        )
        # Should not raise SystemExit
        main()
        assert output_path.exists()

def test_json_noheader_removes_header_text(
    tmp_path: Path, baseline_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.json"
    process_file(
        str(baseline_path),
        _make_settings(format="json", no_header=True, output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    message = data[0]
    # Should not contain "Subject:" which is part of the formatted header
    assert "Subject:" not in message["text"]
    assert ("-" * 80) not in message["text"]

def test_xml_noheader_removes_header_text(
    tmp_path: Path, baseline_path: Path, logger: logging.Logger
) -> None:
    output_path = tmp_path / "messages.xml"
    process_file(
        str(baseline_path),
        _make_settings(format="xml", no_header=True, output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with output_path.open("r", encoding="utf-8") as f:
        content = f.read()

    # Should not contain "Subject:" which is part of the formatted header in the text field
    # But note: <Subject> tag is in the header structure, but we check the text field specifically?
    # The text field is inside <text>...</text>
    import xml.etree.ElementTree as ET
    root = ET.fromstring(content)
    text_content = root.find('message/text').text
    assert "Subject:" not in text_content
    assert ("-" * 80) not in text_content

def test_text_output_respects_encoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logger: logging.Logger) -> None:
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="", msgtime="", msgto="", msgfrom="",
        msgsubject="", msgpassword="", refnum=None, numblocks=None, msgflag="",
        confnum=1, lognum=1, nettag="",
    )

    # 'é' is 0x82 in CP437, 0xC3 0xA9 in UTF-8
    text_content = "Resumé\r\n"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {}

    def fake_parse_messages(*args, **kwargs):
        yield ParsedMessage(
            text=text_content,
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header
        )

    monkeypatch.setattr(qwk, "load_data", fake_load_data)
    monkeypatch.setattr(qwk, "parse_messages", fake_parse_messages)

    output_path = tmp_path / "output.txt"

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437"
    )

    process_file("dummy.qwk", settings, logger)

    with open(output_path, "rb") as f:
        content = f.read()

    expected_bytes_cp437 = b"Resum\x82\r\n"

    assert content == expected_bytes_cp437

def test_parse_messages_recovers_from_invalid_numblocks() -> None:
    # Block 0: QWK Header
    qwk_header = b'Produced ' + b'\x00' * (128 - 9)

    # Header 1: numblocks=0 (Invalid)
    header1 = struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        b' ', b"1".ljust(7, b' '), b"010190", b"0000", b"To".ljust(25, b' '), b"From".ljust(25, b' '), b"Subj1".ljust(25, b' '), b"".ljust(12, b' '), b"0".ljust(8, b' '),
        b"0".ljust(6, b' '), # numblocks=0
        b' ', 1, 1, b' '
    )

    # Header 2: numblocks=2 (1 body block) - Valid
    header2 = struct.pack(
        '<c7s8s5s25s25s25s12s8s6scHHc',
        b' ', b"2".ljust(7, b' '), b"010190", b"0000", b"To".ljust(25, b' '), b"From".ljust(25, b' '), b"Subj2".ljust(25, b' '), b"".ljust(12, b' '), b"0".ljust(8, b' '),
        b"2".ljust(6, b' '), # numblocks=2
        b' ', 1, 2, b' '
    )

    body2 = b"Hello world".ljust(128, b' ')

    data = bytearray(qwk_header + header1 + header2 + body2)

    messages = list(parse_messages(data, progress_bar=None))

    # Should skip first message (invalid) and parse second message.
    assert len(messages) == 1
    assert messages[0].msgnum == 2
    assert messages[0].header.msgsubject.strip() == "Subj2"

def test_process_multiple_files_handles_controldat_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, logger: logging.Logger
) -> None:
    def mock_process_file(input_path: str, settings: ProcessingSettings, logger: logging.Logger) -> None:
        if "bad" in input_path:
            raise ControlDatFormatError("Bad control.dat")

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "process_file", mock_process_file)

    input_paths = ["bad.zip", "good.zip"]
    output_dir = tmp_path / "output"
    settings = _make_settings()

    # Should not raise exception
    had_errors = qwk.process_multiple_files(input_paths, str(output_dir), settings, logger)

    assert had_errors is True

def test_clean_flag_activates_cleaning_options(
    monkeypatch: pytest.MonkeyPatch, baseline_path: Path
) -> None:
    namespace = _make_cli_namespace(
        input_paths=[str(baseline_path)],
        clean=True,
    )
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self: namespace)

    captured_settings = []

    def mock_process_file(input_path: str, settings: ProcessingSettings, logger: logging.Logger) -> None:
        captured_settings.append(settings)

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "process_file", mock_process_file)

    main()

    assert len(captured_settings) == 1
    settings = captured_settings[0]
    assert settings.truncate_signatures is True
    assert settings.cut_quoting is True
    assert settings.binaries_removal is True
    assert settings.redact_pii is False
