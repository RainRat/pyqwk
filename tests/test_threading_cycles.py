import logging
from pyqwk.core import _order_messages_by_thread


def test_threading_circular_reference(message_factory, caplog):
    """Test that circular references are detected and do not cause infinite recursion."""
    # A -> B -> A
    # Msg 1 refs 2. Msg 2 refs 1.
    msgs = [
        message_factory(1, 2, "Message A"),
        message_factory(2, 1, "Message B"),
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        ordered = _order_messages_by_thread(msgs)

    # Check for warning
    assert "Circular reference detected" in caplog.text
    # Cycle is detected when processing the second message (B), which tries to set A as parent
    # but A is already a child of B (due to B appearing later in list/processing order).
    assert "conf 1, msgnum 2" in caplog.text

    # Both messages should be present
    assert len(ordered) == 2
    ids = {m.msgnum for m in ordered}
    assert 1 in ids
    assert 2 in ids

    # Check structure
    root = ordered[0]
    child = ordered[1]

    assert root.depth == 0
    assert child.depth == 1
    assert child.parent_msgnum == root.msgnum


def test_threading_self_reference(message_factory, caplog):
    """Test that self-references are handled gracefully (ignored) and do not cause infinite recursion."""
    # A -> A
    # Code explicitly checks `if parent_index != index`, so this should NOT form a cycle in the graph.
    msgs = [
        message_factory(1, 1, "Message A"),
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        ordered = _order_messages_by_thread(msgs)

    # Should be no warning because it's filtered out before traversal
    assert "Circular reference detected" not in caplog.text

    assert len(ordered) == 1
    assert ordered[0].msgnum == 1
    assert ordered[0].depth == 0
    # It ends up as a root
    assert ordered[0].parent_msgnum is None


def test_threading_long_cycle(message_factory, caplog):
    """Test a longer cycle: A -> B -> C -> A."""
    msgs = [
        message_factory(1, 3, "Message A"),
        message_factory(2, 1, "Message B"),
        message_factory(3, 2, "Message C"),
    ]

    with caplog.at_level(logging.WARNING, logger="pyqwk.core"):
        ordered = _order_messages_by_thread(msgs)

    assert "Circular reference detected" in caplog.text
    assert len(ordered) == 3

    # One should be root, others nested
    depths = [m.depth for m in ordered]
    assert 0 in depths
    assert 1 in depths
    assert 2 in depths
