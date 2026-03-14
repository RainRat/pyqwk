
import logging
from unittest.mock import patch
from pyqwk.core import (
    MessageHeader,
    ProcessingSettings,
    ParsedMessage,
    process_merged_files
)

def test_format_oneline_highlighting():
    """Cover lines 429-431 in pyqwk/core.py."""
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Hello World",
        msgpassword="", refnum=None, numblocks=1, msgflag="",
        confnum=1, lognum=0, nettag="",
    )
    board_dict = {1: "General"}

    # Enable highlighting
    oneline = header.format_oneline(
        board_dict,
        use_colors=True,
        highlight_term="Bob"
    )
    assert "\x1b[7mBob\x1b[0m" in oneline

    # Highlight subject
    oneline_sub = header.format_oneline(
        board_dict,
        use_colors=True,
        highlight_term="World"
    )
    assert "\x1b[7mWorld\x1b[0m" in oneline_sub

    # Highlight conference
    oneline_conf = header.format_oneline(
        board_dict,
        use_colors=True,
        highlight_term="General"
    )
    assert "\x1b[7mGeneral\x1b[0m" in oneline_conf

def test_format_text_color_separator():
    """Cover line 388 in pyqwk/core.py."""
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Subj",
        msgpassword="", refnum=None, numblocks=1, msgflag="",
        confnum=1, lognum=0, nettag="",
    )

    with patch('shutil.get_terminal_size') as mock_size:
        mock_size.return_value.columns = 80
        formatted = header.format_text(
            board_dict={1: "General"},
            verbose=False,
            use_colors=True,
            include_separator=True
        )
        # Check for colored separator
        assert "\x1b[90m" + ("-" * 80) in formatted

def test_process_merged_files_rich_coverage(tmp_path, capsys):
    """Cover lines 999, 1018, 1252 in pyqwk/core.py."""
    logger = logging.getLogger("test_rich")

    # Setup mock message
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Topic",
        msgpassword="", refnum=None, numblocks=1, msgflag="",
        confnum=1, lognum=0, nettag="",
    )
    msg = ParsedMessage(
        text="This is a test body.",
        msgnum=1, refnum=None, confnum=1,
        header=header
    )

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", quiet=False,
        oneline=True, # Hit line 999
        search_term="test",
        regex=False
    )

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), {1: "General"})
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.return_value = [msg]
            with patch('sys.stdout.isatty', return_value=True): # Hit line 1018 and 1252
                process_merged_files(['fake.qwk'], settings, logger)

    captured = capsys.readouterr()
    # Line 999: format_oneline should have been called
    assert "General" in captured.out

    # Note: line 1018 is NOT hit if oneline is True because it's in the 'else' block of 'if settings.oneline'.
    # I need another run for line 1018.

def test_process_merged_files_body_highlighting(tmp_path, capsys):
    """Cover line 1018 in pyqwk/core.py."""
    logger = logging.getLogger("test_rich_body")

    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Topic",
        msgpassword="", refnum=None, numblocks=1, msgflag="",
        confnum=1, lognum=0, nettag="",
    )
    msg = ParsedMessage(
        text="Find this word.",
        msgnum=1, refnum=None, confnum=1,
        header=header
    )

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", quiet=False,
        oneline=False,
        search_term="word"
    )

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (bytearray(b'Produced '), {1: "General"})
        with patch('pyqwk.core.parse_messages') as mock_parse:
            mock_parse.return_value = [msg]
            with patch('sys.stdout.isatty', return_value=True):
                process_merged_files(['fake.qwk'], settings, logger)

    captured = capsys.readouterr()
    # Check for body highlighting (line 1018)
    assert "\x1b[7mword\x1b[0m" in captured.out
    # Check for colorized success message (line 1252)
    assert "\x1b[1;32mSuccessfully processed 1 message" in captured.out

def test_fmt_val_no_highlight():
    """Cover line 367 in pyqwk/core.py."""
    # Line 367 is 'return val' when (highlight_term and use_colors) is False
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="", msgtime="",
        msgto="", msgfrom="", msgsubject="",
        msgpassword="", refnum=None, numblocks=1, msgflag="",
        confnum=1, lognum=0, nettag="",
    )
    # This calls fmt_val internally
    formatted = header.format_text(board_dict={1: "General"}, verbose=False, highlight_term=None, use_colors=False)
    assert "Conference:" in formatted
