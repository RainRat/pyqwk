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

# Mocking GUI dependencies
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

def get_app():
    from pyqwk.gui import QwkGuiApp
    root = MagicMock()
    return QwkGuiApp(root)

class TestGuiConferenceFilter:
    def test_conference_population(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages:

            mock_load_data.return_value = (bytearray(), {1: "General", 2: "Tech"})
            mock_parse_messages.return_value = []

            app.load_messages("test.qwk")

            # Check if combobox values are set
            # Values are populated when cache path != current path
            expected_values = ["All Conferences", "1: General", "2: Tech"]
            mock_gui_deps["combo"].__setitem__.assert_any_call('values', expected_values)
            assert app.conf_mapping == {"1: General": 1, "2: Tech": 2}

    def test_conference_filtering(self, mock_gui_deps):
        app = get_app()
        app.conf_combo.get.return_value = "1: General"
        app.conf_mapping = {"1: General": 1}

        settings = app._current_settings()
        assert settings.conferences == ["1"]

    def test_caching_mechanism(self, mock_gui_deps):
        app = get_app()
        with patch("pyqwk.gui.load_data") as mock_load_data, \
             patch("pyqwk.gui.parse_messages") as mock_parse_messages, \
             patch("pyqwk.gui.matches_filters") as mock_matches_filters:

            mock_load_data.return_value = (bytearray(), {1: "General"})
            mock_parse_messages.return_value = []
            mock_matches_filters.return_value = True

            # First load
            app.load_messages("test.qwk")
            assert mock_load_data.call_count == 1

            # Second load with same path (should use cache)
            app.load_messages("test.qwk")
            assert mock_load_data.call_count == 1

            # Third load with different path (should reload)
            app.load_messages("other.qwk")
            assert mock_load_data.call_count == 2
