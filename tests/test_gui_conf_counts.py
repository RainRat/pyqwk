import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import ParsedMessage, MessageHeader

# Re-use setup from test_gui if possible, but for simplicity we'll do a quick mock here
# since we only need to test load_messages and counts.


@pytest.fixture
def mock_gui_deps():
    with (
        patch("pyqwk.gui.tk") as mock_tk,
        patch("pyqwk.gui.ttk") as mock_ttk,
        patch("pyqwk.gui.filedialog") as mock_fd,
        patch("pyqwk.gui.messagebox") as mock_mb,
    ):

        def make_var(value=None):
            m = MagicMock()
            m.get.return_value = value
            return m

        mock_tk.BooleanVar.side_effect = lambda value=False, **kwargs: make_var(value)
        mock_tk.StringVar.side_effect = lambda value="", **kwargs: make_var(value)
        mock_tk.IntVar.side_effect = lambda value=0, **kwargs: make_var(value)

        yield {"tk": mock_tk, "ttk": mock_ttk, "combo": mock_ttk.Combobox.return_value}


def test_gui_conference_counts(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp

    root = MagicMock()
    app = QwkGuiApp(root)

    # Mock data
    h1 = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    h2 = MessageHeader(
        " ", 2, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 2, 2, ""
    )
    h3 = MessageHeader(
        "*", 3, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 3, ""
    )  # Private

    msgs = [
        ParsedMessage("M1", 1, None, 1, h1),
        ParsedMessage("M2", 2, None, 2, h2),
        ParsedMessage("M3", 3, None, 1, h3),
    ]

    mock_board_dict = {1: "General", 2: "Tech"}

    with (
        patch("pyqwk.gui.load_data", return_value=(bytearray(), mock_board_dict)),
        patch("pyqwk.gui.parse_messages", return_value=msgs),
        patch("pyqwk.gui.process_message", side_effect=lambda t, *args: t),
        patch.object(app, "on_message_selected"),
    ):
        # 1. Test with Private=True (default in init)
        app.private_var.get.return_value = True
        app.load_messages("test.qwk")

        # All Conferences (3), General (2), Tech (1)
        expected_values = ["All Conferences (3)", "1: General (2)", "2: Tech (1)"]
        mock_gui_deps["combo"].__setitem__.assert_any_call("values", expected_values)

        # 2. Test with Private=False
        app.private_var.get.return_value = False
        app.load_messages("test.qwk")

        # All Conferences (2), General (1), Tech (1)
        expected_values_no_private = [
            "All Conferences (2)",
            "1: General (1)",
            "2: Tech (1)",
        ]
        mock_gui_deps["combo"].__setitem__.assert_any_call(
            "values", expected_values_no_private
        )


def test_gui_selection_preservation(mock_gui_deps):
    from pyqwk.gui import QwkGuiApp

    root = MagicMock()
    app = QwkGuiApp(root)

    h1 = MessageHeader(
        " ", 1, "01-01-90", "12:00", "To", "From", "Sub", "", None, 1, " ", 1, 1, ""
    )
    msgs = [ParsedMessage("M1", 1, None, 1, h1)]
    mock_board_dict = {1: "General"}

    with (
        patch("pyqwk.gui.load_data", return_value=(bytearray(), mock_board_dict)),
        patch("pyqwk.gui.parse_messages", return_value=msgs),
        patch("pyqwk.gui.process_message", side_effect=lambda t, *args: t),
        patch.object(app, "on_message_selected"),
    ):
        # Initial load
        app.load_messages("test.qwk")
        mock_gui_deps["combo"].set.assert_called_with("All Conferences (1)")

        # Select "General"
        app.conf_combo.get.return_value = "1: General (1)"
        app.load_messages("test.qwk")  # Reload (e.g. toggled a filter)

        # Should preserve selection
        mock_gui_deps["combo"].set.assert_called_with("1: General (1)")
