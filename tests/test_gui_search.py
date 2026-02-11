from unittest.mock import MagicMock, patch
import pytest
from tests.test_gui import mock_gui_deps, get_app

class TestQwkGuiNewFeatures:
    def test_search_bindings(self, mock_gui_deps):
        app = get_app()
        # Verify search entry bindings
        calls = app.search_entry.bind.call_args_list
        bound_events = [c[0][0] for c in calls]
        assert "<Return>" in bound_events
        assert "<Escape>" in bound_events

    def test_clear_search(self, mock_gui_deps):
        app = get_app()
        app.search_var.set("something")
        app.clear_search()
        app.search_var.set.assert_called_with("")
        app.message_list.focus_set.assert_called()
