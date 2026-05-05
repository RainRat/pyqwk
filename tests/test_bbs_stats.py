from pyqwk.core import ProcessingSettings, calculate_archive_stats
import logging


def test_bbs_stats(tmp_path):
    # Create a dummy QWK archive structure (json format is easier to mock for calculate_archive_stats)
    import json

    header = {
        "status": " ",
        "msgnum": 1,
        "msgdate": "01-01-24",
        "msgtime": "12:00",
        "msgto": "To",
        "msgfrom": "From",
        "msgsubject": "Subj",
        "msgpassword": "",
        "refnum": 0,
        "numblocks": 1,
        "msgflag": " ",
        "confnum": 1,
        "lognum": 1,
        "nettag": "",
    }

    data = [
        {
            "header": header,
            "text": "Message 1",
            "conference": "General",
            "bbs_name": "BBS A",
            "bbs_id": "ID_A",
        },
        {
            "header": {**header, "msgnum": 2},
            "text": "Message 2",
            "conference": "General",
            "bbs_name": "BBS B",
            "bbs_id": "ID_B",
        },
    ]

    archive_path = tmp_path / "archive.json"
    archive_path.write_text(json.dumps(data))

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    logger = logging.getLogger("test")
    stats = calculate_archive_stats([str(archive_path)], settings, logger)

    assert "bbses" in stats
    bbs_names = [b["name"] for b in stats["bbses"]]
    assert "BBS A" in bbs_names
    assert "BBS B" in bbs_names

    counts = {b["name"]: b["count"] for b in stats["bbses"]}
    assert counts["BBS A"] == 1
    assert counts["BBS B"] == 1
