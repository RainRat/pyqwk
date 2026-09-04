import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.font"] = MagicMock()

from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader

@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
        patch("pyqwk.gui.font") as mock_font,
    ):
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

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
            "font": mock_font,
        }

def test_pivot_filter_subject(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    with patch.object(app, "reload_messages") as mock_reload:
        app._pivot_filter(subject="Re: Testing 123")
        # _normalize_subject should strip 'Re: '
        app.search_var.set.assert_called_with("testing 123")
        mock_reload.assert_called_once()

def test_render_message_subject_link(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="Recipient", msgfrom="Author", msgsubject="Original Subject",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)
    app.messages = [msg]

    # Store tag callbacks
    tag_callbacks = {}
    def mock_tag_bind(tag, event, callback):
        tag_callbacks[tag] = callback
    app.detail_text.tag_bind.side_effect = mock_tag_bind

    app._render_message(0)

    # Find subject tag
    subject_tags = [t for t in tag_callbacks if t.startswith("subject_link_")]
    assert len(subject_tags) == 1

    # Verify click calls _pivot_filter with correct (unredacted) subject
    with patch.object(app, "_pivot_filter") as mock_pivot:
        tag_callbacks[subject_tags[0]](None)
        mock_pivot.assert_called_with(subject="Original Subject")

def test_render_message_links_robustness_pii(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    # Enable PII redaction
    app.redact_pii_var.get.return_value = True

    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="john.doe@example.com", msgfrom="jane.smith@example.com",
        msgsubject="Testing 555-1234",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)
    app.messages = [msg]

    tag_callbacks = {}
    def mock_tag_bind(tag, event, callback):
        tag_callbacks[tag] = callback
    app.detail_text.tag_bind.side_effect = mock_tag_bind

    app._render_message(0)

    # Verify that redacted text was inserted but links use original text
    insert_calls = app.detail_text.insert.call_args_list

    # Extract inserted strings
    inserted_texts = [c.args[1] for c in insert_calls]
    # Check for redacted elements
    assert "[EMAIL]" in inserted_texts # From or To
    assert "Testing [PHONE]" in inserted_texts # Subject

    # Find tags
    from_tags = [t for t in tag_callbacks if t.startswith("from_link_")]
    to_tags = [t for t in tag_callbacks if t.startswith("to_link_")]
    subject_tags = [t for t in tag_callbacks if t.startswith("subject_link_")]

    with patch.object(app, "_pivot_filter") as mock_pivot:
        # Check From link
        tag_callbacks[from_tags[0]](None)
        mock_pivot.assert_called_with(author="jane.smith@example.com")

        # Check To link
        tag_callbacks[to_tags[0]](None)
        mock_pivot.assert_called_with(recipient="john.doe@example.com")

        # Check Subject link
        tag_callbacks[subject_tags[0]](None)
        mock_pivot.assert_called_with(subject="Testing 555-1234")

def test_context_menus_have_subject_pivot(mock_gui_deps):
    root = MagicMock()
    app = QwkGuiApp(root)

    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
        msgto="Recipient", msgfrom="Author", msgsubject="Subject To Pivot",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)
    app.messages = [msg]

    # Mock identify_row to return "0"
    app.message_list.identify_row.return_value = "0"

    with patch("pyqwk.gui.tk.Menu") as mock_menu_cls:
        mock_menu = mock_menu_cls.return_value

        # Test List Context Menu
        app._show_list_context_menu(MagicMock(x=0, y=0))

        # Find "Filter by Subject" and "Filter by Recipient" calls
        subj_call = [c for c in mock_menu.add_command.call_args_list if "Filter by Subject" in c.kwargs.get("label", "")]
        assert len(subj_call) == 1
        recip_call = [c for c in mock_menu.add_command.call_args_list if "Filter by Recipient" in c.kwargs.get("label", "")]
        assert len(recip_call) == 1

        # Test Text Context Menu
        mock_menu.add_command.reset_mock()
        app.message_list.selection.return_value = ("0",)
        app._show_text_context_menu(MagicMock())

        subj_call = [c for c in mock_menu.add_command.call_args_list if "Filter by Subject" in c.kwargs.get("label", "")]
        assert len(subj_call) == 1
        recip_call = [c for c in mock_menu.add_command.call_args_list if "Filter by Recipient" in c.kwargs.get("label", "")]
        assert len(recip_call) == 1

        # Verify Copy commands also present in Text Context Menu
        copy_labels = [c.kwargs.get("label", "") for c in mock_menu.add_command.call_args_list if "Copy " in c.kwargs.get("label", "")]
        assert "Copy Subject" in copy_labels
        assert "Copy From" in copy_labels
        assert "Copy To" in copy_labels
        assert "Copy Num" in copy_labels
