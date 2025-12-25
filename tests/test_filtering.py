import sys
import logging
from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import qwk
from qwk import process_file, ProcessingSettings

@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests.filtering")
    logger.addHandler(logging.NullHandler())
    return logger

def make_settings(**overrides) -> ProcessingSettings:
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
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

@pytest.fixture
def mock_dependencies():
    with patch('qwk.load_data') as mock_load, \
         patch('qwk.parse_messages') as mock_parse, \
         patch('qwk._write_text') as mock_write:

        mock_load.return_value = (b'', {})
        yield mock_load, mock_parse, mock_write

def test_process_file_skips_private_messages_by_default(
    mock_dependencies, message_factory, logger
):
    mock_load, mock_parse, mock_write = mock_dependencies

    # Create a private message (status '*')
    # Reference: qwk.py is_private property: status not in (' ', '-')
    private_msg = message_factory(1, 0, "Private Msg", status='*')

    mock_parse.return_value = [private_msg]
    settings = make_settings(private=False)

    process_file("dummy.qwk", settings, logger)

    # Verify _write_text called with empty list
    assert mock_write.called
    args, _ = mock_write.call_args
    messages = args[0]
    assert len(messages) == 0

def test_process_file_includes_private_messages_with_flag(
    mock_dependencies, message_factory, logger
):
    mock_load, mock_parse, mock_write = mock_dependencies

    private_msg = message_factory(1, 0, "Private Msg", status='*')

    mock_parse.return_value = [private_msg]
    settings = make_settings(private=True)

    process_file("dummy.qwk", settings, logger)

    # Verify _write_text called with the message
    assert mock_write.called
    args, _ = mock_write.call_args
    messages = args[0]
    assert len(messages) == 1
    assert messages[0].msgnum == 1

def test_process_file_always_skips_password_messages(
    mock_dependencies, message_factory, logger
):
    mock_load, mock_parse, mock_write = mock_dependencies

    # Create a password protected message (status '%')
    # Reference: qwk.py is_password property: status in ('%', '^', '!', '#', '$')
    password_msg = message_factory(1, 0, "Password Msg", status='%')

    mock_parse.return_value = [password_msg]

    # Test with private=False
    settings = make_settings(private=False)
    process_file("dummy.qwk", settings, logger)
    assert len(mock_write.call_args[0][0]) == 0

    # Test with private=True (should still skip password messages)
    settings_private = make_settings(private=True)
    process_file("dummy.qwk", settings_private, logger)
    assert len(mock_write.call_args[0][0]) == 0

def test_process_file_mixed_messages(
    mock_dependencies, message_factory, logger
):
    mock_load, mock_parse, mock_write = mock_dependencies

    msgs = [
        message_factory(1, 0, "Public", status=' '),
        message_factory(2, 0, "Private", status='*'),
        message_factory(3, 0, "Password", status='%'),
    ]

    mock_parse.return_value = msgs

    # Case 1: Default (Public only)
    settings = make_settings(private=False)
    process_file("dummy.qwk", settings, logger)

    processed = mock_write.call_args[0][0]
    assert len(processed) == 1
    assert processed[0].msgnum == 1

    # Case 2: Private enabled (Public + Private)
    settings = make_settings(private=True)
    process_file("dummy.qwk", settings, logger)

    processed = mock_write.call_args[0][0]
    assert len(processed) == 2
    assert processed[0].msgnum == 1
    assert processed[1].msgnum == 2
