import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import (
    ProcessingSettings,
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
        noHeader=False,
        truncateSignatures=False,
        cutQuoting=False,
        individualFiles=False,
        binariesRemoval=False,
        redactPII=False,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)


def test_parse_messages_matches_baseline(baseline_path: Path, expected_output_path: Path, logger: logging.Logger) -> None:
    file_data, boarddict = load_data(str(baseline_path), logger)

    assert isinstance(file_data, bytearray)
    assert boarddict == {}

    messages = list(parse_messages(file_data, boarddict, noHeader=False, verbose=False))
    expected_message = _read_expected(expected_output_path)

    assert messages == [(expected_message, False, False)]


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
        truncateSignatures=True,
        cutQuoting=True,
        binariesRemoval=False,
        redactPII=True,
    )

    assert processed == (
        "Intro line\r\n"
        "Another line\r\n"
        "Contact: [EMAIL] or [PHONE]\r\n"
    )


def test_process_file_writes_individual_files(
    tmp_path, baseline_path: Path, expected_output_path: Path, logger: logging.Logger
) -> None:
    output_dir = tmp_path / "messages"
    process_file(
        str(baseline_path),
        str(output_dir),
        _make_settings(individualFiles=True),
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


def test_parse_messages_from_qwk_packet(testdata_dir: Path, logger: logging.Logger) -> None:
    file_data, boarddict = load_data(str(testdata_dir / "test2_qwk.zip"), logger)

    messages = list(parse_messages(file_data, boarddict, noHeader=False, verbose=False))

    assert len(messages) == 2
    assert {is_private for _, is_private, _ in messages} == {False}
    assert {is_password for _, _, is_password in messages} == {False}
    assert all("Conference: Net140.Tech" in message for message, _, _ in messages)
