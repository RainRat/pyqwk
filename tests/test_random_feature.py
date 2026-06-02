import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import ProcessingSettings, process_merged_files
from pyqwk.gui import QwkGuiApp

def test_cli_random_sort(tmp_path, capsys):
    # Create a small set of messages in a JSON format for easy loading
    import json
    messages_data = [
        {"msgnum": i, "confnum": 1, "from": f"User{i}", "to": "All", "date": "01-01-24", "time": "12:00", "subject": f"Subj{i}", "text": f"Body{i}"}
        for i in range(1, 21)
    ]
    input_file = tmp_path / "test.json"
    with open(input_file, "w") as f:
        json.dump(messages_data, f)

    # Base settings with random sort
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        sort="random",
        quiet=True
    )

    logger = MagicMock()

    with patch("sys.stdout", new_callable=pytest.importorskip("io").StringIO) as mock_stdout:
        process_merged_files([str(input_file)], settings, logger)
        output = mock_stdout.getvalue()

    lines = [line for line in output.splitlines() if line.strip()]
    bodies = [line.strip() for line in lines]

    assert len(bodies) == 20
    default_order = [f"Body{i}" for i in range(1, 21)]
    assert bodies != default_order

def test_gui_random_message():
    # Mocking Tk and root to avoid TclError
    with patch("tkinter.Tk"), patch("tkinter.ttk.Style"), patch("tkinter.font.Font"):
        root = MagicMock()
        # Mocking QwkGuiApp's __init__ to avoid building the whole UI
        with patch.object(QwkGuiApp, "__init__", return_value=None):
            app = QwkGuiApp(root)
            app.message_list = MagicMock()
            app._get_all_tree_items = MagicMock(return_value=["0", "1", "2", "3", "4"])

            with patch("random.choice", return_value="3"):
                app._select_random_message()

            app.message_list.selection_set.assert_called_once_with("3")
            app.message_list.see.assert_called_once_with("3")
            app.message_list.focus.assert_called_once_with("3")
