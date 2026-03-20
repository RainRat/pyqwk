from pyqwk.core import _render_stats_bar_chart

def test_render_stats_bar_chart_empty():
    """Verify that an empty list returns an empty list."""
    assert _render_stats_bar_chart("Title", []) == []

def test_render_stats_bar_chart_basic():
    """Verify basic bar chart rendering without colors."""
    items = [("Label A", 10), ("Label B", 5)]
    output = _render_stats_bar_chart("Stats", items, use_colors=False)

    assert len(output) == 3 # Title + 2 items
    assert "  Stats" in output[0]
    assert "Label A" in output[1]
    assert "10" in output[1]
    assert "##########" in output[1] # 10/10 * 40 = 40 chars? No, wait.
    # Max count is 10. bar_len = int(10 * 40 / 10) = 40.
    assert "#" * 40 in output[1]
    assert "Label B" in output[2]
    assert " 5" in output[2]
    assert "#" * 20 in output[2]

def test_render_stats_bar_chart_with_colors():
    """Verify bar chart rendering with colors."""
    items = [("Label A", 10)]
    output = _render_stats_bar_chart("Stats", items, use_colors=True)

    assert "\033[" in output[0]
    assert "\033[" in output[1]
    assert "Label A" in output[1]

def test_render_stats_bar_chart_long_labels():
    """Verify that long labels are truncated."""
    long_label = "A" * 50
    items = [(long_label, 10)]
    output = _render_stats_bar_chart("Stats", items, use_colors=False)

    # Truncated to 25 chars
    assert "A" * 25 in output[1]
    assert "A" * 26 not in output[1]

def test_render_stats_bar_chart_integer_labels():
    """Verify that integer labels (like years) are handled correctly."""
    items = [(2023, 10), (2024, 20)]
    output = _render_stats_bar_chart("Years", items, use_colors=False)

    assert "2023" in output[1]
    assert "2024" in output[2]

def test_render_stats_bar_chart_zero_max():
    """Verify rendering when all counts are zero."""
    items = [("Label A", 0), ("Label B", 0)]
    output = _render_stats_bar_chart("Zeroes", items, use_colors=False)

    assert "Label A" in output[1]
    assert "   0" in output[1]
    assert "#" not in output[1][output[1].find(":"):]
