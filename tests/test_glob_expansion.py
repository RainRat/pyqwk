import os
import pytest
from pyqwk.core import expand_paths


def test_expand_paths_no_wildcards(tmp_path):
    """Verify that paths without wildcards are unaffected and treated normally."""
    file1 = tmp_path / "test1.qwk"
    file1.touch()

    file2 = tmp_path / "test2.zip"
    file2.touch()

    # Passing normal files
    paths = [str(file1), str(file2)]
    result = expand_paths(paths)
    assert len(result) == 2
    assert str(file1) in result
    assert str(file2) in result


def test_expand_paths_simple_wildcard(tmp_path):
    """Verify that standard wildcard expansion resolves matching files correctly."""
    # Create matching and non-matching files
    qwk_file1 = tmp_path / "one.qwk"
    qwk_file1.touch()

    qwk_file2 = tmp_path / "two.qwk"
    qwk_file2.touch()

    other_file = tmp_path / "three.txt"
    other_file.touch()

    pattern = str(tmp_path / "*.qwk")
    result = expand_paths([pattern])

    assert len(result) == 2
    assert str(qwk_file1) in result
    assert str(qwk_file2) in result
    assert str(other_file) not in result


def test_expand_paths_wildcard_in_subdir(tmp_path):
    """Verify wildcard expansion within subdirectories."""
    sub_dir = tmp_path / "archives"
    sub_dir.mkdir()

    zip_file = sub_dir / "packet1.zip"
    zip_file.touch()

    tar_file = sub_dir / "packet2.tar"
    tar_file.touch()

    pattern = str(sub_dir / "*.zip")
    result = expand_paths([pattern])

    assert len(result) == 1
    assert str(zip_file) in result
    assert str(tar_file) not in result


def test_expand_paths_no_matches_fallback(tmp_path):
    """Verify that patterns matching no files fall back to the original pattern."""
    pattern = str(tmp_path / "*.nonexistent")
    result = expand_paths([pattern])

    # Should fall back to the original string so downstream can handle file not found nicely
    assert len(result) == 1
    assert result[0] == pattern


def test_expand_paths_glob_yielding_directories(tmp_path):
    """Verify that if a wildcard resolves to directories, those directories are recursively expanded."""
    sub_dir1 = tmp_path / "conf1"
    sub_dir1.mkdir()
    sub_dir2 = tmp_path / "conf2"
    sub_dir2.mkdir()

    file1 = sub_dir1 / "messages.dat"
    file1.touch()

    file2 = sub_dir2 / "reply.dat"
    file2.touch()

    # Pattern matching the directories
    pattern = str(tmp_path / "conf*")
    result = expand_paths([pattern])

    assert len(result) == 2
    assert str(file1) in result
    assert str(file2) in result
