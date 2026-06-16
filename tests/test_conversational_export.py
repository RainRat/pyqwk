import os
import tempfile
from pyqwk.core import process_merged_files, ProcessingSettings, ParsedMessage, MessageHeader, ConferenceMap

def test_threaded_individual_files_export():
    # Setup some test messages with reply relationships
    h1 = MessageHeader(status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
                       msgto="All", msgfrom="Alice", msgsubject="Hello", msgpassword="",
                       refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag="")
    m1 = ParsedMessage(text="First post", msgnum=1, refnum=None, confnum=1, header=h1)

    h2 = MessageHeader(status=" ", msgnum=2, msgdate="01-01-23", msgtime="12:05",
                       msgto="Alice", msgfrom="Bob", msgsubject="Re: Hello", msgpassword="",
                       refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag="")
    m2 = ParsedMessage(text="First reply", msgnum=2, refnum=1, confnum=1, header=h2)

    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = ProcessingSettings(
            verbose=False, private=True, no_header=False,
            truncate_signatures=False, cut_quoting=False,
            individual_files=True, threaded=True,
            binaries_removal=False, redact_pii=False,
            format="html", separator="none",
            output_mode="file", output_path=tmp_dir,
            encoding="utf-8", quiet=True
        )

        import pyqwk.core
        from unittest.mock import patch

        with patch("pyqwk.core.load_data") as mock_load:
            bd = ConferenceMap({1: "General"})
            mock_load.return_value = ([m1, m2], bd)

            from logging import getLogger
            process_merged_files(["dummy.qwk"], settings, getLogger("test"))

        # Verify files were created
        files = os.listdir(tmp_dir)
        assert "index.html" in files

        # Check index content for indentation
        with open(os.path.join(tmp_dir, "index.html"), "r") as f:
            index_content = f.read()
            # Bob's reply should be indented (depth 1)
            assert "└&nbsp;<a" in index_content

def test_new_template_variables():
    h = MessageHeader(status=" ", msgnum=1, msgdate="01-01-23", msgtime="12:00",
                      msgto="All", msgfrom="Alice", msgsubject="Link test", msgpassword="",
                      refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=0, nettag="")
    # Message with url, email, and phone
    text = "Check http://example.com or mail alice@example.com or call 555-1234"
    m = ParsedMessage(text=text, msgnum=1, refnum=None, confnum=1, header=h)
    m.thread_id = "T1"
    m.parent_msgnum = 0
    m.depth = 1

    from pyqwk.core import _get_message_mapping
    mapping = _get_message_mapping(m, 1)

    assert mapping["urls"] == "http://example.com"
    assert mapping["emails"] == "alice@example.com"
    assert mapping["phones"] == "555-1234"
    assert mapping["thread_id"] == "T1"
    assert mapping["parent_msgnum"] == 0
    assert mapping["depth"] == 1
