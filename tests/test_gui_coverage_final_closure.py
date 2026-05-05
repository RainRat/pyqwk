import sys
from unittest.mock import MagicMock, patch


# Mock tkinter BEFORE any pyqwk imports
class MockTclError(Exception):
    pass


if "tkinter" in sys.modules:
    existing_tk = sys.modules["tkinter"]
    existing_tk.TclError = MockTclError
else:
    mock_tk = MagicMock()
    mock_tk.TclError = MockTclError
    sys.modules["tkinter"] = mock_tk

if "tkinter.ttk" not in sys.modules:
    sys.modules["tkinter.ttk"] = MagicMock()
if "tkinter.filedialog" not in sys.modules:
    sys.modules["tkinter.filedialog"] = MagicMock()
if "tkinter.messagebox" not in sys.modules:
    sys.modules["tkinter.messagebox"] = MagicMock()
if "tkinter.simpledialog" not in sys.modules:
    sys.modules["tkinter.simpledialog"] = MagicMock()

import pytest
from pyqwk.gui import QwkGuiApp
from pyqwk.core import ParsedMessage, MessageHeader, BBSInfo, ConferenceMap


@pytest.fixture
def app():
    root = MagicMock()
    root.after = MagicMock()

    with (
        patch("tkinter.BooleanVar", return_value=MagicMock()),
        patch("tkinter.StringVar", return_value=MagicMock()),
        patch("tkinter.ttk.Treeview", return_value=MagicMock()) as mock_tree,
        patch("tkinter.Text", return_value=MagicMock()) as mock_text,
        patch("tkinter.ttk.Combobox") as mock_combo,
    ):
        # Return distinct mocks for bbs_combo and conf_combo
        bbs_mock = MagicMock(name="bbs_combo")
        conf_mock = MagicMock(name="conf_combo")
        mock_combo.side_effect = [bbs_mock, conf_mock]

        a = QwkGuiApp(root)
        a.message_list = mock_tree.return_value
        a.detail_text = mock_text.return_value
        a.bbs_combo = bbs_mock
        a.conf_combo = conf_mock

        return a


def test_show_list_context_menu_with_bbs(app):
    """Cover line 126: Filter by BBS in context menu."""
    event = MagicMock(x_root=100, y_root=100, y=50)
    app.message_list.identify_row.return_value = "0"

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    # Ensure bbs_name is set to trigger line 126
    app.messages = [
        ParsedMessage(
            text="Hello",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
            bbs_name="MyBBS",
        )
    ]
    app.board_dict = {1: "General"}

    with patch("pyqwk.gui.tk.Menu") as mock_menu_class:
        mock_menu_instance = mock_menu_class.return_value
        app._show_list_context_menu(event)

        # Verify BBS filter command was added
        found_bbs_command = False
        for call in mock_menu_instance.add_command.call_args_list:
            if "Filter by BBS:" in call.kwargs.get("label", ""):
                found_bbs_command = True
                break
        assert found_bbs_command


def test_clear_filters_bbs_exception(app):
    """Cover lines 343-344: Exception when setting bbs_combo current."""
    app.bbs_combo.current.side_effect = Exception("Mock Error")

    app.clear_filters()

    app.bbs_combo.set.assert_called_with("All BBSes")


def test_load_messages_restore_bbs_selection(app, mocker):
    """Cover line 950: restore BBS selection in load_messages."""
    app.current_paths = ["test.qwk"]
    app.bbs_combo.get.return_value = "MyBBS (1)"
    app.bbs_mapping = {"MyBBS (1)": "BBSID"}

    header = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    msg = ParsedMessage("Hello", 1, None, 1, header, bbs_name="MyBBS", bbs_id="BBSID")

    bbs_info = BBSInfo(name="MyBBS", bbs_id="BBSID")
    board_dict = ConferenceMap({1: "General"})
    board_dict.bbs_info = bbs_info

    mocker.patch("pyqwk.gui.load_data", return_value=(bytearray(), board_dict))
    mocker.patch("pyqwk.gui.parse_messages", return_value=[msg])
    # Mock matches_filters to return True so we populate bbs_counts
    mocker.patch("pyqwk.gui.matches_filters", return_value=True)

    app.load_messages(["test.qwk"])

    # Verify that new_bbs_selection was set to the display string matching BBSID
    # In line 950: new_bbs_selection = display_str
    # and then in 954: self.bbs_combo.set(new_bbs_selection)
    app.bbs_combo.set.assert_called_with("MyBBS (1)")
