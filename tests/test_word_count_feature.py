import pytest
import sys
from unittest.mock import MagicMock, patch
from pyqwk.core import ProcessingSettings, matches_filters, ParsedMessage, MessageHeader, process_merged_files
import os

def test_word_count_filtering():
    """Verify that messages can be filtered by word count."""
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", min_words=5, max_words=10
    )

    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " ")

    # Too short (4 words)
    msg1 = ParsedMessage(text="One two three four.", msgnum=1, refnum=None, confnum=1, header=header)
    assert not matches_filters(msg1, settings, set())

    # Just right (5 words)
    msg2 = ParsedMessage(text="One two three four five.", msgnum=2, refnum=None, confnum=1, header=header)
    assert matches_filters(msg2, settings, set())

    # Just right (10 words)
    msg3 = ParsedMessage(text="One two three four five six seven eight nine ten.", msgnum=3, refnum=None, confnum=1, header=header)
    assert matches_filters(msg3, settings, set())

    # Too long (11 words)
    msg4 = ParsedMessage(text="One two three four five six seven eight nine ten eleven.", msgnum=4, refnum=None, confnum=1, header=header)
    assert not matches_filters(msg4, settings, set())

def test_word_count_sorting():
    """Verify that messages can be sorted by word count."""
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", sort="words", reverse=False
    )

    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " ")

    msg_short = ParsedMessage(text="Short msg", msgnum=1, refnum=None, confnum=1, header=header)
    msg_long = ParsedMessage(text="This is a much longer message with more words", msgnum=2, refnum=None, confnum=1, header=header)
    msg_medium = ParsedMessage(text="Medium length message here", msgnum=3, refnum=None, confnum=1, header=header)

    # We need to mock load_data and handle_output to test process_merged_files
    messages = [msg_long, msg_short, msg_medium]

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (messages, {1: "General"})

        # Use a list to capture messages passed to write_messages
        with patch('pyqwk.core.write_messages') as mock_write:
            process_merged_files(["dummy.qwk"], settings, MagicMock())

            # Get the messages passed to write_messages
            args, _ = mock_write.call_args
            sorted_msgs = args[0]

            assert [m.msgnum for m in sorted_msgs] == [1, 3, 2] # 2, 4, 9 words respectively

def test_gui_word_count_column():
    """Verify that the GUI initializes with a Words column."""
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'):

        from pyqwk.gui import QwkGuiApp

        app = QwkGuiApp(mock_root)

        # Check that Words is in column_labels
        assert "Words" in app.column_labels

        # Check treeview columns (using the mock call)
        found_words = False
        for call in mock_ttk.Treeview.call_args_list:
            _, kwargs = call
            if 'columns' in kwargs and "Words" in kwargs['columns']:
                found_words = True
                break
        assert found_words

def test_gui_word_count_display():
    """Verify that word count is displayed in the treeview."""
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk') as mock_tk, \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'), \
         patch('pyqwk.gui.load_data') as mock_load, \
         patch('pyqwk.gui.messagebox'):

        from pyqwk.gui import QwkGuiApp

        mock_tree = mock_ttk.Treeview.return_value
        mock_tree.get_children.return_value = []
        mock_tree.exists.return_value = False

        # Mock StringVar.get and BooleanVar.get to return safe defaults
        mock_tk.StringVar.return_value.get.return_value = ""
        mock_tk.BooleanVar.return_value.get.return_value = False

        # Ensure private_var is True by default as in gui.py
        def mock_bool_init(value=False):
            m = MagicMock()
            m.get.return_value = value
            return m
        mock_tk.BooleanVar.side_effect = mock_bool_init

        header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " ")
        msg = ParsedMessage(text="One two three.", msgnum=1, refnum=None, confnum=1, header=header)

        mock_load.return_value = ([msg], {1: "General"})

        app = QwkGuiApp(mock_root)

        # Manually ensure private messages are shown for the test
        app.private_var.get.return_value = True

        app.current_paths = ["test.qwk"]
        # Clear mock calls before load_messages
        mock_tree.insert.reset_mock()
        app.load_messages(["test.qwk"])

        # Find the insert call
        found_words = False
        for call in mock_tree.insert.call_args_list:
            _, kwargs = call
            values = kwargs.get('values', [])
            # index of Words is 6
            if len(values) > 7 and values[7] == 3:
                found_words = True
                break

        assert found_words

def test_gui_word_limits_ui_present():
    """Verify that Word Limits UI elements are present in the toolbar."""
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk'), \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'):

        from pyqwk.gui import QwkGuiApp

        # Track Labelframe titles
        labelframe_titles = []
        def mock_labelframe_init(master, **kwargs):
            if 'text' in kwargs:
                labelframe_titles.append(kwargs['text'])
            return MagicMock()
        mock_ttk.Labelframe.side_effect = mock_labelframe_init

        app = QwkGuiApp(mock_root)

        assert "Word Limits" in labelframe_titles
        assert hasattr(app, "min_words_var")
        assert hasattr(app, "max_words_var")
        assert hasattr(app, "min_words_entry")
        assert hasattr(app, "max_words_entry")
