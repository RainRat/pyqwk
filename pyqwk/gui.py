import logging
import os
import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk

from pyqwk.core import (
    ProcessingSettings,
    _order_messages_by_thread,
    load_data,
    parse_messages,
    process_message,
)


class QwkGuiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PyQWK Reader")
        self.root.geometry("1000x650")

        self.logger = logging.getLogger(__name__)

        self.messages = []
        self.board_dict: dict[int, str] = {}
        self.current_path: str | None = None

        self.clean_var = tk.BooleanVar(value=False)
        self.private_var = tk.BooleanVar(value=False)
        self.redact_var = tk.BooleanVar(value=False)
        self.threaded_var = tk.BooleanVar(value=False)

        self._build_menu()
        self._build_toolbar()
        self._build_layout()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open...", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(10, 5))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="Open QWK", command=self.open_file).pack(
            side=tk.LEFT
        )
        ttk.Checkbutton(
            toolbar,
            text="Clean",
            variable=self.clean_var,
            command=self.reload_messages,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(
            toolbar,
            text="Include Private",
            variable=self.private_var,
            command=self.reload_messages,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(
            toolbar,
            text="Redact PII",
            variable=self.redact_var,
            command=self.reload_messages,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(
            toolbar,
            text="Threaded",
            variable=self.threaded_var,
            command=self.reload_messages,
        ).pack(side=tk.LEFT, padx=8)

        self.status_label = ttk.Label(toolbar, text="Ready")
        self.status_label.pack(side=tk.RIGHT)

    def _build_layout(self) -> None:
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Frame(paned, padding=8)
        detail_frame = ttk.Frame(paned, padding=8)
        paned.add(list_frame, weight=1)
        paned.add(detail_frame, weight=2)

        ttk.Label(list_frame, text="Messages").pack(anchor=tk.W)

        # Treeview setup
        self.message_list = ttk.Treeview(
            list_frame,
            columns=("From", "Date", "Conference"),
            selectmode="browse",
        )
        self.message_list.heading("#0", text="Subject", anchor=tk.W)
        self.message_list.heading("From", text="From", anchor=tk.W)
        self.message_list.heading("Date", text="Date", anchor=tk.W)
        self.message_list.heading("Conference", text="Conference", anchor=tk.W)

        self.message_list.column("#0", minwidth=200, width=300)
        self.message_list.column("From", minwidth=80, width=120)
        self.message_list.column("Date", minwidth=80, width=120)
        self.message_list.column("Conference", minwidth=80, width=100)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.message_list.yview
        )
        self.message_list.configure(yscroll=scrollbar.set)

        self.message_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.message_list.bind("<<TreeviewSelect>>", self.on_message_selected)

        ttk.Label(detail_frame, text="Message Detail").pack(anchor=tk.W)
        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.detail_text.config(state=tk.DISABLED)

    def _current_settings(self) -> ProcessingSettings:
        clean = self.clean_var.get()
        return ProcessingSettings(
            verbose=False,
            private=self.private_var.get(),
            no_header=True,
            truncate_signatures=clean,
            cut_quoting=clean,
            individual_files=False,
            threaded=self.threaded_var.get(),
            binaries_removal=clean,
            redact_pii=self.redact_var.get(),
            format='text',
            separator='none',
            output_mode='stdout',
            output_path=None,
            encoding='cp437',
            quiet=True,
        )

    def _format_message_detail(self, message_index: int) -> str:
        message = self.messages[message_index]
        header = message.header
        conf_name = self.board_dict.get(header.confnum, str(header.confnum))
        parts = [
            f"Conference: {conf_name}",
            f"Date: {header.msgdate} {header.msgtime}",
            f"From: {header.msgfrom}",
            f"To: {header.msgto}",
            f"Subject: {header.msgsubject}",
        ]
        if header.msgnum is not None:
            parts.append(f"Message #: {header.msgnum}")
        if message.refnum:
            parts.append(f"Reference #: {message.refnum}")
        parts.append("")
        parts.append(message.text)
        return "\n".join(parts)

    def open_file(self) -> None:
        filetypes = [
            ("QWK archives", "*.qwk"),
            ("messages.dat", "messages.dat"),
            ("All files", "*.*"),
        ]
        path = filedialog.askopenfilename(
            title="Open QWK archive",
            filetypes=filetypes,
        )
        if not path:
            return
        self.current_path = path
        self.load_messages(path)

    def reload_messages(self) -> None:
        if self.current_path:
            self.load_messages(self.current_path)

    def load_messages(self, path: str) -> None:
        try:
            self.status_label.config(text="Loading...")
            self.root.update_idletasks()
            settings = self._current_settings()
            file_data, board_dict = load_data(path, self.logger, settings.encoding)
            messages = []
            for parsed_message in parse_messages(file_data, None, settings.encoding):
                if (
                    settings.private is False
                    and parsed_message.header.is_private is True
                ) or parsed_message.header.is_password is True:
                    continue
                processed_buffer = process_message(
                    parsed_message.text,
                    settings.truncate_signatures,
                    settings.cut_quoting,
                    settings.binaries_removal,
                    settings.redact_pii,
                )
                messages.append(replace(parsed_message, text=processed_buffer))

            if settings.threaded:
                messages = _order_messages_by_thread(messages)

            self.messages = messages
            self.board_dict = board_dict

            self.message_list.delete(*self.message_list.get_children())
            parent_at_depth = {-1: ""}

            for index, message in enumerate(self.messages):
                header = message.header
                conf_name = self.board_dict.get(header.confnum, str(header.confnum))
                subject = header.msgsubject.strip() or "(no subject)"

                parent_iid = ""
                if settings.threaded:
                    parent_iid = parent_at_depth.get(message.depth - 1, "")

                iid = str(index)
                self.message_list.insert(
                    parent_iid,
                    tk.END,
                    iid=iid,
                    text=subject,
                    values=(
                        header.msgfrom,
                        f"{header.msgdate} {header.msgtime}",
                        conf_name,
                    ),
                    open=True  # Expand by default
                )

                if settings.threaded:
                    parent_at_depth[message.depth] = iid

            basename = os.path.basename(path)
            self.status_label.config(
                text=f"Loaded {basename} ({len(self.messages)} messages)"
            )
            if self.messages:
                first_item = self.message_list.get_children()[0]
                self.message_list.selection_set(first_item)
                # focus is needed for some themes
                self.message_list.focus(first_item)
                # Manually trigger selection event since selection_set doesn't fire it
                self.on_message_selected()
            else:
                self._set_detail_text("No messages found.")
        except Exception as exc:
            self.status_label.config(text="Error")
            messagebox.showerror("Failed to load QWK", str(exc))

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)
        self.detail_text.config(state=tk.DISABLED)

    def on_message_selected(self, _event: object | None = None) -> None:
        selected_items = self.message_list.selection()
        if not selected_items:
            return
        # Use the first selected item
        iid = selected_items[0]
        index = int(iid)
        self._set_detail_text(self._format_message_detail(index))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    QwkGuiApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
