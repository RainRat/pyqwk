import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, _generate_safe_filename

@pytest.fixture
def base_message():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="01-20-24",
        msgtime="14:30",
        msgto="Recipient Name",
        msgfrom="Author Name",
        msgsubject="Test Subject!",
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text="Hello world",
        msgnum=123,
        refnum=None,
        confnum=1,
        header=header,
        confname="General Chat",
        bbs_name="The BBS",
        bbs_id="THEBBS"
    )

@pytest.fixture
def settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format='text',
        separator='auto',
        output_mode='file',
        output_path='output/',
        encoding='cp437'
    )

def test_generate_safe_filename_default(base_message, settings):
    filename = _generate_safe_filename(base_message, settings, 1)
    assert filename == "001-00123-test_subject.txt"

def test_generate_safe_filename_custom_pattern(base_message, settings):
    settings.filename_pattern = "{date}_{author}_{subject}"
    filename = _generate_safe_filename(base_message, settings, 1)
    # _slugify(01-20-24) -> 01_20_24
    # _slugify(Author Name) -> author_name
    # _slugify(Test Subject!) -> test_subject
    assert filename == "01_20_24_author_name_test_subject.txt"

def test_generate_safe_filename_pattern_with_msgnum(base_message, settings):
    settings.filename_pattern = "msg_{msgnum}_{confname}"
    filename = _generate_safe_filename(base_message, settings, 1)
    assert filename == "msg_123_general_chat.txt"

def test_generate_safe_filename_invalid_pattern_fallback(base_message, settings):
    settings.filename_pattern = "{invalid_var}_{subject}"
    filename = _generate_safe_filename(base_message, settings, 1)
    # Should fall back to default
    assert filename == "001-00123-test_subject.txt"

def test_generate_safe_filename_sanitization(base_message, settings):
    settings.filename_pattern = "{author}/../../{subject}"
    filename = _generate_safe_filename(base_message, settings, 1)
    # mapping will slugify author and subject
    # author_name_.._.._test_subject.txt
    # re.sub(r'[^\w\-.]', '_', filename) will replace / with _
    assert ".." in filename
    assert "/" not in filename

def test_generate_safe_filename_different_format(base_message, settings):
    settings.format = 'json'
    settings.filename_pattern = "{msgnum}_{subject}"
    filename = _generate_safe_filename(base_message, settings, 1)
    assert filename == "123_test_subject.json"

def test_generate_safe_filename_missing_metadata(base_message, settings):
    base_message.confname = None
    base_message.bbs_name = None
    settings.filename_pattern = "{confname}_{bbs_name}"
    filename = _generate_safe_filename(base_message, settings, 1)
    assert filename == "conf_1_bbs.txt"
