import io
import logging
from unittest.mock import MagicMock, patch

import pytest

from pyqwk.core import (
    ConferenceMap,
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    calculate_archive_stats,
    process_merged_files,
)


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def base_settings():
    return ProcessingSettings(
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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )


def create_mock_msg(
    msgnum,
    msgfrom="User",
    msgto="All",
    msgsubject="Subject",
    confnum=1,
    bbs_name=None,
    text=None,
):
    text_content = text if text is not None else f"Body of {msgnum}"
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto=msgto,
        msgfrom=msgfrom,
        msgsubject=msgsubject,
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text=text_content,
        msgnum=msgnum,
        refnum=0,
        confnum=confnum,
        header=header,
        confname=f"Conf {confnum}",
        bbs_name=bbs_name,
    )


def test_limit_restricts_output(tmp_path, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"
    mock_messages = [create_mock_msg(i, text=f"Message {i}") for i in range(1, 11)]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        limit=3,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Message 1" in content
    assert "Message 2" in content
    assert "Message 3" in content
    assert "Message 4" not in content


def test_limit_zero(tmp_path, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"
    mock_messages = [create_mock_msg(i, text=f"Message {i}") for i in range(1, 11)]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        limit=0,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content == ""


def test_limit_higher_than_total(tmp_path, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"
    mock_messages = [create_mock_msg(i, text=f"Message {i}") for i in range(1, 11)]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *args, **kwargs: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *args, **kwargs: iter(mock_messages))

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        limit=20,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert "Message 10" in content


def test_limit_per_author_logic(mock_logger, base_settings):
    base_settings.limit_per_author = 2
    messages = [
        create_mock_msg(101, msgfrom="Alice"),
        create_mock_msg(102, msgfrom="Alice"),
        create_mock_msg(103, msgfrom="Alice"),
        create_mock_msg(201, msgfrom="Bob"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            alice_msgs = [m for m in written_messages if m.header.msgfrom == "Alice"]
            bob_msgs = [m for m in written_messages if m.header.msgfrom == "Bob"]

            assert len(alice_msgs) == 2
            assert len(bob_msgs) == 1
            assert [m.msgnum for m in alice_msgs] == [101, 102]


def test_limit_per_author_case_insensitivity(mock_logger, base_settings):
    base_settings.limit_per_author = 1
    messages = [
        create_mock_msg(101, msgfrom="Alice"),
        create_mock_msg(102, msgfrom="alice"),
        create_mock_msg(103, msgfrom="ALICE"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101


def test_limit_per_author_with_limit_per_conf(mock_logger, base_settings):
    base_settings.limit_per_author = 1
    base_settings.limit_per_conf = 2

    messages = [
        create_mock_msg(101, msgfrom="Alice", confnum=1),
        create_mock_msg(102, msgfrom="Alice", confnum=1),
        create_mock_msg(103, msgfrom="Bob", confnum=1),
        create_mock_msg(104, msgfrom="Charlie", confnum=1),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 2
            assert [m.msgnum for m in written_messages] == [101, 103]


def test_limit_per_bbs_logic(mock_logger, base_settings):
    base_settings.limit_per_bbs = 2
    messages = [
        create_mock_msg(101, bbs_name="BBS A"),
        create_mock_msg(102, bbs_name="BBS A"),
        create_mock_msg(103, bbs_name="BBS A"),
        create_mock_msg(201, bbs_name="BBS B"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            bbs_a_msgs = [m for m in written_messages if m.bbs_name == "BBS A"]
            bbs_b_msgs = [m for m in written_messages if m.bbs_name == "BBS B"]

            assert len(bbs_a_msgs) == 2
            assert len(bbs_b_msgs) == 1
            assert [m.msgnum for m in bbs_a_msgs] == [101, 102]


def test_limit_per_bbs_stats(mock_logger, base_settings):
    base_settings.limit_per_bbs = 1
    messages = [
        create_mock_msg(101, bbs_name="BBS A"),
        create_mock_msg(102, bbs_name="BBS A"),
        create_mock_msg(201, bbs_name="BBS B"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        stats = calculate_archive_stats(["mock.qwk"], base_settings, mock_logger)
        assert stats["matching_messages"] == 2
        assert stats["total_messages"] == 3


def test_limit_per_bbs_case_insensitive(mock_logger, base_settings):
    base_settings.limit_per_bbs = 1
    messages = [
        create_mock_msg(101, bbs_name="BBS A"),
        create_mock_msg(102, bbs_name="bbs a"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101


def test_limit_per_conf_logic(mock_logger, base_settings):
    base_settings.limit_per_conf = 2
    messages = [
        create_mock_msg(101, confnum=1),
        create_mock_msg(102, confnum=1),
        create_mock_msg(103, confnum=1),
        create_mock_msg(201, confnum=2),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1", 2: "Conf 2"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            conf1_msgs = [m for m in written_messages if m.confnum == 1]
            conf2_msgs = [m for m in written_messages if m.confnum == 2]

            assert len(conf1_msgs) == 2
            assert len(conf2_msgs) == 1
            assert [m.msgnum for m in conf1_msgs] == [101, 102]


def test_limit_per_conf_with_global_limit(mock_logger, base_settings):
    base_settings.limit_per_conf = 2
    base_settings.limit = 3

    messages = [
        create_mock_msg(101, confnum=1),
        create_mock_msg(102, confnum=1),
        create_mock_msg(103, confnum=1),
        create_mock_msg(201, confnum=2),
        create_mock_msg(202, confnum=2),
        create_mock_msg(203, confnum=2),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1", 2: "Conf 2"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            assert [m.msgnum for m in written_messages] == [101, 102, 201]


def test_limit_per_conf_streaming_behavior(mock_logger, base_settings):
    base_settings.limit_per_conf = 1
    messages = [
        create_mock_msg(101, confnum=1),
        create_mock_msg(102, confnum=1),
        create_mock_msg(201, confnum=2),
        create_mock_msg(202, confnum=2),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1", 2: "Conf 2"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 2
            assert [m.msgnum for m in written_messages] == [101, 201]


def test_limit_per_subject_logic(mock_logger, base_settings):
    base_settings.limit_per_subject = 1
    messages = [
        create_mock_msg(1, msgfrom="User A", msgsubject="Subject A"),
        create_mock_msg(2, msgfrom="User B", msgsubject="Re: Subject A"),
        create_mock_msg(3, msgfrom="User C", msgsubject="Subject B"),
        create_mock_msg(4, msgfrom="User D", msgsubject="Subject A"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, ConferenceMap())):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            process_merged_files(["dummy.qwk"], base_settings, mock_logger)
            output = fake_out.getvalue()
            assert "Body of 1" in output
            assert "Body of 3" in output
            assert "Body of 2" not in output
            assert "Body of 4" not in output

    base_settings.limit_per_subject = 2
    with patch("pyqwk.core.load_data", return_value=(messages, ConferenceMap())):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            process_merged_files(["dummy.qwk"], base_settings, mock_logger)
            output = fake_out.getvalue()
            assert "Body of 1" in output
            assert "Body of 2" in output
            assert "Body of 3" in output
            assert "Body of 4" not in output


def test_limit_per_subject_stats(mock_logger, base_settings):
    base_settings.limit_per_subject = 1
    messages = [
        create_mock_msg(1, msgfrom="User A", msgsubject="Subject A"),
        create_mock_msg(2, msgfrom="User B", msgsubject="Re: Subject A"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, ConferenceMap())):
        stats = calculate_archive_stats(["dummy.qwk"], base_settings, mock_logger)
        assert stats["total_messages"] == 2
        assert stats["matching_messages"] == 1


def test_consistent_limits_in_stats(mock_logger, base_settings):
    messages = [
        create_mock_msg(1, msgfrom="User A", msgsubject="Subject A", confnum=1),
        create_mock_msg(2, msgfrom="User A", msgsubject="Subject B", confnum=1),
        create_mock_msg(3, msgfrom="User B", msgsubject="Subject C", confnum=2),
    ]

    base_settings.limit_per_conf = 1
    with patch("pyqwk.core.load_data", return_value=(messages, ConferenceMap())):
        stats = calculate_archive_stats(["dummy.qwk"], base_settings, mock_logger)
        assert stats["matching_messages"] == 2

    base_settings.limit_per_conf = None
    base_settings.limit_per_author = 1
    with patch("pyqwk.core.load_data", return_value=(messages, ConferenceMap())):
        stats = calculate_archive_stats(["dummy.qwk"], base_settings, mock_logger)
        assert stats["matching_messages"] == 2


def test_limit_per_to_logic(mock_logger, base_settings):
    base_settings.limit_per_to = 2
    messages = [
        create_mock_msg(101, msgto="Alice"),
        create_mock_msg(102, msgto="Alice"),
        create_mock_msg(103, msgto="Alice"),
        create_mock_msg(201, msgto="Bob"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 3
            alice_msgs = [m for m in written_messages if m.header.msgto == "Alice"]
            bob_msgs = [m for m in written_messages if m.header.msgto == "Bob"]

            assert len(alice_msgs) == 2
            assert len(bob_msgs) == 1
            assert [m.msgnum for m in alice_msgs] == [101, 102]


def test_limit_per_to_stats(mock_logger, base_settings):
    base_settings.limit_per_to = 1
    messages = [
        create_mock_msg(101, msgto="Alice"),
        create_mock_msg(102, msgto="Alice"),
        create_mock_msg(201, msgto="Bob"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        stats = calculate_archive_stats(["mock.qwk"], base_settings, mock_logger)
        assert stats["matching_messages"] == 2
        assert stats["total_messages"] == 3


def test_limit_per_to_case_insensitive(mock_logger, base_settings):
    base_settings.limit_per_to = 1
    messages = [
        create_mock_msg(101, msgto="Alice"),
        create_mock_msg(102, msgto="alice"),
    ]

    with patch("pyqwk.core.load_data", return_value=(messages, {1: "Conf 1"})):
        with patch("pyqwk.core.write_messages") as mock_write:
            process_merged_files(["mock.qwk"], base_settings, mock_logger)
            written_messages = mock_write.call_args[0][0]

            assert len(written_messages) == 1
            assert written_messages[0].msgnum == 101


def test_limit_zero_with_sorting(mock_logger):
    settings = ProcessingSettings(
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
        encoding="cp437",
        limit=0,
        sort="num",
        quiet=True,
    )
    msg1 = create_mock_msg(1, text="msg1")
    bd = ConferenceMap({1: "Conf1"})

    with patch("pyqwk.core.load_data", return_value=([msg1], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, mock_logger)
            output = mock_stdout.getvalue()
            assert output == "\n"


def test_tail_zero_with_sorting(mock_logger):
    settings = ProcessingSettings(
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
        encoding="cp437",
        tail=0,
        sort="num",
        quiet=True,
    )
    msg1 = create_mock_msg(1, text="msg1")
    bd = ConferenceMap({1: "Conf1"})

    with patch("pyqwk.core.load_data", return_value=([msg1], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, mock_logger)
            output = mock_stdout.getvalue()
            assert output == "\n"


def test_skip_zero_with_sorting(mock_logger):
    settings = ProcessingSettings(
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
        encoding="cp437",
        skip=0,
        sort="num",
        quiet=True,
    )
    msg1 = create_mock_msg(1, text="msg1")
    bd = ConferenceMap({1: "Conf1"})

    with patch("pyqwk.core.load_data", return_value=([msg1], bd)):
        with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
            process_merged_files(["test.qwk"], settings, mock_logger)
            output = mock_stdout.getvalue()
            assert "From" in output
            assert "To" in output
            assert "Sub" in output
