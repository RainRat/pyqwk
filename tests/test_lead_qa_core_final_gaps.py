import logging
import os
from unittest.mock import MagicMock, patch
from pyqwk.core import (
    _parse_json_messages,
    _xml_safe,
    process_merged_files,
    ProcessingSettings,
    ConferenceMap,
    BBSInfo,
    ParsedMessage,
    MessageHeader
)

def _get_default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="none",
        output_path=None,
        encoding="cp437"
    )

def test_parse_json_messages_metadata_filtering():
    # Test dictionary input with type="metadata" (Line 1174)
    data_dict = {"type": "metadata", "some": "info"}
    assert _parse_json_messages(data_dict) == []

    # Test dictionary input with type="qwk_archive" (Line 1172)
    data_qwk = {"type": "qwk_archive", "messages": [{"header": {"msgnum": 1, "confnum": 1}, "text": "Hi"}]}
    msgs_qwk = _parse_json_messages(data_qwk)
    assert len(msgs_qwk) == 1
    assert msgs_qwk[0].msgnum == 1

    # Test single dictionary (Line 1176)
    data_single = {"header": {"msgnum": 2, "confnum": 1}, "text": "Single"}
    msgs_single = _parse_json_messages(data_single)
    assert len(msgs_single) == 1
    assert msgs_single[0].msgnum == 2

    # Test list input with "metadata" entry (Line 1180)
    data_list = [
        {"type": "metadata", "info": "header"},
        {"header": {"msgnum": 3, "confnum": 1}, "text": "Hello"}
    ]
    msgs = _parse_json_messages(data_list)
    assert len(msgs) == 1
    assert msgs[0].msgnum == 3

def test_xml_safe_none():
    # Test None input for _xml_safe (Line 3882)
    assert _xml_safe(None) == ""
    assert _xml_safe("test") == "test"

def test_process_merged_files_conference_merge(tmp_path):
    # Test merging of conference maps and BBS info (Lines 3530, 3532)
    archive1 = str(tmp_path / "archive1.zip")
    archive2 = str(tmp_path / "archive2.zip")

    bbs2 = BBSInfo(name="BBS2", bbs_id="ID2", user_name="User2")

    cm1 = ConferenceMap({1: "Conf1"})
    cm2 = ConferenceMap({2: "Conf2"})
    cm2.bbs_info = bbs2

    settings = _get_default_settings()
    settings.merge = True

    logger = logging.getLogger("test")

    # We patch ConferenceMap to capture the instances created in process_merged_files
    created_maps = []
    original_cm_init = ConferenceMap.__init__

    def mocked_cm_init(self, *args, **kwargs):
        original_cm_init(self, *args, **kwargs)
        created_maps.append(self)

    with patch.object(ConferenceMap, '__init__', autospec=True, side_effect=mocked_cm_init):
        def mock_load_data(path, logger, encoding):
            if "archive1" in path:
                return ([], cm1)
            else:
                return ([], cm2)

        with patch("pyqwk.core.load_data", side_effect=mock_load_data):
            process_merged_files([archive1, archive2], settings, logger)

            # Line 3525: board_dict_to_use = ConferenceMap(board_dict)
            # This creates a NEW ConferenceMap containing entries from cm1.
            assert len(created_maps) >= 1
            merged_map = created_maps[0]
            assert 1 in merged_map
            assert 2 in merged_map
            assert merged_map.bbs_info == bbs2

def test_process_merged_files_limit_re_scan(tmp_path):
    # Test handle_output returns True (Line 3235)
    archive = str(tmp_path / "archive.zip")
    h1 = MessageHeader(" ", 1, "01-01-23", "10:00", "All", "From", "Sub", "", None, 1, " ", 1, 1, "")
    msg1 = ParsedMessage("Text1", 1, None, 1, h1)
    h2 = MessageHeader(" ", 2, "01-01-23", "10:05", "All", "From", "Sub", "", None, 1, " ", 1, 1, "")
    msg2 = ParsedMessage("Text2", 2, None, 1, h2)
    cm = ConferenceMap({1: "Conf1"})

    settings = _get_default_settings()
    settings.limit = 1
    settings.output_mode = "stdout"

    logger = logging.getLogger("test")

    with patch("pyqwk.core.load_data", return_value=([msg1, msg2], cm)):
        with patch("sys.stdout.write") as mock_stdout:
            process_merged_files([archive], settings, logger)

            output = "".join(call.args[0] for call in mock_stdout.call_args_list)
            assert "Text1" in output
            assert "Text2" not in output

def test_process_merged_files_no_msgnum(tmp_path):
    # Hit line 3146: msg_num = message.msgnum if message.msgnum is not None else count
    archive = str(tmp_path / "archive.zip")
    h1 = MessageHeader(" ", None, "01-01-23", "10:00", "All", "From", "Sub", "", None, 1, " ", 1, 1, "")
    msg1 = ParsedMessage("Text1", None, None, 1, h1)
    cm = ConferenceMap({1: "Conf1"})

    settings = _get_default_settings()
    settings.individual_files = True
    out_dir = tmp_path / "out_no_msgnum"
    settings.output_path = str(out_dir)

    logger = logging.getLogger("test")

    with patch("pyqwk.core.load_data", return_value=([msg1], cm)):
        process_merged_files([archive], settings, logger)

    files = os.listdir(out_dir)
    assert any("001-00001-sub.txt" in f for f in files)
