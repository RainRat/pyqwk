import sys
from unittest.mock import MagicMock, patch
import pytest
import tkinter as tk

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.gui import QwkGuiApp
from pyqwk.core import (
    RE_URL_PATTERN,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    matches_filters,
    calculate_archive_stats,
    render_stats_as_text
)

@pytest.fixture(autouse=True)
def mock_gui_deps():
    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.filedialog") as mock_fd, \
         patch("pyqwk.gui.messagebox") as mock_mb:

        # Configure Variable mocks
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        # Tkinter constants
        mock_tk.END = "end"
        mock_tk.HORIZONTAL = "horizontal"
        mock_tk.VERTICAL = "vertical"
        mock_tk.BOTH = "both"
        mock_tk.X = "x"
        mock_tk.Y = "y"
        mock_tk.LEFT = "left"
        mock_tk.RIGHT = "right"
        mock_tk.TOP = "top"
        mock_tk.BOTTOM = "bottom"
        mock_tk.SUNKEN = "sunken"
        mock_tk.W = "w"
        mock_tk.E = "e"
        mock_tk.WORD = "word"
        mock_tk.DISABLED = "disabled"
        mock_tk.NORMAL = "normal"
        mock_tk.INSERT = "insert"

        # Mock classes/types
        class TclError(Exception):
            pass
        mock_tk.TclError = TclError

        # Mock Combobox
        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "combo": mock_combo,
        }

def get_app(initial_paths=None):
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root, initial_paths=initial_paths)

def test_url_pattern():
    assert RE_URL_PATTERN.search("Check out https://google.com")
    assert RE_URL_PATTERN.search("Visit http://example.com/path?q=1")
    assert RE_URL_PATTERN.search("Gopher: gopher://floodgap.com")
    assert RE_URL_PATTERN.search("FTP: ftp://files.org")
    assert RE_URL_PATTERN.search("Telnet: telnet://bbs.org")
    assert RE_URL_PATTERN.search("WWW: www.google.com")
    assert not RE_URL_PATTERN.search("just some text")
    assert not RE_URL_PATTERN.search("mail@example.com")

def test_has_links_filter():
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437', has_links=True
    )

    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")

    msg_with_url = ParsedMessage("Visit https://google.com", 1, None, 1, header)
    msg_without_url = ParsedMessage("Hello world", 2, None, 1, header)

    assert matches_filters(msg_with_url, settings, set()) is True
    assert matches_filters(msg_without_url, settings, set()) is False

def test_url_stats(tmp_path):
    # Mock data for stats
    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")
    messages = [
        ParsedMessage("Link 1: https://a.com", 1, None, 1, header),
        ParsedMessage("Link 2: https://b.com and https://a.com", 2, None, 1, header),
        ParsedMessage("No link here", 3, None, 1, header),
    ]

    # We need to mock load_data to return our messages
    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (messages, {1: "General"})

        settings = ProcessingSettings(
            verbose=False, private=True, no_header=False, truncate_signatures=False,
            cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
            redact_pii=False, format='text', separator='none', output_mode='stdout',
            output_path=None, encoding='cp437'
        )

        stats = calculate_archive_stats(["dummy.qwk"], settings, MagicMock())

        # Verify links were found and counted correctly
        links = {link['url']: link['count'] for link in stats['links']}
        assert "https://a.com" in links
        assert "https://b.com" in links
        assert links["https://a.com"] == 2
        assert links["https://b.com"] == 1

        # Verify text rendering includes links
        report = render_stats_as_text(stats)
        assert "Top Links:" in report
        assert "https://a.com" in report

@pytest.fixture
def mock_gui():
    root = tk.Tk()
    app = QwkGuiApp(root)
    yield app
    root.destroy()

def test_gui_url_rendering(mock_gui_deps):
    app = get_app()
    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")
    msg = ParsedMessage("Visit https://google.com for more info.", 1, None, 1, header)
    app.messages = [msg]
    app.board_dict = {1: "General"}

    with patch('webbrowser.open') as mock_open:
        app._render_message(0)

        # Verify URL was inserted with specific tags
        found_url = False
        for call in app.detail_text.insert.call_args_list:
            if len(call.args) >= 2 and "https://google.com" in call.args[1]:
                tags = call.args[2]
                if isinstance(tags, tuple) and "link" in tags and any(t.startswith("url_") for t in tags):
                    found_url = True
                    break
        assert found_url

def test_gui_has_links_filter(mock_gui_deps):
    app = get_app()
    app.has_links_var.get.return_value = True
    settings = app._current_settings()
    assert settings.has_links is True
