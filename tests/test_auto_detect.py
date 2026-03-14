import pytest
import logging
import sys
from pathlib import Path

# Add shared fixtures
@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"

@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

def test_main_auto_detects_json(monkeypatch, tmp_path, baseline_path):
    from pyqwk.cli import main

    output_path = tmp_path / "output.json"

    # Mock sys.argv
    monkeypatch.setattr(sys, "argv", ["qwk", str(baseline_path), "-o", str(output_path)])

    # We want to verify that ProcessingSettings was created with format='json'
    # We can mock process_file to check settings

    captured_settings = []

    def mock_process_file(input_path, settings, logger):
        captured_settings.append(settings)

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "process_file", mock_process_file)

    main()

    assert len(captured_settings) == 1
    assert captured_settings[0].format == 'json'

def test_main_auto_detects_html(monkeypatch, tmp_path, baseline_path):
    from pyqwk.cli import main

    output_path = tmp_path / "output.html"

    monkeypatch.setattr(sys, "argv", ["qwk", str(baseline_path), "-o", str(output_path)])

    captured_settings = []
    def mock_process_file(input_path, settings, logger):
        captured_settings.append(settings)

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "process_file", mock_process_file)

    main()

    assert len(captured_settings) == 1
    assert captured_settings[0].format == 'html'

def test_main_defaults_to_text_unknown_extension(monkeypatch, tmp_path, baseline_path):
    from pyqwk.cli import main

    output_path = tmp_path / "output.foo"

    monkeypatch.setattr(sys, "argv", ["qwk", str(baseline_path), "-o", str(output_path)])

    captured_settings = []
    def mock_process_file(input_path, settings, logger):
        captured_settings.append(settings)

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "process_file", mock_process_file)

    main()

    assert len(captured_settings) == 1
    assert captured_settings[0].format == 'text'

def test_main_respects_explicit_format(monkeypatch, tmp_path, baseline_path):
    from pyqwk.cli import main

    output_path = tmp_path / "output.json"

    # User specifies format text explicitly, should override auto-detection
    monkeypatch.setattr(sys, "argv", ["qwk", str(baseline_path), "-o", str(output_path), "--format", "text"])

    captured_settings = []
    def mock_process_file(input_path, settings, logger):
        captured_settings.append(settings)

    import pyqwk.cli as cli
    monkeypatch.setattr(cli, "process_file", mock_process_file)

    main()

    assert len(captured_settings) == 1
    assert captured_settings[0].format == 'text'
