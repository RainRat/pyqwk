import sys
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import ParsedMessage, MessageHeader, BBSInfo, ConferenceMap

def test_gui_mine_highlighting():
    # Mocking dependencies for pyqwk.gui
    mock_tk = MagicMock()
    mock_ttk = MagicMock()

    # We must mock sys.modules before importing the app
    with patch.dict(sys.modules, {
        "tkinter": mock_tk,
        "tkinter.filedialog": MagicMock(),
        "tkinter.messagebox": MagicMock(),
        "tkinter.ttk": mock_ttk
    }):
        from pyqwk.gui import QwkGuiApp

        # Configure variables
        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m
        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)

        root = MagicMock()
        app = QwkGuiApp(root)

        # Setup test data
        header_mine_from = MessageHeader(
            status=' ', msgnum=1, msgdate='01-01-90', msgtime='12:00',
            msgto='Someone Else', msgfrom='MY NAME', msgsubject='Subject 1',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        header_mine_to = MessageHeader(
            status=' ', msgnum=2, msgdate='01-01-90', msgtime='12:05',
            msgto='my name', msgfrom='Someone Else', msgsubject='Subject 2',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )
        header_others = MessageHeader(
            status=' ', msgnum=3, msgdate='01-01-90', msgtime='12:10',
            msgto='Alice', msgfrom='Bob', msgsubject='Subject 3',
            msgpassword='', refnum=None, numblocks=1, msgflag=' ',
            confnum=1, lognum=1, nettag=''
        )

        app.messages = [
            ParsedMessage("Body 1", 1, None, 1, header_mine_from),
            ParsedMessage("Body 2", 2, None, 1, header_mine_to),
            ParsedMessage("Body 3", 3, None, 1, header_others),
        ]

        # Mock board_dict with BBS info
        board_dict = ConferenceMap({1: "General"})
        board_dict.bbs_info = BBSInfo(user_name="My Name")
        app.board_dict = board_dict

        # Mock load_data to return these values
        with patch("pyqwk.gui.load_data", return_value=(bytearray(), board_dict)), \
             patch("pyqwk.gui.parse_messages", return_value=app.messages), \
             patch("pyqwk.gui.matches_filters", return_value=True), \
             patch("pyqwk.gui.process_message", side_effect=lambda t, *args: t):

            app.load_messages("dummy.qwk")

            # Verify treeview inserts
            # app.message_list.insert(parent_iid, tk.END, iid=iid, text=subject, values=..., tags=...)
            calls = app.message_list.insert.call_args_list

            # Message 1: From me (tags should include 'mine')
            args1 = calls[0].kwargs
            assert "mine" in args1["tags"]

            # Message 2: To me (tags should include 'mine')
            args2 = calls[1].kwargs
            assert "mine" in args2["tags"]

            # Message 3: Others (tags should NOT include 'mine')
            args3 = calls[2].kwargs
            assert "mine" not in args3["tags"]

if __name__ == "__main__":
    # If run directly, run the test
    pytest.main([__file__])
