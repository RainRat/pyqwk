from unittest.mock import MagicMock, patch

from pyqwk.core import (
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    matches_filters,
    calculate_archive_stats,
    render_stats_as_text
)

def test_has_emails_filter():
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437', has_emails=True
    )

    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")

    msg_with_email = ParsedMessage("Contact me at test@example.com", 1, None, 1, header)
    msg_without_email = ParsedMessage("Hello world", 2, None, 1, header)

    assert matches_filters(msg_with_email, settings, set()) is True
    assert matches_filters(msg_without_email, settings, set()) is False

def test_has_phones_filter():
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437', has_phones=True
    )

    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")

    msg_with_phone = ParsedMessage("Call 555-1234", 1, None, 1, header)
    msg_without_phone = ParsedMessage("Hello world", 2, None, 1, header)

    assert matches_filters(msg_with_phone, settings, set()) is True
    assert matches_filters(msg_without_phone, settings, set()) is False

def test_has_ansi_filter():
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format='text', separator='none', output_mode='stdout',
        output_path=None, encoding='cp437', has_ansi=True
    )

    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")

    msg_with_ansi = ParsedMessage("Color \x1b[31mRed\x1b[0m text", 1, None, 1, header)
    msg_without_ansi = ParsedMessage("Hello world", 2, None, 1, header)

    assert matches_filters(msg_with_ansi, settings, set()) is True
    assert matches_filters(msg_without_ansi, settings, set()) is False

def test_entity_discovery_stats():
    # Mock data for stats
    header = MessageHeader(" ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 0, "")
    messages = [
        ParsedMessage("Email: user1@a.com and user1@a.com", 1, None, 1, header),
        ParsedMessage("Email: user2@b.com", 2, None, 1, header),
        ParsedMessage("Phone: 555-1111 and 555-2222", 3, None, 1, header),
        ParsedMessage("Phone: 555-1111", 4, None, 1, header),
    ]

    with patch('pyqwk.core.load_data') as mock_load:
        mock_load.return_value = (messages, {1: "General"})

        settings = ProcessingSettings(
            verbose=False, private=True, no_header=False, truncate_signatures=False,
            cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
            redact_pii=False, format='text', separator='none', output_mode='stdout',
            output_path=None, encoding='cp437'
        )

        stats = calculate_archive_stats(["dummy.qwk"], settings, MagicMock())

        # Verify emails were found and counted correctly
        emails = {e['email']: e['count'] for e in stats['emails']}
        assert "user1@a.com" in emails
        assert "user2@b.com" in emails
        assert emails["user1@a.com"] == 2
        assert emails["user2@b.com"] == 1

        # Verify phones were found and counted correctly
        phones = {p['phone']: p['count'] for p in stats['phones']}
        assert "555-1111" in phones
        assert "555-2222" in phones
        assert phones["555-1111"] == 2
        assert phones["555-2222"] == 1

        # Verify text rendering includes emails and phones
        report = render_stats_as_text(stats)
        assert "Top Emails:" in report
        assert "user1@a.com" in report
        assert "Top Phone Numbers:" in report
        assert "555-1111" in report

def test_gui_variable_initialization():
    # Mock tkinter before importing gui
    mock_tk = MagicMock()
    def make_var(value=False, **kwargs):
        m = MagicMock()
        m.get.return_value = value
        return m
    mock_tk.BooleanVar.side_effect = make_var
    mock_ttk = MagicMock()
    with patch.dict("sys.modules", {"tkinter": mock_tk, "tkinter.ttk": mock_ttk, "tkinter.filedialog": MagicMock(), "tkinter.messagebox": MagicMock()}):
        from pyqwk.gui import QwkGuiApp
        root = MagicMock()
        app = QwkGuiApp(root)

        # Check if variables are initialized
        assert hasattr(app, "has_emails_var")
        assert hasattr(app, "has_phones_var")
        assert hasattr(app, "has_ansi_var")

def test_gui_settings_propagation():
    # Mock tkinter before importing gui
    mock_tk = MagicMock()
    # Create distinct mock objects for the variables so they can have different return values
    mock_emails = MagicMock()
    mock_emails.get.return_value = True
    mock_phones = MagicMock()
    mock_phones.get.return_value = False
    mock_ansi = MagicMock()
    mock_ansi.get.return_value = True

    # Track calls to BooleanVar to assign our specific mocks
    vars_created = []
    def make_var(value=False, **kwargs):
        m = MagicMock()
        m.get.return_value = value
        vars_created.append(m)
        return m

    mock_tk.BooleanVar.side_effect = make_var
    mock_ttk = MagicMock()

    with patch.dict("sys.modules", {"tkinter": mock_tk, "tkinter.ttk": mock_ttk, "tkinter.filedialog": MagicMock(), "tkinter.messagebox": MagicMock()}):
        from pyqwk.gui import QwkGuiApp
        root = MagicMock()
        app = QwkGuiApp(root)

        # Override the variables we care about with distinct behavior
        app.has_emails_var = mock_emails
        app.has_phones_var = mock_phones
        app.has_ansi_var = mock_ansi

        settings = app._current_settings()
        assert settings.has_emails is True
        assert settings.has_phones is False
        assert settings.has_ansi is True
