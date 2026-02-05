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
    matches_filters,
    get_allowed_conferences,
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

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.reload_messages())

        self._build_menu()
        self._build_toolbar()
        self._build_status_bar()
        self._build_layout()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open...", command=self.open_file, accelerator="Ctrl+O"
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        # Bind keyboard shortcuts
        self.root.bind("<Control-o>", self.open_file)
        self.root.bind("<Control-q>", self.quit_app)

    def quit_app(self, _event: object | None = None) -> None:
        self.root.quit()

    def _build_status_bar(self) -> None:
        status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(status_bar, text="Ready", padding=(5, 2))
        self.status_label.pack(side=tk.LEFT)

        ttk.Sizegrip(status_bar).pack(side=tk.RIGHT)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(10, 5))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Actions group
        actions_frame = ttk.Frame(toolbar)
        actions_frame.pack(side=tk.LEFT)
        ttk.Button(actions_frame, text="Open QWK", command=self.open_file).pack(side=tk.LEFT)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Search group
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.LEFT)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=(5, 2))
        ttk.Button(
            search_frame, text="×", width=2, command=lambda: self.search_var.set("")
        ).pack(side=tk.LEFT)
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus_set())

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Options group
        options_frame = ttk.Frame(toolbar)
        options_frame.pack(side=tk.LEFT)

        for text, var in [
            ("Clean", self.clean_var),
            ("Include Private", self.private_var),
            ("Redact PII", self.redact_var),
            ("Threaded", self.threaded_var),
        ]:
            ttk.Checkbutton(
                options_frame, text=text, variable=var, command=self.reload_messages
            ).pack(side=tk.LEFT, padx=5)

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
        self.message_list.heading(
            "#0",
            text="Subject",
            anchor=tk.W,
            command=lambda: self.sort_column("#0", False),
        )
        self.message_list.heading(
            "From",
            text="From",
            anchor=tk.W,
            command=lambda: self.sort_column("From", False),
        )
        self.message_list.heading(
            "Date",
            text="Date",
            anchor=tk.W,
            command=lambda: self.sort_column("Date", False),
        )
        self.message_list.heading(
            "Conference",
            text="Conference",
            anchor=tk.W,
            command=lambda: self.sort_column("Conference", False),
        )

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

        # Configure tags for visual hierarchy
        self.detail_text.tag_configure(
            "header_label", font=("TkDefaultFont", 9, "bold"), foreground="#555555"
        )
        self.detail_text.tag_configure("header_value", font=("TkDefaultFont", 9))
        self.detail_text.tag_configure("body", font=("TkFixedFont", 10))

    def _current_settings(self) -> ProcessingSettings:
        clean = self.clean_var.get()
        search_val = self.search_var.get().strip()
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
            search_term=search_val if search_val else None,
        )

    def _render_message(self, message_index: int) -> None:
        """Render a message with rich formatting in the detail view."""
        message = self.messages[message_index]
        header = message.header
        conf_name = self.board_dict.get(header.confnum, str(header.confnum))

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        def insert_header(label: str, value: str) -> None:
            self.detail_text.insert(tk.END, f"{label}: ", "header_label")
            self.detail_text.insert(tk.END, f"{value}\n", "header_value")

        insert_header("Conference", conf_name)
        insert_header("Date", f"{header.msgdate} {header.msgtime}")
        insert_header("From", header.msgfrom)
        insert_header("To", header.msgto)
        insert_header("Subject", header.msgsubject)

        if header.msgnum is not None:
            insert_header("Message #", str(header.msgnum))
        if message.refnum:
            insert_header("Reference #", str(message.refnum))

        self.detail_text.insert(tk.END, "\n", "header_value")
        self.detail_text.insert(tk.END, message.text, "body")

        self.detail_text.config(state=tk.DISABLED)

    def open_file(self, _event: object | None = None) -> None:
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
            allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)
            for parsed_message in parse_messages(file_data, None, settings.encoding):
                if not matches_filters(parsed_message, settings, allowed_conferences):
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
        try:
            index = int(iid)
            self._render_message(index)
        except ValueError:
            # Handle cases where iid is not an integer (e.g., if we change ID generation)
            pass

    def sort_column(self, col: str, reverse: bool) -> None:
        """Sort the treeview contents by the given column."""
        if self.threaded_var.get():
            # Sorting breaks the tree structure visualization, so we disable it for now
            # or we could just sort top-level items. For simplicity, we skip if threaded.
            return

        l = [
            (self.message_list.set(k, col), k)
            if col != "#0"
            else (self.message_list.item(k, "text"), k)
            for k in self.message_list.get_children("")
        ]

        try:
            l.sort(key=lambda t: t[0].lower(), reverse=reverse)
        except Exception:
            # Fallback if sorting fails
            l.sort(key=lambda t: t[0], reverse=reverse)

        # Rearrange items in sorted positions
        for index, (_, k) in enumerate(l):
            self.message_list.move(k, "", index)

        # Update heading to toggle reverse flag
        self.message_list.heading(
            col, command=lambda: self.sort_column(col, not reverse)
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    QwkGuiApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
