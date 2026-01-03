import os
import sys
from pathlib import Path
import pytest

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyqwk.cli import _expand_directories

class TestDirectoryExpansion:
    """Tests for the _expand_directories function."""

    def test_expand_flat_directory_valid_files(self, tmp_path):
        """Test finding supported files in a flat directory."""
        # Create valid files
        (tmp_path / "test1.qwk").touch()
        (tmp_path / "test2.rep").touch()
        (tmp_path / "archive.zip").touch()
        (tmp_path / "messages.dat").touch()

        # Create invalid files
        (tmp_path / "test.txt").touch()
        (tmp_path / "image.png").touch()

        expanded = _expand_directories([str(tmp_path)])

        filenames = [os.path.basename(p) for p in expanded]
        assert "test1.qwk" in filenames
        assert "test2.rep" in filenames
        assert "archive.zip" in filenames
        assert "messages.dat" in filenames
        assert "test.txt" not in filenames
        assert "image.png" not in filenames
        assert len(expanded) == 4

    def test_expand_recursive_directory(self, tmp_path):
        """Test recursive file finding in subdirectories."""
        # Root
        (tmp_path / "root.qwk").touch()

        # Subdir
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "sub.qwk").touch()

        # Sub-subdir
        subsubdir = subdir / "deep"
        subsubdir.mkdir()
        (subsubdir / "deep.rep").touch()

        expanded = _expand_directories([str(tmp_path)])

        # Normalize paths for assertion (handle separator differences if any, though tmp_path uses / usually)
        filenames = {os.path.basename(p) for p in expanded}
        assert filenames == {"root.qwk", "sub.qwk", "deep.rep"}

    def test_mixed_inputs_file_and_directory(self, tmp_path):
        """Test processing a mix of direct file paths and directory paths."""
        dir_path = tmp_path / "dir"
        dir_path.mkdir()
        (dir_path / "in_dir.qwk").touch()

        file_path = tmp_path / "direct.qwk"
        file_path.touch()

        expanded = _expand_directories([str(file_path), str(dir_path)])

        filenames = {os.path.basename(p) for p in expanded}
        assert filenames == {"in_dir.qwk", "direct.qwk"}

    def test_case_insensitivity(self, tmp_path):
        """Test that file extension matching is case-insensitive."""
        (tmp_path / "TEST.QWK").touch()
        (tmp_path / "Archive.ZIP").touch()
        (tmp_path / "MESSAGES.DAT").touch()

        expanded = _expand_directories([str(tmp_path)])

        filenames = {os.path.basename(p) for p in expanded}
        assert filenames == {"TEST.QWK", "Archive.ZIP", "MESSAGES.DAT"}

    def test_sorting_order(self, tmp_path):
        """Test that results are sorted alphabetically."""
        (tmp_path / "b.qwk").touch()
        (tmp_path / "a.qwk").touch()
        (tmp_path / "c.qwk").touch()

        expanded = _expand_directories([str(tmp_path)])

        filenames = [os.path.basename(p) for p in expanded]
        assert filenames == ["a.qwk", "b.qwk", "c.qwk"]

    def test_empty_directory(self, tmp_path):
        """Test behavior with an empty directory."""
        expanded = _expand_directories([str(tmp_path)])
        assert expanded == []

    def test_ignores_hidden_or_irrelevant_files(self, tmp_path):
        """Test that non-matching files are ignored."""
        (tmp_path / ".hidden").touch()
        (tmp_path / "README").touch()
        (tmp_path / "script.sh").touch()

        expanded = _expand_directories([str(tmp_path)])
        assert expanded == []

    def test_direct_non_matching_file_is_preserved(self, tmp_path):
        """
        Test that if a file path is passed directly (not via directory expansion),
        it is returned as-is even if it doesn't match the extensions.
        The function `_expand_directories` blindly appends non-directory paths.
        Validation happens later.
        """
        weird_file = tmp_path / "weird.file"
        weird_file.touch()

        expanded = _expand_directories([str(weird_file)])

        assert len(expanded) == 1
        assert os.path.basename(expanded[0]) == "weird.file"
