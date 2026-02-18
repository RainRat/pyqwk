import sys
from unittest.mock import MagicMock, patch, call
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = mock_ttk

from pyqwk.core import ProcessingSettings, ParsedMessage, MessageHeader

# Ensure pyqwk.gui uses our mocks
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

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "filedialog": mock_fd,
            "messagebox": mock_mb,
        }

def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)

class TestQwkGui:
    def test_initialization(self, mock_gui_deps):
        app = get_app()
        assert app.root is not None
        assert hasattr(app, 'message_list')
        app.root.bind.assert_any_call("<Control-o>", app.open_file)
        app.root.bind.assert_any_call("<Escape>", app.clear_search)

    def test_current_settings(self, mock_gui_deps):
        app = get_app()
        app.clean_var.get.return_value = True
        app.private_var.get.return_value = False
        app.search_var.get.return_value = "test search"

        settings = app._current_settings()
        assert isinstance(settings, ProcessingSettings)
        assert settings.private is False
        assert settings.search_term == "test search"

    def test_load_messages_success(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters, \
             patch("pyqwk.gui.process_message") as mock_process_message:

            mock_load_data.return_value = (bytearray(), {1: "General"})
            header = MessageHeader(
                status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
                msgto='All', msgfrom='User', msgsubject='Subject',
                msgpassword='', refnum=None, numblocks=1, msgflag=' ',
                confnum=1, lognum=1, nettag=''
            )
            mock_parse_messages.return_value = [
                ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)
            ]
            mock_matches_filters.return_value = True
            mock_process_message.return_value = "Processed Body"

            app.load_messages("test.qwk")
            assert len(app.messages) == 1
            app.message_list.insert.assert_called()

    def test_load_messages_error(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data", side_effect=Exception("Load failed")):
            app.load_messages("bad.qwk")
            mock_gui_deps["messagebox"].showerror.assert_called_with("Failed to load QWK", "Load failed")

    def test_clear_conf_filter(self, mock_gui_deps):
        app = get_app()
        app.conf_combo.set("1: General")
        with patch.object(app, 'reload_messages') as mock_reload:
            app.clear_conf_filter()
            app.conf_combo.set.assert_called_with("All Conferences")
            mock_reload.assert_called_once()
            app.message_list.focus_set.assert_called_once()

    def test_on_message_selected(self, mock_gui_deps):
        app = get_app()
        header = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='All', msgfrom='User', msgsubject='Subject',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        app.messages = [ParsedMessage(text="Body", msgnum=1, refnum=None, confnum=1, header=header)]
        app.message_list.selection.return_value = ("0",)
        app.on_message_selected()
        app.detail_text.insert.assert_any_call(mock_gui_deps["tk"].END, "Body", "body")

    def test_open_file_cancel(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["filedialog"].askopenfilename.return_value = ""
        app.open_file()
        assert app.current_path is None

    def test_open_file_select(self, mock_gui_deps):
        app = get_app()
        mock_gui_deps["filedialog"].askopenfilename.return_value = "selected.qwk"
        with patch.object(app, 'load_messages') as mock_load:
            app.open_file()
            assert app.current_path == "selected.qwk"
            mock_load.assert_called_with("selected.qwk")

    def test_sort_column(self, mock_gui_deps):
        app = get_app()
        app.message_list.get_children.return_value = ["item1", "item2"]
        app.message_list.set.side_effect = lambda k, col: "Value2" if k == "item1" else "Value1"
        app.threaded_var.get.return_value = False
        app.sort_column("From", False)
        app.message_list.move.assert_has_calls([call("item2", "", 0), call("item1", "", 1)])

    def test_sort_column_threaded_disabled(self, mock_gui_deps):
        app = get_app()
        app.message_list.move.reset_mock()
        app.threaded_var.get.return_value = True
        app.sort_column("From", False)
        app.message_list.move.assert_not_called()
