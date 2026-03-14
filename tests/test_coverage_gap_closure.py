import pytest
from unittest.mock import MagicMock, patch
from pyqwk.core import load_data, _write_text, ProcessingSettings, ParsedMessage, MessageHeader, matches_filters
import io

def _make_settings(**kwargs):
    defaults = dict(
        verbose=False, private=False, no_header=False,
        truncate_signatures=False, cut_quoting=False,
        individual_files=False, threaded=False,
        binaries_removal=False, redact_pii=False,
        format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437',
        conferences=None, authors=None, recipients=None, subjects=None,
        search_term=None, after=None, before=None,
        regex=False, dry_run=False, strip_ansi=False,
        quiet=False, headers_only=False, oneline=False,
        extract_attachments=False, limit=None, skip=None,
        sort=None, reverse=False, merge=False, unique=False, organize=False,
        organize_by_bbs=False, include_toc=False,
        has_attachments=False, mine=False, on_this_day=False, reference_date=None
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)

def test_load_data_mbox_error():
    # Lines 1061-1062
    with patch('pyqwk.core._parse_mbox_messages') as mock_parse:
        mock_parse.side_effect = Exception("Mock mbox error")
        with pytest.raises(ValueError, match="Failed to load mbox archive: Mock mbox error"):
            load_data("test.mbox", MagicMock())

def test_load_data_eml_error():
    # Lines 1070-1071
    with patch('pyqwk.core._parse_eml_messages') as mock_parse:
        mock_parse.side_effect = Exception("Mock eml error")
        with pytest.raises(ValueError, match="Failed to load EML file: Mock eml error"):
            load_data("test.eml", MagicMock())

def test_write_text_toc_colors():
    # Line 2706 (TOC separator color)
    settings = _make_settings(include_toc=True)
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='ToUser', msgfrom='FromUser', msgsubject='Subj', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    msg = ParsedMessage(text="body", msgnum=1, refnum=None, confnum=1, header=header, confname="General")

    with patch('pyqwk.core.sys.stdout', new=io.StringIO()) as mock_stdout:
        mock_stdout.isatty = MagicMock(return_value=True)
        _write_text([msg], None, settings=settings)
        output = mock_stdout.getvalue()
        assert "\x1b[90m" in output

def test_cli_main_version():
    with patch('sys.argv', ['qwk', '--version']):
        with pytest.raises(SystemExit) as e:
            from pyqwk.cli import main
            main()
        assert e.value.code == 0

def test_any_match_empty_patterns():
    # Line 1560: if not patterns: return True
    # By removing the 'if settings.authors and' check in matches_filters,
    # we can now hit the 'if not patterns' branch in any_match
    # by passing an empty list (which is the default).
    settings = _make_settings(authors=[])
    header = MessageHeader(
        status=' ', msgnum=1, msgdate='01-01-23', msgtime='12:00',
        msgto='ToUser', msgfrom='FromUser', msgsubject='Subj', msgpassword='',
        refnum=None, numblocks=1, msgflag='', confnum=1, lognum=1, nettag=''
    )
    msg = ParsedMessage(text="body", msgnum=1, refnum=None, confnum=1, header=header)
    assert matches_filters(msg, settings, set()) == True
