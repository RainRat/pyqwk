import logging
from pyqwk.core import matches_filters, ProcessingSettings, ParsedMessage, MessageHeader

def test_bug():
    header = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, 1, " ", 1, 0, "")
    msg = ParsedMessage("Body", 1, None, 1, header)

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="utf-8", quiet=True,
        authors=[]
    )

    result = matches_filters(msg, settings, set())
    print(f"Match with authors=[]: {result}")

if __name__ == "__main__":
    test_bug()
