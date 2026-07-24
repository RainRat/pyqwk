import sys
import pytest
from unittest.mock import patch
from pyqwk.cli import main


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_blog(mock_expand_paths, mock_process_merged_files):
    """Verify the 'blog' preset defaults."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "blog", "-o", "out_dir"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]

    assert settings.format == "markdown"
    assert settings.truncate_signatures is True
    assert settings.cut_quoting is True
    assert settings.binaries_removal is True
    assert settings.threaded is True
    assert settings.individual_files is True


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_email(mock_expand_paths, mock_process_merged_files):
    """Verify the 'email' preset defaults."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "email", "-o", "out_dir"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]

    assert settings.format == "eml"
    assert settings.individual_files is True


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_backup(mock_expand_paths, mock_process_merged_files):
    """Verify the 'backup' preset defaults."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "backup", "-o", "out.db"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]

    assert settings.format == "sqlite"
    assert settings.private is True
    assert settings.unique is True


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_digest(mock_expand_paths, mock_process_merged_files):
    """Verify the 'digest' preset defaults."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "digest", "-o", "out.html"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]

    assert settings.format == "html"
    assert settings.threaded is True
    assert settings.truncate_signatures is True
    assert settings.cut_quoting is True
    assert settings.binaries_removal is True
    assert settings.include_toc is True


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_text_archive(mock_expand_paths, mock_process_merged_files):
    """Verify the 'text-archive' preset defaults."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "text-archive", "-o", "out.txt"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]

    assert settings.format == "text"
    assert settings.truncate_signatures is True
    assert settings.cut_quoting is True
    assert settings.binaries_removal is True
    assert settings.no_header is True


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_overrides(mock_expand_paths, mock_process_merged_files):
    """Verify that explicitly specified flags override preset defaults."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    # Preset 'blog' defaults to format='markdown' and threaded=True.
    # We override format to 'html'.
    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "blog", "-F", "html", "-o", "out_dir"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]

    # format should be html (overridden), but threaded and individual_files should still be True (from preset)
    assert settings.format == "html"
    assert settings.threaded is True
    assert settings.individual_files is True


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_oneline_conflict(mock_expand_paths, mock_process_merged_files):
    """Verify that using --oneline with a preset that has individual-files raises error."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    # 'blog' preset triggers individual_files=True. Specifying --oneline should raise a parser/usage error.
    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "blog", "--oneline", "-o", "out_dir"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 2


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_overrides_complex(mock_expand_paths, mock_process_merged_files):
    """Verify that explicit overrides using format=html or attached short options work."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "blog", "--format=html", "-o", "out_dir"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]
    assert settings.format == "html"


@patch("pyqwk.cli.process_merged_files")
@patch("pyqwk.cli.expand_paths")
def test_preset_override_combined_short_options(mock_expand_paths, mock_process_merged_files):
    """Verify that combined short-flag options (e.g. -pi) are correctly recognized and override preset values."""
    mock_expand_paths.return_value = ["dummy.qwk"]

    with patch.object(sys, "argv", ["qwk", "dummy.qwk", "-P", "blog", "-pi", "-o", "out_dir"]):
        main()

    mock_process_merged_files.assert_called_once()
    settings = mock_process_merged_files.call_args[0][1]
    assert settings.individual_files is True
    assert settings.private is True
