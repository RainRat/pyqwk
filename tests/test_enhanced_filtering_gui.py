from unittest.mock import MagicMock, patch
import sys
from pyqwk.core import ParsedMessage, MessageHeader

def test_enhanced_filtering_gui_elements():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk') as mock_tk, \
         patch('pyqwk.gui.ttk'), \
         patch('pyqwk.gui.font'):

        mock_tk.StringVar().get().strip.return_value = ""
        mock_tk.BooleanVar().get.return_value = False

        from pyqwk.gui import QwkGuiApp
        app = QwkGuiApp(mock_root)

        # Check if new BooleanVars exist
        assert hasattr(app, "has_questions_var")
        assert hasattr(app, "has_quotes_var")

        # Check if 'Words' column is in labels
        assert "Words" in app.column_labels

        # Manually set the values to avoid MagicMock/patch.object complications
        app.has_questions_var = MagicMock()
        app.has_questions_var.get.return_value = True
        app.has_quotes_var = MagicMock()
        app.has_quotes_var.get.return_value = False

        settings = app._current_settings()
        assert settings.has_questions is True
        assert settings.has_quotes is False

def test_words_column_population():
    mock_root = MagicMock()
    with patch('pyqwk.gui.tk') as mock_tk, \
         patch('pyqwk.gui.ttk') as mock_ttk, \
         patch('pyqwk.gui.font'), \
         patch('pyqwk.gui.load_data') as mock_load, \
         patch('pyqwk.gui.messagebox'):

        mock_tk.StringVar().get().strip.return_value = ""
        mock_tk.BooleanVar().get.return_value = False

        mock_tree = MagicMock()
        mock_ttk.Treeview.return_value = mock_tree

        header = MessageHeader(" ", 1, "01-01-23", "12:00", "All", "Author", "Subject", "", None, 1, " ", 1, 0, " ")
        msg = ParsedMessage("One two three", 1, None, 1, header)

        mock_load.return_value = ([msg], {1: "Conf"})

        from pyqwk.gui import QwkGuiApp
        app = QwkGuiApp(mock_root)
        app.load_messages(["test.qwk"])

        # Verify insert was called with the word count (3)
        # The values tuple is (flags, msgnum, from, to, date, size, words, conf, bbs)
        # In current code: flags(0), num(1), from(2), to(3), date(4), size(5), words(6), conf(7), bbs(8)
        found_call = False
        for call in mock_tree.insert.call_args_list:
            _, kwargs = call
            if 'values' in kwargs:
                values = kwargs['values']
                if len(values) > 6 and values[6] == 3:
                    found_call = True
                    break
        assert found_call
