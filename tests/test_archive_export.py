import os
import zipfile
import tarfile
import logging
import tempfile
from pyqwk.core import ProcessingSettings, process_merged_files, load_data

def test_archive_export_zip(tmp_path):
    # Setup test file from testdata
    input_archive = "testdata/test1_qwk.zip"
    output_zip = os.path.join(tmp_path, "export.zip")

    logger = logging.getLogger("test")

    # Define settings for individual HTML files exported into a ZIP archive
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="auto",
        output_mode="file",
        output_path=output_zip,
        encoding="cp437",
    )

    process_merged_files([input_archive], settings, logger)

    assert os.path.exists(output_zip)
    assert zipfile.is_zipfile(output_zip)

    # Inspect the exported ZIP contents
    with zipfile.ZipFile(output_zip, "r") as zf:
        namelist = zf.namelist()
        assert "index.html" in namelist
        # Check that we have individual message HTML files
        html_files = [f for f in namelist if f.endswith(".html")]
        assert len(html_files) > 1


def test_archive_export_tar_gz(tmp_path):
    input_archive = "testdata/test1_qwk.zip"
    output_tar = os.path.join(tmp_path, "export.tar.gz")

    logger = logging.getLogger("test")

    # Define settings for individual Markdown files exported into a tar.gz archive
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="markdown",
        separator="auto",
        output_mode="file",
        output_path=output_tar,
        encoding="cp437",
    )

    process_merged_files([input_archive], settings, logger)

    assert os.path.exists(output_tar)
    assert tarfile.is_tarfile(output_tar)

    with tarfile.open(output_tar, "r:gz") as tf:
        names = tf.getnames()
        assert "README.md" in names
        md_files = [n for n in names if n.endswith(".md")]
        assert len(md_files) > 1


def test_archive_export_tar_bz2(tmp_path):
    input_archive = "testdata/test1_qwk.zip"
    output_tar = os.path.join(tmp_path, "export.tar.bz2")

    logger = logging.getLogger("test")

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="markdown",
        separator="auto",
        output_mode="file",
        output_path=output_tar,
        encoding="cp437",
    )

    process_merged_files([input_archive], settings, logger)

    assert os.path.exists(output_tar)
    assert tarfile.is_tarfile(output_tar)

    with tarfile.open(output_tar, "r:bz2") as tf:
        names = tf.getnames()
        assert "README.md" in names
        md_files = [n for n in names if n.endswith(".md")]
        assert len(md_files) > 1


def test_archive_export_dry_run(tmp_path):
    input_archive = "testdata/test1_qwk.zip"
    output_zip = os.path.join(tmp_path, "export_dry.zip")

    logger = logging.getLogger("test")

    # Dry-run should not create any files on the disk
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="auto",
        output_mode="file",
        output_path=output_zip,
        encoding="cp437",
        dry_run=True,
    )

    process_merged_files([input_archive], settings, logger)

    assert not os.path.exists(output_zip)
