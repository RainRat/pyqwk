import sys
import io
from unittest.mock import MagicMock, patch
from collections import defaultdict
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    ProcessingSettings,
    matches_filters,
)


@pytest.fixture
def app():
    root = MagicMock()
    with patch("pyqwk.gui.tk"), patch("pyqwk.gui.ttk"), patch("pyqwk.gui.simpledialog"):
        app = QwkGuiApp(root)
        app.message_list = MagicMock()
        return app


def _make_settings(**kwargs):
    defaults = dict(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        conferences=None,
        authors=None,
        recipients=None,
        subjects=None,
        search_term=None,
        after=None,
        before=None,
        regex=False,
        dry_run=False,
        strip_ansi=False,
        quiet=False,
        headers_only=False,
        oneline=False,
        extract_attachments=False,
        limit=None,
        skip=None,
        sort=None,
        reverse=False,
        merge=True,
        unique=False,
        organize=False,
        merge_stats=False,
        organize_by_bbs=False,
        include_toc=False,
        has_attachments=False,
        mine=False,
        on_this_day=False,
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def test_gui_load_structured_data(app):
    """Test loading structured data (list of messages) in GUI."""
    h1 = MessageHeader(
        " ",
        101,
        "01-01-23",
        "12:00",
        "To1",
        "From1",
        "Subj1",
        "",
        None,
        1,
        " ",
        1,
        1,
        "",
    )
    msg = ParsedMessage("Text 1", 101, None, 1, h1)

    mock_data = ([msg], {1: "General"})

    with (
        patch("pyqwk.gui.load_data", return_value=mock_data),
        patch("pyqwk.gui.get_allowed_conferences", return_value=[1]),
        patch("pyqwk.gui.os.path.exists", return_value=True),
        patch("pyqwk.gui.matches_filters", return_value=True),
    ):
        app.load_messages("dummy.json")

    assert len(app.messages) == 1


def test_prompt_jump_to_message_empty(app):
    """Test jump-to-message with empty message list."""
    app.messages = []
    with patch("pyqwk.gui.simpledialog.askinteger") as mock_ask:
        app.prompt_jump_to_message()
        mock_ask.assert_not_called()


def test_prompt_jump_to_message_invalid_selection(app):
    """Test jump-to-message with invalid selection string."""
    h1 = MessageHeader(
        " ",
        101,
        "01-01-23",
        "12:00",
        "To1",
        "From1",
        "Subj1",
        "",
        None,
        1,
        " ",
        1,
        1,
        "",
    )
    app.messages = [ParsedMessage("Text 1", 101, None, 1, h1)]
    app.message_list.selection.return_value = ["invalid"]

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=101),
        patch.object(app, "_select_by_index") as mock_select,
    ):
        app.prompt_jump_to_message()
        mock_select.assert_called_with(0)


def test_prompt_jump_to_message_global_fallback(app):
    """Test jump-to-message global fallback when current conf search fails."""
    h1 = MessageHeader(
        " ",
        101,
        "01-01-23",
        "12:00",
        "To1",
        "From1",
        "Subj1",
        "",
        None,
        1,
        " ",
        1,
        1,
        "",
    )
    h2 = MessageHeader(
        " ",
        102,
        "01-01-23",
        "12:05",
        "To2",
        "From2",
        "Subj2",
        "",
        None,
        1,
        " ",
        2,
        1,
        "",
    )
    app.messages = [
        ParsedMessage("Text 1", 101, None, 1, h1),
        ParsedMessage("Text 2", 102, None, 2, h2),
    ]
    app.message_list.selection.return_value = ["0"]

    with (
        patch("pyqwk.gui.simpledialog.askinteger", return_value=102),
        patch.object(app, "_select_by_index") as mock_select,
    ):
        app.prompt_jump_to_message()
        mock_select.assert_called_with(1)


def test_threading_visited_branches():
    """Test visited branches in core.py visit_iterative (lines 3572, 3628)."""
    h1 = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, ""
    )
    h2 = MessageHeader(
        " ", 2, "01-01-23", "12:05", "To2", "From2", "Subj2", "", "1", 1, " ", 1, 1, ""
    )
    h3 = MessageHeader(
        " ", 3, "01-01-23", "12:10", "To3", "From3", "Subj3", "", "3", 1, " ", 1, 1, ""
    )

    msg1 = ParsedMessage("Text 1", 1, None, 1, h1)
    msg2 = ParsedMessage("Text 2", 2, "1", 1, h2)
    msg3 = ParsedMessage("Text 3", 3, None, 1, h3)

    def mock_defaultdict(factory):
        if factory == list:
            d = defaultdict(list)
            # Root 0 has child 1. Root 2 also has child 1.
            d[0] = [1]
            d[2] = [1]
            return d
        return defaultdict(factory)

    settings = _make_settings(threaded=True, merge=True)
    with patch("pyqwk.core.defaultdict", side_effect=mock_defaultdict):
        # We also need to mock roots to include 0 and 2.
        with (
            patch("pyqwk.core.load_data", return_value=(bytearray(), {})),
            patch("pyqwk.core.parse_messages", return_value=[msg1, msg2, msg3]),
            patch("pyqwk.core.sys.stdout", new_callable=io.StringIO),
        ):
            process_merged_files(["archive.qwk"], settings, MagicMock())
            # No direct return from process_merged_files, but we verify it runs.
            # We check that it didn't crash.


def test_any_match_truthy_empty():
    """Test any_match with a truthy empty collection (line 1592)."""

    class TruthyEmpty:
        def __bool__(self):
            return True

        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

    settings = _make_settings(authors=TruthyEmpty())
    h1 = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To1", "From1", "Subj1", "", None, 1, " ", 1, 1, ""
    )
    msg = ParsedMessage("Text 1", 1, None, 1, h1)

    assert matches_filters(msg, settings, set()) is True
