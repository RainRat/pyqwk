from unittest.mock import MagicMock, patch

# We want to avoid global sys.modules mocking here as it's brittle when running the full suite
# Instead we will patch the components specifically for the test.

def test_gui_horizontal_scrollbar_initialization():
    # Patch everything in pyqwk.gui to avoid side effects
    # We must patch where it's USED, which is pyqwk.gui.tk and pyqwk.gui.ttk
    with patch("pyqwk.gui.tk"), \
         patch("pyqwk.gui.ttk") as mock_ttk, \
         patch("pyqwk.gui.font"):

        # Track scrollbar instances and their orients
        scrollbar_instances = []
        def scrollbar_side_effect(*args, **kwargs):
            m = MagicMock()
            m.orient = kwargs.get('orient')
            scrollbar_instances.append(m)
            return m
        mock_ttk.Scrollbar.side_effect = scrollbar_side_effect

        from pyqwk.gui import QwkGuiApp
        import pyqwk.gui

        # Mock some constants that might be needed from pyqwk.gui.tk or pyqwk.gui.ttk
        pyqwk.gui.tk.HORIZONTAL = "horizontal"
        pyqwk.gui.tk.VERTICAL = "vertical"

        root = MagicMock()
        app = QwkGuiApp(root)

        # Check for horizontal scrollbars
        h_scrollbars = [m for m in scrollbar_instances if m.orient == "horizontal"]

        assert len(h_scrollbars) >= 2, f"Expected at least 2 horizontal scrollbars, found {len(h_scrollbars)}"

        # Verify the one gridded at row=1, col=0
        found_gridded = False
        for m in h_scrollbars:
            for call_args in m.grid.call_args_list:
                if call_args.kwargs.get('row') == 1 and call_args.kwargs.get('column') == 0:
                    found_gridded = True
                    assert call_args.kwargs.get('sticky') == "ew"

        assert found_gridded, "Horizontal scrollbar for message list was not gridded at row=1, column=0"
