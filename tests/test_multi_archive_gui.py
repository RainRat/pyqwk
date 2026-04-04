import sys
from unittest.mock import MagicMock, patch, ANY
import pytest

# Mock tkinter before any pyqwk.gui imports
mock_tk = MagicMock()
mock_ttk = MagicMock()
mock_fd = MagicMock()
mock_mb = MagicMock()
sys.modules["tkinter"] = mock_tk
sys.modules["tkinter.filedialog"] = mock_fd
sys.modules["tkinter.messagebox"] = mock_mb
sys.modules["tkinter.ttk"] = mock_ttk
sys.modules["tkinter.simpledialog"] = MagicMock()

from pyqwk.gui import QwkGuiApp

@pytest.fixture
def app():
    root = MagicMock()
    # Avoid initial load by passing None
    app = QwkGuiApp(root, initial_paths=None)
    # Mock some widgets
    app.message_list = MagicMock()
    app.status_label = MagicMock()
    app.conf_combo = MagicMock()
    app.detail_text = MagicMock()
    return app

def test_open_file_multiple(app):
    """Test selecting multiple files in the open dialog."""
    with patch("pyqwk.gui.filedialog.askopenfilenames") as mock_ask:
        mock_ask.return_value = ["test1.qwk", "test2.qwk"]
        with patch.object(app, 'load_messages') as mock_load:
            app.open_file()
            mock_load.assert_called_once_with(["test1.qwk", "test2.qwk"])
            assert app.current_paths == ["test1.qwk", "test2.qwk"]

def test_open_folder(app):
    """Test opening a folder of archives."""
    with patch("pyqwk.gui.filedialog.askdirectory") as mock_ask_dir, \
         patch("pyqwk.gui.expand_paths") as mock_expand:
        mock_ask_dir.return_value = "/some/path"
        mock_expand.return_value = ["/some/path/a.qwk", "/some/path/b.rep"]

        with patch.object(app, 'load_messages') as mock_load:
            app.open_folder()
            mock_expand.assert_called_once_with(["/some/path"])
            mock_load.assert_called_once_with(["/some/path/a.qwk", "/some/path/b.rep"])
            assert app.current_paths == ["/some/path/a.qwk", "/some/path/b.rep"]

def test_load_messages_multi_merge(app):
    """Test that load_messages merges data from multiple paths."""
    paths = ["path1.qwk", "path2.qwk"]

    # Mock data for load_data
    from pyqwk.core import ParsedMessage, MessageHeader

    def create_msg(conf, msgnum, text, subject):
        header = MessageHeader(" ", msgnum, "01-01-23", "12:00", "To", "From", subject, "", None, 1, " ", conf, 0, "")
        return ParsedMessage(text, msgnum, None, conf, header)

    m1 = create_msg(1, 101, "Text 1", "Subj 1")
    m2 = create_msg(2, 201, "Text 2", "Subj 2")

    mock_data = {
        "path1.qwk": ([m1], {1: "Conf 1"}),
        "path2.qwk": ([m2], {2: "Conf 2"})
    }

    with patch("pyqwk.gui.load_data") as mock_load_data, \
         patch("pyqwk.gui.matches_filters") as mock_matches:
        mock_load_data.side_effect = lambda path, logger, enc: mock_data[path]
        mock_matches.return_value = True

        app.load_messages(paths)

        assert len(app.messages) == 2
        assert app.messages[0].source_file == "path1.qwk"
        assert app.messages[1].source_file == "path2.qwk"
        assert app.board_dict == {1: "Conf 1", 2: "Conf 2"}

def test_show_stats_multi(app):
    """Test that stats window handles multiple paths."""
    app.current_paths = ["a.qwk", "b.qwk"]

    with patch("pyqwk.gui.calculate_archive_stats") as mock_calc, \
         patch("pyqwk.gui.render_stats_as_text") as mock_render, \
         patch("pyqwk.gui.tk.Toplevel") as mock_top:

        mock_calc.return_value = {"some": "stats"}
        mock_render.return_value = "Report Content"

        app.show_stats_window()

        mock_calc.assert_called_once_with(["a.qwk", "b.qwk"], ANY, app.logger)
        mock_top.assert_called_once()
