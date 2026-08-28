from unittest.mock import MagicMock, patch

import pytest


def test_toolbar_consolidation():
    """Verify that the toolbar has been consolidated and 'Discovery' label is removed."""

    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.messagebox"),
        patch("pyqwk.gui.filedialog"),
        patch("pyqwk.gui.simpledialog"),
    ):
        # Ensure classes return mocks
        mock_tk.BooleanVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.StringVar.side_effect = lambda **kwargs: MagicMock()
        mock_tk.IntVar.side_effect = lambda **kwargs: MagicMock()

        from pyqwk.gui import QwkGuiApp

        root = MagicMock()
        QwkGuiApp(root)

        # Check that "Filters" labelframe exists
        filter_frame_calls = [
            call
            for call in mock_ttk.Labelframe.call_args_list
            if call[1].get("text") == "Filters"
        ]
        assert len(filter_frame_calls) == 1, "Expected one 'Filters' labelframe"

        # Check that "BBS & Conferences" labelframe exists
        bbs_conf_frame_calls = [
            call
            for call in mock_ttk.Labelframe.call_args_list
            if call[1].get("text") == "BBS & Conferences"
        ]
        assert len(bbs_conf_frame_calls) == 1, "Expected one 'BBS & Conferences' labelframe"

        # Check that "Discovery:" label DOES NOT exist
        discovery_label_calls = [
            call
            for call in mock_ttk.Label.call_args_list
            if call[1].get("text") == "Discovery:"
        ]
        assert len(discovery_label_calls) == 0, (
            "Expected 'Discovery:' label to be removed"
        )

        # Verify all filter checkboxes exist across groups
        expected_filters = {
            "Private",
            "Attachments",
            "My Messages",
            "On This Day",
            "Links",
            "Emails",
            "Phones",
            "Colors",
            "Message Links",
            "Regex",
            "Conversations",
            "Clean View",
            "Wrap",
            "Remove Colors",
            "Hide Personal Info",
            "Embed Attachments",
        }

        checkbutton_calls = [
            call[1].get("text") for call in mock_ttk.Checkbutton.call_args_list
        ]

        for f in expected_filters:
            assert f in checkbutton_calls, f"Expected filter checkbox '{f}' not found"

        # Verify they are all in the same cluster (packed into the same parent)
        # Find the parent of "Attachments"
        attachments_call = [
            call
            for call in mock_ttk.Checkbutton.call_args_list
            if call[1].get("text") == "Attachments"
        ][0]
        filters_parent = attachments_call[0][0]

        # Check that "Links" (formerly in Discovery) shares the same parent
        links_call = [
            call
            for call in mock_ttk.Checkbutton.call_args_list
            if call[1].get("text") == "Links"
        ][0]
        assert links_call[0][0] == filters_parent, (
            "Filters and Discovery checkboxes should share the same parent frame"
        )


if __name__ == "__main__":
    pytest.main([__file__])
