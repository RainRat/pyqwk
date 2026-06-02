import logging
from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
        verbose=False,
        private=True,
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
        regex=False,
        dry_run=False,
        strip_ansi=False,
        quiet=True,
        headers_only=False,
        merge=False,
        unique=False,
        organize=False,
        organize_by_date=False,
        organize_by_bbs=False,
        organize_by_author=False,
        organize_by_to=False,
        organize_by_subject=False,
        include_toc=False,
        extract_attachments=True,
        organize_attachments=True,
        msgnum_filters=None,
        search_term=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_attachment_organization_empty_subpath(tmp_path, monkeypatch):
    """Test organize_attachments when no organization criteria are met (Covers lines 3112 and 3282)."""
    logger = logging.getLogger("test")

    # Message with attachment
    uue_content = "begin 644 file.txt\n#0V%T\n`\nend\n"
    header = MessageHeader(" ", 1, "01-01-24", "12:00", "All", "From", "Sub", "", None, 1, " ", 1, 1, "")
    msg = ParsedMessage(uue_content, 1, None, 1, header)

    monkeypatch.setattr("pyqwk.core.load_data", lambda p, l, e: ([msg], {1: "Conf"}))

    # 1. Test line 3112 (non-individual files)
    output_path = tmp_path / "merged.txt"
    settings = _make_settings(
        output_mode="file",
        output_path=str(output_path),
        extract_attachments=True,
        organize_attachments=True,
        # Ensure all organization flags are False
        organize=False,
        organize_by_bbs=False,
        organize_by_author=False,
        organize_by_to=False,
        organize_by_subject=False,
        organize_by_date=False
    )

    process_merged_files(["dummy.qwk"], settings, logger)

    # Check that attachment is in the base 'attachments' directory
    attach_dir = tmp_path / "attachments"
    assert attach_dir.exists()
    assert (attach_dir / "file.txt").exists()

    # 2. Test line 3282 (individual files)
    output_dir = tmp_path / "out"
    settings_ind = _make_settings(
        individual_files=True,
        output_mode="file",
        output_path=str(output_dir),
        format="html",
        extract_attachments=True,
        organize_attachments=True,
        organize=False,
        organize_by_bbs=False,
        organize_by_author=False,
        organize_by_to=False,
        organize_by_subject=False,
        organize_by_date=False,
        include_toc=False
    )

    process_merged_files(["dummy.qwk"], settings_ind, logger)

    # Verify attachment prefix in HTML doesn't have extra subpath
    msg_html = output_dir / "001-00001-sub.html"
    assert msg_html.exists()
    content = msg_html.read_text()
    # depth is 0 because relative_sub_path is "", so attachment_prefix is "attachments/"
    # Line 3282 was skipped, so it should be just "attachments/"
    assert 'href="attachments/file.txt"' in content
    assert (output_dir / "attachments" / "file.txt").exists()
