import sys
from unittest.mock import patch
from pyqwk.cli import main

def test_cli_multi_input_no_output_defaults_to_merge_stdout(capsys):
    """Test that providing multiple input files without -o defaults to merging to stdout."""
    # Use real test files from testdata
    test_file1 = "testdata/test1_qwk.zip"
    test_file2 = "testdata/test2_qwk.zip"

    # Mock sys.argv
    test_args = ["pyqwk", test_file1, test_file2]

    # Mock process_merged_files to avoid actually processing and printing large amounts of data
    with patch("pyqwk.cli.process_merged_files") as mock_process_merged:
        with patch.object(sys, 'argv', test_args):
            # We expect it NOT to call sys.exit or parser.error
            main()

        # Check that process_merged_files was called
        mock_process_merged.assert_called_once()

        # Verify the settings passed to process_merged_files
        args, kwargs = mock_process_merged.call_args
        settings = args[1]

        assert settings.merge is True
        assert settings.output_mode == 'stdout'
        assert settings.output_path is None
