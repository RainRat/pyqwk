import os
import io
import json
import shutil
import logging
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    matches_filters,
    _cleanup_temp_files,
    _temp_files_to_clean,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
    calculate_archive_stats,
    validate_archive
)

def test_matches_filters_thread_id_non_integer():
    header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="12:00",
        msgto="ToUser", msgfrom="FromUser", msgsubject="Sub", msgpassword="",
        refnum=0, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag=" "
    )
    msg = ParsedMessage(
        text="Body", msgnum=1, refnum=0, confnum=1, header=header
    )
    msg.thread_id = "abc"

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", thread_id_filters={"abc"}
    )
    allowed_confs = {1}
    assert matches_filters(msg, settings, allowed_confs) is True

    settings_no_match = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", thread_id_filters={"xyz"}
    )
    assert matches_filters(msg, settings_no_match, allowed_confs) is False


def test_cleanup_temp_files(tmp_path):
    # Success path for files
    temp_f = tmp_path / "test_temp_file.txt"
    temp_f.write_text("dummy")
    assert temp_f.exists()

    _temp_files_to_clean.append(str(temp_f))

    # Success path for directories
    temp_d = tmp_path / "test_temp_dir"
    temp_d.mkdir()
    (temp_d / "file.txt").write_text("nested")
    assert temp_d.exists()

    _temp_files_to_clean.append(str(temp_d))

    # Clean up
    _cleanup_temp_files()

    assert not temp_f.exists()
    assert not temp_d.exists()

    # Clear list to be clean
    _temp_files_to_clean.clear()


def test_cleanup_temp_files_exception():
    _temp_files_to_clean.append("some_non_existent_path_raising_exception")
    with patch("os.path.exists", side_effect=RuntimeError("Fake disk failure")):
        # Should catch RuntimeError and pass silently
        _cleanup_temp_files()
    _temp_files_to_clean.clear()


def test_process_merged_files_with_progress_bar(tmp_path):
    p = tmp_path / "structured.json"
    p.write_text(json.dumps([
        {
            "header": {
                "status": " ", "msgnum": 1, "msgdate": "01-01-24", "msgtime": "12:00",
                "msgto": "ToUser", "msgfrom": "FromUser", "msgsubject": "Sub", "msgpassword": "",
                "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "
            },
            "text": "Body", "confnum": 1
        }
    ]))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", quiet=False
    )
    logger = logging.getLogger("test_progress_bar")

    with patch("sys.stdout", new_callable=io.StringIO):
        process_merged_files([str(p)], settings, logger)


def test_count_merged_messages_with_progress_bar(tmp_path):
    p = tmp_path / "structured.json"
    p.write_text(json.dumps([
        {
            "header": {
                "status": " ", "msgnum": 1, "msgdate": "01-01-24", "msgtime": "12:00",
                "msgto": "ToUser", "msgfrom": "FromUser", "msgsubject": "Sub", "msgpassword": "",
                "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "
            },
            "text": "Body", "confnum": 1
        }
    ]))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", quiet=False
    )
    logger = logging.getLogger("test_progress_bar")

    with patch("sys.stdout", new_callable=io.StringIO):
        calculate_archive_stats([str(p)], settings, logger)


def test_validate_archive_mbox_eml_markdown(tmp_path):
    logger = logging.getLogger("test_validation")

    p_mbox = tmp_path / "test.mbox"
    p_mbox.write_text("From bob@example.com Mon Jan  1 00:00:00 2024\nSubject: Hi\n\nHello")
    res_mbox = validate_archive(str(p_mbox), logger)
    assert res_mbox["format"] == "mbox"

    p_eml = tmp_path / "test.eml"
    p_eml.write_text("Subject: Hello\n\nWorld")
    res_eml = validate_archive(str(p_eml), logger)
    assert res_eml["format"] == "eml"

    p_md = tmp_path / "test.md"
    p_md.write_text("# Title\nContent")
    res_md = validate_archive(str(p_md), logger)
    assert res_md["format"] == "markdown"

    p_markdown = tmp_path / "test.markdown"
    p_markdown.write_text("# Title\nContent")
    res_markdown = validate_archive(str(p_markdown), logger)
    assert res_markdown["format"] == "markdown"


def test_validate_archive_misaligned_qwk(tmp_path):
    p = tmp_path / "test.qwk"
    p.write_bytes(b"A" * 150)
    logger = logging.getLogger("test_misaligned")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("Block misalignment detected" in err for err in res["errors"])


def test_validate_archive_qwk_corruption(tmp_path):
    p = tmp_path / "corrupt.qwk"
    p.write_bytes(b"A" * 128)
    logger = logging.getLogger("test_qwk_corruption")
    with patch("pyqwk.core.parse_messages", side_effect=ValueError("Invalid parse")):
        res = validate_archive(str(p), logger)
        assert res["valid"] is False
        assert any("Binary corruption or format error during QWK parsing" in err for err in res["errors"])


def test_validate_archive_json_single_dict(tmp_path):
    p = tmp_path / "single_msg.json"
    p.write_text(json.dumps({
        "header": {
            "status": " ", "msgnum": 1, "msgdate": "01-01-24", "msgtime": "12:00",
            "msgto": "ToUser", "msgfrom": "FromUser", "msgsubject": "Sub", "msgpassword": "",
            "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "
        },
        "text": "Body", "confnum": 1
    }))
    logger = logging.getLogger("test_single_dict")
    res = validate_archive(str(p), logger)
    assert res["valid"] is True
    assert res["messages_count"] == 1


