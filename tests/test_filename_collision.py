import logging
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import (
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
)


@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger


def test_filename_collision_resolution(tmp_path, logger):
    """Test that filename collisions are resolved by appending a short hash."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=str(output_dir),
        encoding="cp437",
        quiet=True,
    )

    # Mock headers
    h1 = MagicMock(spec=MessageHeader)
    h1.msgnum = 100
    h1.confnum = 1
    h1.msgsubject = "Collision Test"
    h1.msgfrom = "User1"
    h1.msgto = "All"
    h1.msgdate = "01-01-23"
    h1.msgtime = "12:00"
    h1.is_private = False
    h1.is_password = False
    h1.as_dict = {
        "from": "User1",
        "to": "All",
        "subject": "Collision Test",
        "date": "01-01-23 12:00",
    }
    h1.format_text.return_value = "Header1\n"

    h2 = MagicMock(spec=MessageHeader)
    h2.msgnum = 100
    h2.confnum = 1
    h2.msgsubject = "Collision Test"
    h2.msgfrom = "User2"
    h2.msgto = "All"
    h2.msgdate = "01-01-23"
    h2.msgtime = "12:00"
    h2.is_private = False
    h2.is_password = False
    h2.as_dict = {
        "from": "User2",
        "to": "All",
        "subject": "Collision Test",
        "date": "01-01-23 12:00",
    }
    h2.format_text.return_value = "Header2\n"

    # Both messages will have the same initial filename: 001-00100-collision_test.txt
    msg1 = ParsedMessage(
        text="Body Content 1", msgnum=100, refnum=None, confnum=1, header=h1
    )
    msg2 = ParsedMessage(
        text="Body Content 2", msgnum=100, refnum=None, confnum=1, header=h2
    )

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (bytearray(b"Produced "), {})
        with patch("pyqwk.core.parse_messages") as mock_parse:
            # We simulate two archives by returning them sequentially
            mock_parse.side_effect = [[msg1], [msg2]]

            process_merged_files(["arch1.qwk", "arch2.qwk"], settings, logger)

    # Check that both files exist
    files = list(output_dir.iterdir())
    assert len(files) == 2

    # Original filename should be there
    expected_original = "001-00100-collision_test.txt"
    assert any(f.name == expected_original for f in files)

    # Hashed filename should also be there
    hashed_files = [f for f in files if f.name != expected_original]
    assert len(hashed_files) == 1
    assert "-" in hashed_files[0].name
    # Hash is 8 chars before .txt
    name_part = hashed_files[0].name.replace(".txt", "")
    assert len(name_part.split("-")[-1]) == 8


def test_conference_slug_fallback(tmp_path, logger):
    """Test that conference names with only special characters fall back to 'conference' slug."""
    output_dir = tmp_path / "organize_output"
    output_dir.mkdir()

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        organize=True,  # This triggers the slugification logic
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=str(output_dir),
        encoding="cp437",
        quiet=True,
    )

    # Mock header with a subject and a conference name that results in empty slug
    h1 = MagicMock(spec=MessageHeader)
    h1.msgnum = 1
    h1.confnum = 99
    h1.msgsubject = "Test"
    h1.msgfrom = "User"
    h1.msgto = "All"
    h1.msgdate = "01-01-23"
    h1.msgtime = "12:00"
    h1.is_private = False
    h1.is_password = False
    h1.as_dict = {
        "from": "User",
        "to": "All",
        "subject": "Test",
        "date": "01-01-23 12:00",
    }
    h1.format_text.return_value = "Header\n"

    # confname "!!!" will result in an empty slug
    msg1 = ParsedMessage(
        text="Body", msgnum=1, refnum=None, confnum=99, header=h1, confname="!!!"
    )

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (bytearray(b"Produced "), {99: "!!!"})
        with patch("pyqwk.core.parse_messages") as mock_parse:
            mock_parse.return_value = [msg1]

            process_merged_files(["archive.qwk"], settings, logger)

    # Check for the directory name: 099-conference
    conf_dir = output_dir / "099-conference"
    assert conf_dir.exists()
    assert conf_dir.is_dir()

    # Check the file inside
    files = list(conf_dir.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith("099-00001-test")
