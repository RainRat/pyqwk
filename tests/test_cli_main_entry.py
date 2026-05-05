import sys
import pytest
from unittest.mock import patch
from pyqwk.cli import main


def test_cli_main_entry_point():
    """Verify that the main() entry point can be called."""
    # We use a very simple command that should exit successfully.
    # --version usually prints and exits, but argparse might raise SystemExit.
    with patch.object(sys, "argv", ["qwk", "--version"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0


def test_cli_main_no_args():
    """Verify that calling main with no args shows error and exits."""
    with patch.object(sys, "argv", ["qwk"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        # argparse exits with 2 for usage errors
        assert excinfo.value.code == 2
