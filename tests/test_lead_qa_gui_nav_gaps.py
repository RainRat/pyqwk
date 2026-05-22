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


@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.font"),
    ):
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        mock_combo = MagicMock()
        mock_ttk.Combobox.return_value = mock_combo

        yield {
            "tk": mock_tk,
            "ttk": mock_ttk,
            "combo": mock_combo,
        }


def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)


def test_navigate_conference_early_return_on_focus(mock_gui_deps):
    app = get_app()
    values = ["All", "1: General"]
    app.conf_combo.__getitem__.side_effect = lambda k: values if k == "values" else None
    app.conf_combo.current.reset_mock()

    app.root.focus_get.return_value = app.search_entry
    app._navigate_conference(1)
    app.conf_combo.current.assert_not_called()

    app.root.focus_get.return_value = app.exclude_entry
    app._navigate_conference(1)
    app.conf_combo.current.assert_not_called()


def test_navigate_conference_unselected_combobox(mock_gui_deps):
    app = get_app()
    values = ["All", "1: General", "2: Tech"]
    app.conf_combo.__getitem__.side_effect = lambda k: values if k == "values" else None
    app.conf_combo.current.return_value = -1

    with patch.object(app, "reload_messages"):
        app._navigate_conference(1)
        app.conf_combo.current.assert_any_call(0)

        app.conf_combo.current.reset_mock()
        app.conf_combo.current.return_value = -1
        app._navigate_conference(-1)
        app.conf_combo.current.assert_any_call(2)
