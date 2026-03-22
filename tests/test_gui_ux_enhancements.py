import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock tkinter before importing pyqwk.gui
mock_tk = MagicMock()
mock_ttk = MagicMock()
sys.modules['tkinter'] = mock_tk
sys.modules['tkinter.ttk'] = mock_ttk
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['tkinter.simpledialog'] = MagicMock()

from pyqwk.gui import QwkGuiApp

class TestGuiUX(unittest.TestCase):
    def setUp(self):
        self.root = MagicMock()
        with patch('pyqwk.gui.expand_paths', return_value=[]):
            self.app = QwkGuiApp(self.root)

    def test_context_menu_bindings(self):
        """Verify that context menu bindings are applied to the widgets."""
        # Check message_list bindings
        calls = self.app.message_list.bind.call_args_list
        bound_events = [c[0][0] for c in calls]
        self.assertIn("<Button-3>", bound_events)
        self.assertIn("<Control-Button-1>", bound_events)

        # Check detail_text bindings
        calls = self.app.detail_text.bind.call_args_list
        bound_events = [c[0][0] for c in calls]
        self.assertIn("<Button-3>", bound_events)
        self.assertIn("<Control-Button-1>", bound_events)
        self.assertIn("<Key>", bound_events)

    def test_block_text_input(self):
        """Verify that text input is blocked but navigation/copy is allowed."""
        mock_event = MagicMock()

        # Test regular key (should block)
        mock_event.state = 0
        mock_event.keysym = "x"
        self.assertEqual(self.app._block_text_input(mock_event), "break")

        # Test Ctrl+C (should allow)
        mock_event.state = 4
        mock_event.keysym = "c"
        self.assertIsNone(self.app._block_text_input(mock_event))

        # Test navigation key (should allow)
        mock_event.state = 0
        mock_event.keysym = "Down"
        self.assertIsNone(self.app._block_text_input(mock_event))

if __name__ == '__main__':
    unittest.main()