def test_validate_archive_sqlite_missing_messages_table(tmp_path):
    p = tmp_path / "test.db"
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.close()

    logger = logging.getLogger("test_sqlite")
    res = validate_archive(str(p), logger)
    assert res["valid"] is False
    assert any("SQLite database is missing the required 'messages' table." in err for err in res["errors"])


def test_validate_archive_metadata_warnings_msgnum(tmp_path):
    p = tmp_path / "msg_warnings.json"
    p.write_text(json.dumps([
        {
            "header": {
                "status": " ", "msgnum": None, "msgdate": "01-01-24", "msgtime": "12:00",
                "msgto": "ToUser", "msgfrom": "FromUser", "msgsubject": "Sub", "msgpassword": "",
                "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "
            },
            "text": "Body", "confnum": 1
        },
        {
            "header": {
                "status": " ", "msgnum": -10, "msgdate": "01-01-24", "msgtime": "12:00",
                "msgto": "ToUser", "msgfrom": "FromUser", "msgsubject": "Sub", "msgpassword": "",
                "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "
            },
            "text": "Body", "confnum": 1
        }
    ]))
    logger = logging.getLogger("test_msgnum")
    res = validate_archive(str(p), logger)
    assert any("is missing message number" in w for w in res["warnings"])
    assert any("has invalid/non-positive message number" in w for w in res["warnings"])


def test_validate_archive_tar_extract_without_data_filter(tmp_path):
    import tarfile
    p = tmp_path / "test_batch.tar"
    sub_f = tmp_path / "msg.json"
    sub_f.write_text(json.dumps([
        {
            "header": {
                "status": " ", "msgnum": 1, "msgdate": "01-01-24", "msgtime": "12:00",
                "msgto": "ToUser", "msgfrom": "FromUser", "msgsubject": "Sub", "msgpassword": "",
                "refnum": 0, "numblocks": 1, "msgflag": " ", "confnum": 1, "lognum": 0, "nettag": " "
            },
            "text": "Body", "confnum": 1
        }
    ]))
    with tarfile.open(p, "w") as tar:
        tar.add(sub_f, arcname="msg.json")

    class FakeTarfileModule:
        def __getattr__(self, name):
            if name == "data_filter":
                raise AttributeError()
            return getattr(tarfile, name)
        open = tarfile.open

    logger = logging.getLogger("test_tar_filter")
    with patch("pyqwk.core.tarfile", FakeTarfileModule()):
        res = validate_archive(str(p), logger)
        assert res["valid"] is True


def test_gui_block_text_input_alt_left():
    from pyqwk.gui import QwkGuiApp
    app = MagicMock()

    event = MagicMock()
    event.keysym = "Left"
    event.state = MagicMock()
    event.state.__str__.return_value = "alt"

    res = QwkGuiApp._block_text_input(app, event)
    assert res == "break"
    app.go_back.assert_called_once()


def test_gui_is_entry_widget_type_and_error_handling():
    from pyqwk.gui import QwkGuiApp
    class DummyApp:
        search_entry = object()
        exclude_entry = object()
        min_words_entry = object()
        max_words_entry = object()
    app = DummyApp()

    class DummyTkEntry:
        pass
    widget_tk = DummyTkEntry()
    with patch("pyqwk.gui.tk") as mock_tk, patch("pyqwk.gui.ttk") as mock_ttk:
        mock_tk.Entry = DummyTkEntry
        mock_ttk.Entry = object
        assert QwkGuiApp._is_entry_widget(app, widget_tk) is True

    with patch("pyqwk.gui.tk") as mock_tk, patch("pyqwk.gui.ttk") as mock_ttk:
        mock_tk.Entry = 42
        mock_ttk.Entry = 42
        assert QwkGuiApp._is_entry_widget(app, widget_tk) is False

    class ExceptionWidget:
        def winfo_class(self):
            raise RuntimeError("winfo error")

    widget_exc = ExceptionWidget()
    class AnotherDummy:
        pass
    with patch("pyqwk.gui.tk") as mock_tk, patch("pyqwk.gui.ttk") as mock_ttk:
        mock_tk.Entry = AnotherDummy
        mock_ttk.Entry = AnotherDummy
        assert QwkGuiApp._is_entry_widget(app, widget_exc) is False

    class EntryWidget:
        def winfo_class(self):
            return "Entry"

    widget_entry = EntryWidget()
    with patch("pyqwk.gui.tk") as mock_tk, patch("pyqwk.gui.ttk") as mock_ttk:
        mock_tk.Entry = AnotherDummy
        mock_ttk.Entry = AnotherDummy
        assert QwkGuiApp._is_entry_widget(app, widget_entry) is True


def test_gui_update_history_ui_exception():
    from pyqwk.gui import QwkGuiApp
    app = MagicMock()
    app._history_stack = [1, 2]
    app.edit_menu.entryconfig.side_effect = RuntimeError("menu error")

    QwkGuiApp._update_history_ui(app)
    app.edit_menu.entryconfig.assert_called_once()


def test_gui_jump_to_referenced_message_errors():
    from pyqwk.gui import QwkGuiApp
    app = MagicMock()

    app.message_list.selection.return_value = []
    QwkGuiApp.jump_to_referenced_message(app)

    app.message_list.selection.return_value = ["abc"]
    QwkGuiApp.jump_to_referenced_message(app)


def test_gui_sort_column_replies():
    from pyqwk.gui import QwkGuiApp
    app = MagicMock()
    msg = MagicMock()
    msg.reply_count = 42
    app.messages = {1: msg}
    app.message_list.get_children.return_value = ["1"]

    QwkGuiApp.sort_column(app, "Replies", False)
    app.message_list.get_children.assert_called_once()
