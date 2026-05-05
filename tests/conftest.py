import pytest
import sys
from pathlib import Path

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyqwk.core import ProcessedMessage, MessageHeader


@pytest.fixture
def message_factory():
    def _make_msg(msgnum, refnum, subject, confnum=1, text="Body\n", status=" "):
        header = MessageHeader(
            status=status,
            msgnum=msgnum,
            msgdate="",
            msgtime="",
            msgto="",
            msgfrom="",
            msgsubject=subject,
            msgpassword="",
            refnum=refnum,
            numblocks=None,
            msgflag="",
            confnum=confnum,
            lognum=0,
            nettag="",
        )
        return ProcessedMessage(
            text=text, msgnum=msgnum, refnum=refnum, confnum=confnum, header=header
        )

    return _make_msg
