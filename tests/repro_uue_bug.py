from pyqwk.core import _is_binary_line

def test_uue_backtick_line():
    # Start UUE block
    line1 = "begin 644 test.txt"
    skip1, in_yenc1, in_uue1 = _is_binary_line(line1, None, False, False)
    assert skip1 is True
    assert in_uue1 is True

    # Data line
    line2 = "M" + ("A" * 60)
    skip2, in_yenc2, in_uue2 = _is_binary_line(line2, line1, False, in_uue1)
    assert skip2 is True
    assert in_uue2 is True

    # Backtick line (common in UUE before 'end')
    line3 = "`"
    skip3, in_yenc3, in_uue3 = _is_binary_line(line3, line2, False, in_uue2)

    print(f"Backtick line: skip={skip3}, in_uue={in_uue3}")

    # End line
    line4 = "end"
    skip4, in_yenc4, in_uue4 = _is_binary_line(line4, line3, False, in_uue3)
    print(f"End line: skip={skip4}, in_uue={in_uue4}")

if __name__ == "__main__":
    test_uue_backtick_line()
