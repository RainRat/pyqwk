
import sys
from unittest.mock import MagicMock, patch

import pytest

def test_toolbar_consolidation():
    """Verify that the toolbar has been consolidated and 'Discovery' label is removed."""

    with patch("pyqwk.gui.tk") as mock_tk, \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.messagebox"), \
         patch("pyqwk.gui.filedialog"), \
         patch("pyqwk.gui.simpledialog"):

        # Ensure classes return mocks
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        from pyqwk.gui import QwkGuiApp
        root = MagicMock()
        app = QwkGuiApp(root)

        # Check that "Filters:" label exists
        filter_label_calls = [
            call for call in mock_ttk.Label.call_args_list
            if call[1].get('text') == "Filters:"
        ]
        assert len(filter_label_calls) == 1, "Expected one 'Filters:' label"

        # Check that "Discovery:" label DOES NOT exist
        discovery_label_calls = [
            call for call in mock_ttk.Label.call_args_list
            if call[1].get('text') == "Discovery:"
        ]
        assert len(discovery_label_calls) == 0, "Expected 'Discovery:' label to be removed"

        # Verify all 7 filter checkboxes exist
        expected_filters = {
            "Attachments", "My Messages", "On This Day",
            "Links", "Emails", "Phones", "ANSI"
        }

        checkbutton_calls = [
            call[1].get('text') for call in mock_ttk.Checkbutton.call_args_list
        ]

        for f in expected_filters:
            assert f in checkbutton_calls, f"Expected filter checkbox '{f}' not found"

        # Verify they are all in the same cluster (packed into the same parent)
        # Find the parent of "Attachments"
        attachments_call = [
            call for call in mock_ttk.Checkbutton.call_args_list
            if call[1].get('text') == "Attachments"
        ][0]
        filters_parent = attachments_call[0][0]

        # Check that "Links" (formerly in Discovery) shares the same parent
        links_call = [
            call for call in mock_ttk.Checkbutton.call_args_list
            if call[1].get('text') == "Links"
        ][0]
        assert links_call[0][0] == filters_parent, "Filters and Discovery checkboxes should share the same parent frame"

if __name__ == "__main__":
    pytest.main([__file__])
