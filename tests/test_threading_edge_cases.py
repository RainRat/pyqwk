import logging
import pytest
import sys
from pathlib import Path

# Ensure the root directory is in sys.path so we can import qwk
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qwk import _order_messages_by_thread

class TestThreadingEdgeCases:
    """Test suite for edge cases in message threading."""

    def test_forward_reference_via_refnum(self, message_factory):
        """
        Verify that a message referencing a parent that appears later in the list
        is correctly threaded as a child of that parent.
        """
        # Scenario:
        # 1. Child (Refnum -> 2)
        # 2. Parent (Msgnum -> 2)
        msgs = [
            message_factory(1, 2, "Re: Topic"), # Child
            message_factory(2, 0, "Topic"),     # Parent
        ]

        ordered = _order_messages_by_thread(msgs)

        # Expected Order: Parent -> Child
        # Because Parent is a root, and Child is a child of Parent.
        # Even though Child came first, it should be nested under Parent.

        # Verify order
        assert len(ordered) == 2
        parent = ordered[0]
        child = ordered[1]

        assert parent.msgnum == 2
        assert child.msgnum == 1

        # Verify nesting
        assert parent.depth == 0
        assert child.depth == 1
        assert child.parent_msgnum == 2

    def test_broken_refnum_fallback_to_subject(self, message_factory, caplog):
        """
        Verify that if a refnum points to a missing message, the system falls back
        to subject matching if a suitable parent exists.
        """
        # Scenario:
        # 1. Root Message "Topic" (Msg 10)
        # 2. Reply "Re: Topic" (Msg 20) with Refnum -> 999 (Missing)
        msgs = [
            message_factory(10, 0, "Topic"),
            message_factory(20, 999, "Re: Topic"),
        ]

        with caplog.at_level(logging.DEBUG, logger="qwk"):
            ordered = _order_messages_by_thread(msgs)

        # Should log a debug message about missing refnum
        assert "references missing or external message" in caplog.text

        # Verify fallback threading
        assert len(ordered) == 2
        root = ordered[0]
        reply = ordered[1]

        assert root.msgnum == 10
        assert reply.msgnum == 20

        # Should be threaded via subject match
        assert reply.depth == 1
        assert reply.parent_msgnum == 10

    def test_broken_refnum_no_fallback_becomes_root(self, message_factory, caplog):
        """
        Verify that if a refnum is broken and NO subject match exists,
        the message becomes a new root.
        """
        # Scenario:
        # 1. Reply "Re: Unique Topic" (Msg 30) with Refnum -> 999 (Missing)
        msgs = [
            message_factory(30, 999, "Re: Unique Topic"),
        ]

        with caplog.at_level(logging.DEBUG, logger="qwk"):
            ordered = _order_messages_by_thread(msgs)

        assert "references missing or external message" in caplog.text

        assert len(ordered) == 1
        msg = ordered[0]
        assert msg.msgnum == 30
        assert msg.depth == 0 # Should be a root
        assert msg.parent_msgnum is None

    def test_orphan_adoption_via_subject(self, message_factory):
        """
        Verify that a message with NO refnum (e.g. 0/None) but a matching subject
        is adopted by the preceding matching thread.
        """
        # Scenario:
        # 1. Root "Topic A" (Msg 1)
        # 2. Reply "Re: Topic A" (Msg 2) refnum=0 (None)
        msgs = [
            message_factory(1, 0, "Topic A"),
            message_factory(2, 0, "Re: Topic A"),
        ]
        # Ensure refnum is None/0
        msgs[1].refnum = None

        ordered = _order_messages_by_thread(msgs)

        assert len(ordered) == 2
        assert ordered[0].msgnum == 1
        assert ordered[1].msgnum == 2

        assert ordered[1].depth == 1
        assert ordered[1].parent_msgnum == 1

    def test_interleaved_threads_with_forward_refs(self, message_factory):
        """
        Complex scenario with multiple threads and out-of-order messages.
        """
        # Msg 1: Thread A Root
        # Msg 2: Thread B Child (refs 3)
        # Msg 3: Thread B Root
        # Msg 4: Thread A Child (refs 1)
        msgs = [
            message_factory(1, 0, "Thread A"),
            message_factory(2, 3, "Re: Thread B"), # Forward ref to 3
            message_factory(3, 0, "Thread B"),
            message_factory(4, 1, "Re: Thread A"),
        ]

        ordered = _order_messages_by_thread(msgs)

        # Expected:
        # Thread A (1) -> Child (4)
        # Thread B (3) -> Child (2)
        # Or B then A, depending on stable sort of roots.
        # Roots are 1 and 3. 1 appears first in input, so 1 processed first.

        expected_ids = [1, 4, 3, 2]
        actual_ids = [m.msgnum for m in ordered]

        assert actual_ids == expected_ids

        # Verify depths
        assert ordered[0].depth == 0 # 1
        assert ordered[1].depth == 1 # 4
        assert ordered[2].depth == 0 # 3
        assert ordered[3].depth == 1 # 2
