import json
from unittest.mock import MagicMock
from pyqwk.core import show_stats, ProcessingSettings, ParsedMessage, MessageHeader, ConferenceMap

def test_stats_enhanced_keywords(capsys):
    # Setup mock data
    msg1 = ParsedMessage(
        text="Hello world, this is a test message about Bulletin Board Systems. BBS are cool.",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-90", msgtime="12:00",
            msgto="All", msgfrom="Sysop", msgsubject="Welcome",
            msgpassword="", refnum=None, numblocks=1, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )
    )

    msg2 = ParsedMessage(
        text="The Bulletin Board System (BBS) was popular in the 80s and 90s.",
        msgnum=2,
        refnum=None,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=2, msgdate="01-01-90", msgtime="13:00",
            msgto="All", msgfrom="User", msgsubject="History",
            msgpassword="", refnum=None, numblocks=1, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )
    )

    # Mock load_data to return our pre-parsed messages
    mock_logger = MagicMock()
    board_dict = ConferenceMap({1: "General"})

    import pyqwk.core
    original_load_data = pyqwk.core.load_data
    pyqwk.core.load_data = MagicMock(return_value=([msg1, msg2], board_dict))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format='json',
        separator='none', output_mode='stdout', output_path=None,
        encoding='cp437', quiet=True
    )

    try:
        show_stats(["mock.qwk"], settings, mock_logger)
        captured = capsys.readouterr()

        # Parse JSON output
        stats = json.loads(captured.out)

        assert len(stats) == 1
        entry = stats[0]

        # Verify keywords
        keywords = {kw['word']: kw['count'] for kw in entry['keywords']}
        assert 'bulletin' in keywords
        assert 'board' in keywords
        assert 'system' in keywords
        assert keywords['bulletin'] >= 2

        # Verify subjects
        subjects = {s['subject']: s['count'] for s in entry['subjects']}
        assert 'welcome' in subjects
        assert 'history' in subjects

    finally:
        pyqwk.core.load_data = original_load_data

def test_stats_enhanced_terminal_output(capsys):
    # Similar setup but for text format to check labels
    msg = ParsedMessage(
        text="Electronic mail is fast.",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=MessageHeader(
            status=" ", msgnum=1, msgdate="01-01-90", msgtime="12:00",
            msgto="All", msgfrom="Sysop", msgsubject="Email",
            msgpassword="", refnum=None, numblocks=1, msgflag=" ",
            confnum=1, lognum=1, nettag=""
        )
    )

    mock_logger = MagicMock()
    board_dict = ConferenceMap({1: "General"})

    import pyqwk.core
    original_load_data = pyqwk.core.load_data
    pyqwk.core.load_data = MagicMock(return_value=([msg], board_dict))

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False, format='text',
        separator='none', output_mode='stdout', output_path=None,
        encoding='cp437', quiet=True
    )

    try:
        show_stats(["mock.qwk"], settings, mock_logger)
        captured = capsys.readouterr()

        assert "Top Subjects:" in captured.out
        assert "Top Keywords:" in captured.out
        assert "electronic" in captured.out.lower()
        assert "mail" in captured.out.lower()

    finally:
        pyqwk.core.load_data = original_load_data
