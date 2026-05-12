import pytest
from pyqwk.core import (
    ProcessingSettings,
    matches_filters,
    ParsedMessage,
    MessageHeader,
    _get_message_mapping,
    _serialize_control_dat,
    BBSInfo,
    ConferenceMap,
)

def _make_message(msgfrom="User", msgto="All"):
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject="Test",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )
    return ParsedMessage(text="Hello", msgnum=1, refnum=None, confnum=1, header=header)

def test_my_name_filter():
    """Test that settings.my_name correctly influences the --mine filter."""
    msg = _make_message(msgfrom="Alice")

    # settings.mine is True, but no user_name provided to matches_filters.
    # Currently, it returns True because the filter is skipped if user_name is None.
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format="text",
        separator="none", output_mode="stdout", output_path=None,
        encoding="cp437", mine=True, my_name="Alice"
    )

    # In process_merged_files, user_name is determined from settings.my_name or metadata.
    # Here we simulate that determination.
    user_name = settings.my_name
    assert matches_filters(msg, settings, set(), user_name=user_name)

    # Test mismatch
    assert not matches_filters(msg, settings, set(), user_name="Bob")

def test_my_name_pattern_variable():
    """Test that {my_name} is available in message mapping."""
    msg = _make_message(msgfrom="Bob")
    mapping = _get_message_mapping(msg, 1)
    assert mapping["my_name"] == "Bob"

    # Test with custom pattern (implicitly tested via mapping existence)
    assert "Bob" in "{my_name}".format(**mapping)

def test_my_name_qwk_serialization():
    """Test that settings.my_name is used in CONTROL.DAT serialization."""
    bbs_info = BBSInfo(user_name="Original")
    board_dict = ConferenceMap()

    # Without override
    lines = _serialize_control_dat(bbs_info, board_dict)
    assert lines[6] == b"Original"

    # With override
    lines = _serialize_control_dat(bbs_info, board_dict, my_name="NewName")
    assert lines[6] == b"NewName"

def test_gui_mine_logic(mocker):
    """Test that QwkGuiApp uses my_name for its internal logic."""
    import sys
    from unittest.mock import MagicMock

    # Mock tkinter components
    mock_tk = MagicMock()
    mocker.patch.dict("sys.modules", {
        "tkinter": mock_tk,
        "tkinter.font": MagicMock(),
        "tkinter.ttk": MagicMock(),
        "tkinter.filedialog": MagicMock(),
        "tkinter.messagebox": MagicMock(),
        "tkinter.simpledialog": MagicMock(),
    })

    # Ensure variables don't crash
    mock_tk.BooleanVar.return_value = MagicMock()
    mock_tk.StringVar.return_value = MagicMock()
    mock_tk.IntVar.return_value = MagicMock()

    from pyqwk.gui import QwkGuiApp

    root = MagicMock()
    app = QwkGuiApp(root, my_name="Alice")

    assert app.my_name == "Alice"

    # Verify it passes it to settings
    settings = app._current_settings()
    assert settings.my_name == "Alice"
