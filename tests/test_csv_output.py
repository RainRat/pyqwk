import csv
import io
import pytest
from pyqwk.core import _write_csv, MessageHeader, ProcessedMessage

def test_write_csv_output():
    header = MessageHeader(
        status=' ',
        msgnum=1,
        msgdate='01-01-90',
        msgtime='12:00',
        msgto='User',
        msgfrom='Sysop',
        msgsubject='Welcome',
        msgpassword='',
        refnum=None,
        numblocks=1,
        msgflag='',
        confnum=1,
        lognum=1,
        nettag=''
    )
    message = ProcessedMessage(
        text='Hello World',
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        depth=0,
        thread_id='1',
        parent_msgnum=None
    )

    # We mock _write_text_output to capture the output instead of writing to a file
    # But _write_text_output is imported inside qwk, so we need to patch it or just check the result if we mock it.
    # However, since we are testing internal function _write_csv which calls _write_text_output,
    # and _write_text_output writes to stdout if output_path is None.
    # We can capture stdout.

    from unittest.mock import patch

    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_csv([message], None)

        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]

        # Verify CSV content
        f = io.StringIO(content)
        reader = csv.DictReader(f)
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]['msgsubject'] == 'Welcome'
        assert rows[0]['msgfrom'] == 'Sysop'
        assert rows[0]['text'] == 'Hello World'
        assert rows[0]['thread_id'] == '1'
        assert 'conference_name' in rows[0]
        assert 'bbs_name' in rows[0]
        assert 'source_file' in rows[0]

def test_write_csv_empty():
    from unittest.mock import patch
    with patch('pyqwk.core._write_text_output') as mock_write:
        _write_csv([], None)

        mock_write.assert_called_once()
        content = mock_write.call_args[0][0]

        # Verify CSV headers
        f = io.StringIO(content)
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        assert 'msgsubject' in reader.fieldnames
        assert list(reader) == []
