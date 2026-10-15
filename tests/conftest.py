import pytest
import sys
import tkinter as _real_tk
from tkinter import filedialog as _real_filedialog
from tkinter import messagebox as _real_messagebox
from tkinter import simpledialog as _real_simpledialog
from tkinter import ttk as _real_ttk
from pathlib import Path

# Ensure the root directory is in sys.path so we can import pyqwk.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyqwk.core import ProcessedMessage, MessageHeader


@pytest.fixture
def real_tkinter_modules(monkeypatch):
    """Temporarily restore real tkinter after collection-time GUI mocks."""
    real_modules = {
        "tkinter": _real_tk,
        "tkinter.filedialog": _real_filedialog,
        "tkinter.messagebox": _real_messagebox,
        "tkinter.simpledialog": _real_simpledialog,
        "tkinter.ttk": _real_ttk,
    }
    for name, module in real_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    import pyqwk.gui as gui

    monkeypatch.setattr(gui, "tk", _real_tk)
    monkeypatch.setattr(gui, "ttk", _real_ttk)
    monkeypatch.setattr(gui, "filedialog", _real_filedialog)
    monkeypatch.setattr(gui, "messagebox", _real_messagebox)
    monkeypatch.setattr(gui, "simpledialog", _real_simpledialog)

    return _real_tk


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
