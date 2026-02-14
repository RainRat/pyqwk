import logging
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyqwk.core as qwk
from pyqwk.core import ProcessingSettings, process_file

@pytest.fixture
def testdata_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata"

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
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
        encoding="latin1",
        conferences=None,
        authors=None,
        recipients=None,
        subjects=None,
        search_term=None,
        after=None,
        before=None,
        limit=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_eml_export_individual_files(tmp_path: Path, testdata_dir: Path) -> None:
    logger = logging.getLogger("pyqwk.tests")
    output_dir = tmp_path / "eml_out"
    input_file = testdata_dir / "messages.dat"

    settings = _make_settings(
        format="eml",
        individual_files=True,
        output_mode="file",
        output_path=str(output_dir)
    )

    process_file(str(input_file), settings, logger)

    files = list(output_dir.iterdir())
    assert len(files) == 1
    # Check filename format: {confnum:03d}-{msgnum:05d}-{slug}.eml
    # messages.dat message has msgnum=28, confnum=3, subject="New User"
    filename = files[0].name
    assert filename.startswith("003-00028-new_user")
    assert filename.endswith(".eml")

    content = files[0].read_text(encoding="utf-8")
    assert "From: GammaO #571 @0*1" in content
    assert "Subject: New User" in content
    assert "X-QWK-Conference: 3" in content
    assert "Content-Type: text/plain; charset=utf-8" in content
    # EML should NOT have the mbox "From " separator
    assert not content.startswith("From ")

def test_eml_filename_slugification() -> None:
    from pyqwk.core import ParsedMessage, MessageHeader, _generate_safe_filename
    header = MessageHeader(
        status=" ", msgnum=123, msgdate="01-01-90", msgtime="12:00", msgto="All", msgfrom="From",
        msgsubject="Hello! World / Test #1", msgpassword="", refnum=None,
        numblocks=None, msgflag=" ", confnum=1, lognum=1, nettag=" ",
    )
    msg = ParsedMessage(text="...", msgnum=123, refnum=None, confnum=1, header=header)

    filename = _generate_safe_filename(msg, "eml", 1)
    assert filename == "001-00123-hello_world_test_1.eml"

def test_eml_default_individual_files(tmp_path: Path, testdata_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pyqwk.cli import main
    import os

    output_dir = tmp_path / "eml_auto"
    input_file = testdata_dir / "messages.dat"

    # Test that --format eml with -o directory defaults to individual files
    os.makedirs(output_dir)

    monkeypatch.setattr(sys, "argv", ["qwk", str(input_file), "--format", "eml", "-o", str(output_dir)])

    # main() may or may not call sys.exit(0) on success
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    files = list(output_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".eml"
