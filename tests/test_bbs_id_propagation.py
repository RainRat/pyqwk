import logging
import json
from unittest.mock import patch
from pyqwk.core import (
    ProcessingSettings,
    process_merged_files,
    ParsedMessage,
    MessageHeader,
    ConferenceMap,
    BBSInfo
)

def test_bbs_id_propagation_in_process_merged_files(tmp_path):
    """Verify that BBS ID is correctly propagated to messages during processing."""
    logger = logging.getLogger("test_bbs_id")
    output_path = tmp_path / "output.json"

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='json', separator='none', output_mode='file',
        output_path=str(output_path), encoding='cp437'
    )

    # Mock BBS info with an ID
    bbs_info = BBSInfo(name="Test BBS", bbs_id="TEST_BBS_ID")
    board_dict = ConferenceMap()
    board_dict.bbs_info = bbs_info

    # Mock a single message
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-24', msgtime='12:00',
        msgto='ToUser', msgfrom='FromUser', msgsubject='Subject',
        msgpassword='', refnum=None, numblocks=1, msgflag=' ',
        confnum=1, lognum=0, nettag=''
    )
    message = ParsedMessage(
        text="Hello world", msgnum=1, refnum=None, confnum=1, header=header
    )

    with patch('pyqwk.core.load_data') as mock_load_data, \
         patch('pyqwk.core.parse_messages') as mock_parse_messages:

        mock_load_data.return_value = (bytearray(128), board_dict)
        mock_parse_messages.return_value = iter([message])

        process_merged_files(['dummy.qwk'], settings, logger)

    assert output_path.exists()
    with open(output_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]['bbs_name'] == "Test BBS"
        assert data[0]['bbs_id'] == "TEST_BBS_ID"
        assert data[0]['text'] == "Hello world\r\n"
