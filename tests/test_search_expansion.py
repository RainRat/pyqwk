import pytest
from pyqwk.core import ParsedMessage, MessageHeader, ProcessingSettings, matches_filters


@pytest.fixture
def base_header():
    return MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Author",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag="",
    )


@pytest.fixture
def base_settings():
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
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        search_term=None,
    )


def test_search_confname(base_header, base_settings):
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=base_header,
        confname="Vintage Computing",
    )
    base_settings.search_term = "vintage"
    assert matches_filters(msg, base_settings, set()) is True

    base_settings.search_term = "modern"
    assert matches_filters(msg, base_settings, set()) is False


def test_search_bbs_info(base_header, base_settings):
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=base_header,
        bbs_name="The Digital Orbit",
        bbs_id="DIGITAL",
    )
    base_settings.search_term = "orbit"
    assert matches_filters(msg, base_settings, set()) is True

    base_settings.search_term = "digital"
    assert matches_filters(msg, base_settings, set()) is True


def test_search_source_file(base_header, base_settings):
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=base_header,
        source_file="archive_2023.qwk",
    )
    base_settings.search_term = "2023"
    assert matches_filters(msg, base_settings, set()) is True


def test_search_attachments(base_header, base_settings):
    # Test searching in explicitly provided attachments
    msg = ParsedMessage(
        text="Hello world",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=base_header,
        attachments=["image.gif", "data.zip"],
    )
    base_settings.search_term = "gif"
    assert matches_filters(msg, base_settings, set()) is True


def test_search_extracted_attachments(base_header, base_settings):
    # Test that attachments are extracted and searched if not present
    uue_text = 'Hello\r\nbegin 644 secret.txt\r\nM"@H*      \r\n`\r\nend\r\n'
    msg = ParsedMessage(
        text=uue_text,
        msgnum=1,
        refnum=None,
        confnum=1,
        header=base_header,
        attachments=None,
    )
    base_settings.search_term = "secret"
    assert matches_filters(msg, base_settings, set()) is True
    assert msg.attachments == ["secret.txt"]
