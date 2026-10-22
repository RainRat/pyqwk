import pytest

from pyqwk.core import BBSInfo, MessageHeader, ParsedMessage, _write_qwk


def test_real_tk_open_select_and_export_synthetic_archive(
    tmp_path, real_tkinter_modules, monkeypatch
):
    """Exercise the GUI with real Tk: load, select, and export one QWK archive."""
    from pyqwk import gui

    tk = real_tkinter_modules
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display unavailable")

    root.withdraw()
    notices = []

    def fail_dialog(*args, **kwargs):
        raise AssertionError(f"Unexpected GUI error dialog: {args!r}")

    monkeypatch.setattr(gui.messagebox, "showerror", fail_dialog)
    monkeypatch.setattr(
        gui.messagebox, "showinfo", lambda *args, **kwargs: notices.append(args)
    )

    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Recipient",
        msgfrom="Sender",
        msgsubject="Synthetic Subject",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )
    message = ParsedMessage(
        text="Synthetic body for GUI verification.",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header,
        confname="General",
        bbs_name="Synthetic BBS",
        bbs_id="SYNTH",
    )
    source = tmp_path / "synthetic.qwk"
    _write_qwk(
        [message],
        str(source),
        bbs_info=BBSInfo(name="Synthetic BBS", bbs_id="SYNTH"),
        board_dict={1: "General"},
    )

    destination = tmp_path / "exported.txt"
    monkeypatch.setattr(
        gui.filedialog, "asksaveasfilename", lambda **kwargs: str(destination)
    )

    try:
        app = gui.QwkGuiApp(root)
        app.load_messages(str(source))
        root.update()

        assert len(app.messages) == 1
        items = app.message_list.get_children()
        assert len(items) == 1

        app.message_list.selection_set(items[0])
        app.on_message_selected()
        root.update()

        shown = app.detail_text.get("1.0", tk.END)
        assert "Synthetic Subject" in shown
        assert "Synthetic body for GUI verification." in shown

        app.export_messages()
        root.update()

        assert destination.exists()
        exported = destination.read_text(encoding="utf-8", errors="replace")
        assert "Synthetic Subject" in exported
        assert "Synthetic body for GUI verification." in exported
        assert notices
    finally:
        root.destroy()
