import base64
from pyqwk.core import extract_binaries

def test_base64_truncation_short_final_line():
    # 64 chars of Base64
    line64 = "A" * 64
    # A final line with 3 characters (unpadded Base64 for 2 bytes)
    # "AB" in base64 is "QUI="
    # Unpadded it is "QUI"
    final_line = "QUI"

    text = f"""
{line64}
{final_line}
"""
    binaries = extract_binaries(text)
    # If the bug exists, it might either not find a binary at all (if only one line matches)
    # or it will find it but truncate it.
    assert len(binaries) == 1, "Should have found one binary attachment"
    _, decoded_data = binaries[0]

    full_b64 = line64 + final_line
    # Add padding to make it valid for base64.b64decode
    padding_needed = (4 - (len(full_b64) % 4)) % 4
    if padding_needed == 1:
        # 1 extra character is impossible in base64, so padding_needed won't be 1 for valid unpadded.
        pass

    reference_data = base64.b64decode(full_b64 + "=" * padding_needed)

    assert len(decoded_data) == len(reference_data), f"Expected {len(reference_data)} bytes, got {len(decoded_data)}. Final line '{final_line}' was likely truncated."
