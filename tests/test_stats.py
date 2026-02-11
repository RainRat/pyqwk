import pytest
import logging
import json
from pyqwk.core import ProcessingSettings, show_stats

def test_show_stats_basic(capsys):
    input_path = "testdata/test1_qwk.zip"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )
    logger = logging.getLogger("test")

    show_stats([input_path], settings, logger)

    captured = capsys.readouterr()
    assert "Statistics for:" in captured.out
    assert "Messages: 1 matching / 1 total" in captured.out
    assert "Warren Zatwarniski" in captured.out

def test_show_stats_json(capsys):
    input_path = "testdata/test1_qwk.zip"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='json',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True
    )
    logger = logging.getLogger("test")

    show_stats([input_path], settings, logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["total_messages"] == 1
    assert data[0]["authors"][0]["name"] == "Warren Zatwarniski"

def test_show_stats_filter(capsys):
    input_path = "testdata/test2_qwk.zip"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        strip_ansi=False,
        format='text',
        separator='auto',
        output_mode='stdout',
        output_path=None,
        encoding='cp437',
        quiet=True,
        authors=["Russ"]
    )
    logger = logging.getLogger("test")

    show_stats([input_path], settings, logger)

    captured = capsys.readouterr()
    assert "Messages: 1 matching / 2 total" in captured.out
    assert "Russ Beuker" in captured.out
    assert "Chris Exner" not in captured.out
