import argparse
import datetime
import logging
import os
import tkinter as tk
from collections import Counter
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk, simpledialog

from pyqwk.core import (
    ProcessingSettings,
    _order_messages_by_thread,
    load_data,
    parse_messages,
    process_message,
    matches_filters,
    RE_QUOTE_PATTERN,
    get_allowed_conferences,
    _parse_qwk_date,
    resolve_output_format,
    write_messages,
    extract_binaries,
    calculate_archive_stats,
    render_stats_as_text,
    expand_paths,
    ConferenceMap,
)


class QwkGuiApp:
    @property
    def current_path(self) -> str | None:
        """Return the first path in current_paths for backward compatibility."""
        return self.current_paths[0] if self.current_paths else None

    @current_path.setter
    def current_path(self, value: str | None) -> None:
        if value is None:
            self.current_paths = []
        else:
            self.current_paths = [value]

    def __init__(self, root: tk.Tk, initial_path: str | None = None) -> None:
        self.root = root
        self.root.title("PyQWK Reader")
        self.root.geometry("1100x650")

        self.logger = logging.getLogger(__name__)

        self.messages = []
        self.board_dict: dict[int, str] = {}
        self.current_paths: list[str] = []
        self._cache = {}
        self.conf_mapping = {}

        self.column_labels = {
            "#0": "Subject",
            "Flags": "!",
            "Num": "Num",
            "From": "From",
            "To": "To",
            "Date": "Date",
            "Conference": "Conf",
            "BBS": "BBS",
        }

        self.clean_var = tk.BooleanVar(value=False)
        self.private_var = tk.BooleanVar(value=True)
        self.ansi_var = tk.BooleanVar(value=False)
        self.threaded_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.has_attach_var = tk.BooleanVar(value=False)
        self.mine_var = tk.BooleanVar(value=False)
        self.on_this_day_var = tk.BooleanVar(value=False)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self._search_timer: str | None = None

        self._build_menu()
        self._build_toolbar()
        self._build_status_bar()
        self._build_layout()

        if initial_path:
            self.current_paths = [initial_path]
            self.root.after(100, lambda: self.load_messages(self.current_paths))
        else:
            self.root.after(100, self._render_welcome_screen)

    def _show_list_context_menu(self, event: tk.Event) -> None:
        """Display a context menu for the message list."""
        iid = self.message_list.identify_row(event.y)
        if not iid:
            return

        self.message_list.selection_set(iid)
        self.message_list.focus(iid)

        try:
            idx = int(iid)
            msg = self.messages[idx]
        except (ValueError, IndexError):
            return

        menu = tk.Menu(self.root, tearoff=0)

        # Copy section
        menu.add_command(label="Copy Subject", command=lambda: self._copy_to_clipboard(msg.header.msgsubject.strip()))
        menu.add_command(label="Copy From", command=lambda: self._copy_to_clipboard(msg.header.msgfrom.strip()))
        menu.add_command(label="Copy To", command=lambda: self._copy_to_clipboard(msg.header.msgto.strip()))
        menu.add_command(label="Copy Num", command=lambda: self._copy_to_clipboard(str(msg.header.msgnum or "")))
        menu.add_separator()

        # Filter pivoting
        menu.add_command(label=f"Filter by Author: {msg.header.msgfrom.strip()[:20]}...",
                         command=lambda: self._pivot_filter(author=msg.header.msgfrom.strip()))

        conf_name = self.board_dict.get(msg.confnum, str(msg.confnum))
        menu.add_command(label=f"Filter by Conference: {conf_name[:20]}...",
                         command=lambda: self._pivot_filter(conf_num=msg.confnum))

        menu.post(event.x_root, event.y_root)

    def _show_text_context_menu(self, event: tk.Event) -> None:
        """Display a context menu for the detail viewer."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Copy", command=lambda: self.detail_text.event_generate("<<Copy>>"))
        menu.add_command(label="Select All", command=lambda: self.detail_text.tag_add("sel", "1.0", tk.END))
        menu.post(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy the given text to the system clipboard."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _pivot_filter(self, author: str | None = None, conf_num: int | None = None) -> None:
        """Update filters to pivot the view around a specific attribute."""
        if author:
            self.search_var.set(author)

        if conf_num is not None:
            # Find exact match in combobox
            for i, val in enumerate(self.conf_combo['values']):
                if val.startswith(f"{conf_num}:"):
                    self.conf_combo.current(i)
                    break

        self.reload_messages()

    def _block_text_input(self, event: tk.Event) -> str | None:
        """Block keyboard input in the detail view while allowing common shortcuts."""
        # Allow Control+C (copy) and Control+A (select all)
        if event.state & 0x4:  # Control mask
            if event.keysym.lower() in ('c', 'a'):
                return None
        # Allow navigation keys
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End'):
            return None
        return "break"

    def _render_welcome_screen(self) -> None:
        """Render a welcome screen with instructions and shortcuts."""
        self.detail_text.delete("1.0", tk.END)

        self.detail_text.insert(tk.END, "Welcome to PyQWK\n\n", "header_subject")

        self.detail_text.insert(tk.END, "Getting Started:\n", "header_label")
        self.detail_text.insert(tk.END, "Use Ctrl+O or the 'Open' button in the toolbar to load a message archive.\n\n", "body")

        self.detail_text.insert(tk.END, "Supported Formats:\n", "header_label")
        formats = "QWK, REP, JSON, CSV, SQLite (.db), XML, mbox, EML, and MESSAGES.DAT"
        self.detail_text.insert(tk.END, f"{formats}\n\n", "body")

        self.detail_text.insert(tk.END, "Keyboard Shortcuts:\n", "header_label")
        shortcuts = [
            ("Ctrl + O", "Open Archive"),
            ("Ctrl + S", "Export Current View"),
            ("Ctrl + I", "Archive Statistics"),
            ("Ctrl + F", "Search / Find"),
            ("Ctrl + G", "Go to Message Number"),
            ("Ctrl + Q", "Quit Application"),
            ("Esc", "Clear Search / Filters"),
            ("J / N", "Next Message"),
            ("K / P", "Previous Message"),
        ]

        for key, desc in shortcuts:
            self.detail_text.insert(tk.END, f"{key:<12}", "header_label")
            self.detail_text.insert(tk.END, f"{desc}\n", "body")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open Archive(s)...", command=self.open_file, accelerator="Ctrl+O"
        )
        file_menu.add_command(
            label="Open Folder...", command=self.open_folder
        )
        file_menu.add_command(
            label="Export Current View...",
            command=self.export_messages,
            accelerator="Ctrl+S",
        )
        file_menu.add_command(
            label="Statistics...",
            command=self.show_stats_window,
            accelerator="Ctrl+I",
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(
            label="Find",
            command=self._focus_search,
            accelerator="Ctrl+F",
        )
        edit_menu.add_command(
            label="Go to Message...",
            command=self.prompt_jump_to_message,
            accelerator="Ctrl+G",
        )
        edit_menu.add_command(
            label="Clear Search", command=self.clear_search, accelerator="Esc"
        )
        menubar.add_cascade(label="Edit", menu=edit_menu)

        self.root.config(menu=menubar)

        # Bind keyboard shortcuts
        self.root.bind("<Control-o>", self.open_file)
        self.root.bind("<Control-s>", self.export_messages)
        self.root.bind("<Control-i>", self.show_stats_window)
        self.root.bind("<Control-g>", self.prompt_jump_to_message)
        self.root.bind("<Control-q>", self.quit_app)
        self.root.bind("<Escape>", self.clear_search)
        self.root.bind("j", lambda e: self._select_relative_message(1))
        self.root.bind("n", lambda e: self._select_relative_message(1))
        self.root.bind("k", lambda e: self._select_relative_message(-1))
        self.root.bind("p", lambda e: self._select_relative_message(-1))

    def _get_all_tree_items(self) -> list[str]:
        """Return a flattened list of all item IDs currently visible in the treeview."""
        items = []

        def traverse(item_id):
            items.append(item_id)
            for child in self.message_list.get_children(item_id):
                traverse(child)

        for root_item in self.message_list.get_children(""):
            traverse(root_item)
        return items

    def _select_relative_message(self, delta: int, force: bool = False) -> None:
        """Move the selection up or down in the treeview display order."""
        if not self.messages:
            return

        # If the search entry has focus, don't hijack keyboard navigation unless forced
        if not force and self.root.focus_get() == self.search_entry:
            return

        all_items = self._get_all_tree_items()
        if not all_items:
            return

        current_selection = self.message_list.selection()
        if not current_selection:
            new_item = all_items[0]
        else:
            current_iid = current_selection[0]
            try:
                current_idx = all_items.index(current_iid)
                new_idx = max(0, min(len(all_items) - 1, current_idx + delta))
                new_item = all_items[new_idx]
            except ValueError:
                new_item = all_items[0]

        self.message_list.selection_set(new_item)
        self.message_list.see(new_item)
        self.message_list.focus(new_item)

    def clear_search(self, _event: object | None = None) -> None:
        self.search_var.set("")
        self.message_list.focus_set()

    def _focus_search(self, _event: object | None = None) -> None:
        """Focus the search bar and select all text for quick replacement."""
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)

    def clear_filters(self, _event: object | None = None) -> None:
        """Reset all filters to their default state."""
        try:
            self.conf_combo.current(0)
        except Exception:
            self.conf_combo.set("All Conferences")
        self.has_attach_var.set(False)
        self.mine_var.set(False)
        self.on_this_day_var.set(False)
        self.reload_messages()
        self.message_list.focus_set()

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
        actions_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(actions_frame, text="File:").pack(side=tk.LEFT)
        ttk.Button(actions_frame, text="Open", command=self.open_file).pack(side=tk.LEFT, padx=(5, 2))
        ttk.Button(actions_frame, text="Folder", command=self.open_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_frame, text="Export", command=self.export_messages).pack(side=tk.LEFT, padx=2)
        ttk.Button(actions_frame, text="Stats", command=self.show_stats_window).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Search group
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, width=20
        )
        self.search_entry.pack(side=tk.LEFT, padx=(5, 2))
        ttk.Checkbutton(
            search_frame, text="Regex", variable=self.regex_var, command=self.reload_messages
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="×", width=2, command=self.clear_search).pack(
            side=tk.LEFT
        )

        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Escape>", self.clear_search)
        self.search_entry.bind("<Up>", lambda e: self._select_relative_message(-1, force=True))
        self.search_entry.bind("<Down>", lambda e: self._select_relative_message(1, force=True))
        self.root.bind("<Control-f>", self._focus_search)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Filters group
        filters_frame = ttk.Frame(toolbar)
        filters_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(filters_frame, text="Filters:").pack(side=tk.LEFT)
        self.conf_combo = ttk.Combobox(filters_frame, state="readonly", width=25)
        self.conf_combo.pack(side=tk.LEFT, padx=(5, 2))

        for text, var in [
            ("Attachments", self.has_attach_var),
            ("My Messages", self.mine_var),
            ("On This Day", self.on_this_day_var),
        ]:
            ttk.Checkbutton(
                filters_frame, text=text, variable=var, command=self.reload_messages
            ).pack(side=tk.LEFT, padx=5)

        ttk.Button(filters_frame, text="×", width=2, command=self.clear_filters).pack(
            side=tk.LEFT
        )

        self.conf_combo.bind("<<ComboboxSelected>>", lambda e: self.reload_messages())
        self.conf_combo.bind("<Escape>", lambda e: self.clear_filters())

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Options group
        options_frame = ttk.Frame(toolbar)
        options_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(options_frame, text="View:").pack(side=tk.LEFT, padx=(0, 5))

        for text, var in [
            ("Threaded", self.threaded_var),
            ("Clean", self.clean_var),
            ("Remove Colors", self.ansi_var),
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

        # Treeview setup
        self.message_list = ttk.Treeview(
            list_frame,
            columns=("Flags", "Num", "From", "To", "Date", "Conference", "BBS"),
            selectmode="browse",
        )

        for col, label in self.column_labels.items():
            if col == "Num":
                header_anchor = tk.E
            elif col == "Flags":
                header_anchor = tk.CENTER
            else:
                header_anchor = tk.W

            self.message_list.heading(
                col,
                text=label,
                anchor=header_anchor,
                command=lambda c=col: self.sort_column(c, False),
            )

        self.message_list.column("#0", minwidth=200, width=300)
        self.message_list.column("Flags", minwidth=40, width=45, anchor=tk.CENTER)
        self.message_list.column("Num", minwidth=50, width=60, anchor=tk.E)
        self.message_list.column("From", minwidth=80, width=150)
        self.message_list.column("To", minwidth=80, width=150)
        self.message_list.column("Date", minwidth=80, width=120)
        self.message_list.column("Conference", minwidth=50, width=60)
        self.message_list.column("BBS", minwidth=80, width=100)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.message_list.yview
        )
        self.message_list.configure(yscroll=scrollbar.set)

        self.message_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Tags for visual hierarchy
        self.message_list.tag_configure("even", background="#f7f7f7")
        self.message_list.tag_configure("private", font=("TkDefaultFont", 10, "italic"))
        self.message_list.tag_configure(
            "mine", foreground="#0055aa", font=("TkDefaultFont", 10, "bold")
        )

        self.message_list.bind("<<TreeviewSelect>>", self.on_message_selected)

        # Context menu for list
        self.message_list.bind("<Button-3>", self._show_list_context_menu)
        self.message_list.bind("<Control-Button-1>", self._show_list_context_menu)

        self.detail_text = tk.Text(
            detail_frame,
            wrap=tk.WORD,
            tabs=("2.5c", "10c"),
            padx=15,
            pady=15,
            background="#ffffff",
            relief=tk.FLAT,
            borderwidth=0,
        )
        detail_scrollbar = ttk.Scrollbar(
            detail_frame, orient=tk.VERTICAL, command=self.detail_text.yview
        )
        self.detail_text.configure(yscrollcommand=detail_scrollbar.set)

        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.detail_text.config(state=tk.NORMAL)

        # Intercept key events to allow selection/copy but block editing
        self.detail_text.bind("<Key>", self._block_text_input)

        # Context menu for text
        self.detail_text.bind("<Button-3>", self._show_text_context_menu)
        self.detail_text.bind("<Control-Button-1>", self._show_text_context_menu)

        # Configure tags for visual hierarchy
        self.detail_text.tag_configure(
            "header_label", font=("TkDefaultFont", 10, "bold"), foreground="#444444"
        )
        self.detail_text.tag_configure("header_area", background="#f9f9f9")
        self.detail_text.tag_configure("header_value", font=("TkDefaultFont", 10))
        self.detail_text.tag_configure(
            "header_subject", font=("TkDefaultFont", 14, "bold")
        )
        self.detail_text.tag_configure("header_separator", foreground="#cccccc")
        self.detail_text.tag_configure("body", font=("TkFixedFont", 10))
        self.detail_text.tag_configure("quote", foreground="#4e9a06")
        self.detail_text.tag_configure(
            "search_highlight", background="#ffff00", foreground="#000000"
        )
        self.detail_text.tag_configure("link", foreground="blue", underline=True)
        self.detail_text.tag_bind(
            "link", "<Enter>", lambda e: self.detail_text.config(cursor="hand2")
        )
        self.detail_text.tag_bind(
            "link", "<Leave>", lambda e: self.detail_text.config(cursor="")
        )

    def _current_settings(self) -> ProcessingSettings:
        clean = self.clean_var.get()
        search_val = self.search_var.get().strip()
        if not search_val:
            search_val = None

        selected_conf_name = self.conf_combo.get()
        conferences = None
        if selected_conf_name and not selected_conf_name.startswith("All Conferences"):
            conf_id = self.conf_mapping.get(selected_conf_name)
            if conf_id is not None:
                conferences = [str(conf_id)]

        return ProcessingSettings(
            verbose=False,
            private=self.private_var.get(),
            no_header=True,
            truncate_signatures=clean,
            cut_quoting=clean,
            individual_files=False,
            threaded=self.threaded_var.get(),
            binaries_removal=clean,
            redact_pii=False,
            strip_ansi=clean or self.ansi_var.get(),
            format='text',
            separator='none',
            output_mode='stdout',
            output_path=None,
            encoding='cp437',
            regex=self.regex_var.get(),
            quiet=True,
            search_term=search_val if search_val else None,
            conferences=conferences,
            has_attachments=self.has_attach_var.get(),
            mine=self.mine_var.get(),
            on_this_day=self.on_this_day_var.get(),
        )

    def _render_message(self, message_index: int) -> None:
        """Render a message with rich formatting in the detail view."""
        message = self.messages[message_index]
        header = message.header
        conf_name = self.board_dict.get(header.confnum, str(header.confnum))

        self.detail_text.delete("1.0", tk.END)

        # Apply header area background
        header_start = "1.0"

        # Subject as a prominent title
        self.detail_text.insert(tk.END, (header.msgsubject.strip() or "(no subject)") + "\n\n", "header_subject")

        def insert_field(label: str, value: str, last_in_row: bool = False) -> None:
            self.detail_text.insert(tk.END, f"{label}: ", "header_label")
            self.detail_text.insert(tk.END, f"{value.strip()}\t", "header_value")
            if last_in_row:
                self.detail_text.insert(tk.END, "\n")

        insert_field("From", header.msgfrom.strip())
        insert_field("To", header.msgto.strip(), last_in_row=True)
        insert_field("Date", f"{header.msgdate} {header.msgtime}")
        insert_field("Conf", conf_name, last_in_row=True)

        if message.bbs_name:
            insert_field("BBS", message.bbs_name)
        if message.source_file:
            insert_field("Source", message.source_file, last_in_row=True)

        if header.msgnum is not None or message.refnum:
            if header.msgnum is not None:
                self.detail_text.insert(tk.END, "Msg #: ", "header_label")
                self.detail_text.insert(tk.END, f"{header.msgnum}\t", "header_value")
            if message.refnum:
                self.detail_text.insert(tk.END, "Ref #: ", "header_label")
                self.detail_text.insert(tk.END, str(message.refnum), "link")
                self.detail_text.insert(tk.END, "\t", "header_value")
                self.detail_text.tag_bind(
                    "link",
                    "<Button-1>",
                    lambda e, c=header.confnum, r=message.refnum: self.jump_to_message(c, r),
                )
            self.detail_text.insert(tk.END, "\n")

        if message.attachments:
            self.detail_text.insert(tk.END, "Attachments: ", "header_label")
            self.detail_text.insert(tk.END, ", ".join(message.attachments) + "\n", "header_value")

        header_end = self.detail_text.index(tk.INSERT)
        self.detail_text.tag_add("header_area", header_start, header_end)

        # Visual separator
        self.detail_text.insert(tk.END, "\n")
        separator = ttk.Separator(self.detail_text, orient=tk.HORIZONTAL)
        self.detail_text.window_create(tk.END, window=separator, stretch=True)
        self.detail_text.insert(tk.END, "\n\n")

        # Insert body with quote highlighting
        for line in message.text.splitlines(keepends=True):
            tags = ["body"]
            if RE_QUOTE_PATTERN.match(line):
                tags.append("quote")
            self.detail_text.insert(tk.END, line, tuple(tags))

        # Highlight search terms if present
        search_term = self.search_var.get().strip()
        if search_term:
            start_pos = "1.0"
            is_regex = self.regex_var.get()
            count_var = tk.IntVar()
            first_match_pos = None

            while True:
                try:
                    start_pos = self.detail_text.search(
                        search_term, start_pos, stopindex=tk.END,
                        nocase=True, regexp=is_regex, count=count_var
                    )
                except tk.TclError:
                    # Invalid regex
                    break
                if not start_pos:
                    break

                if first_match_pos is None:
                    first_match_pos = start_pos

                match_count = count_var.get()
                if match_count == 0:  # Avoid infinite loop on zero-width match
                    start_pos = f"{start_pos}+1c"
                    continue
                end_pos = f"{start_pos}+{match_count}c"
                self.detail_text.tag_add("search_highlight", start_pos, end_pos)
                start_pos = end_pos

            self.detail_text.tag_raise("search_highlight")
            if first_match_pos:
                self.detail_text.see(first_match_pos)

    def open_file(self, _event: object | None = None) -> None:
        filetypes = [
            ("All supported formats", "*.qwk *.rep *.json *.csv *.db *.sqlite *.xml *.mbox *.eml"),
            ("QWK archives", "*.qwk"),
            ("REP archives", "*.rep"),
            ("JSON archives", "*.json"),
            ("CSV archives", "*.csv"),
            ("SQLite databases", "*.db *.sqlite"),
            ("XML archives", "*.xml"),
            ("mbox files", "*.mbox"),
            ("EML files", "*.eml"),
            ("messages.dat", "messages.dat"),
            ("All files", "*.*"),
        ]
        paths = filedialog.askopenfilenames(
            title="Open Archive(s)",
            filetypes=filetypes,
        )
        if not paths:
            return
        self.current_paths = list(paths)
        self.load_messages(self.current_paths)

    def open_folder(self, _event: object | None = None) -> None:
        """Open all archives in a selected directory."""
        folder = filedialog.askdirectory(title="Select Folder with Archives")
        if not folder:
            return

        paths = expand_paths([folder])
        if not paths:
            messagebox.showinfo("Open Folder", "No supported message archives found in the selected folder.")
            return

        self.current_paths = paths
        self.load_messages(self.current_paths)

    def _on_search_changed(self, *args: object) -> None:
        """Handle search term changes with debouncing to improve UI responsiveness."""
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
        self._search_timer = self.root.after(250, self.reload_messages)

    def _on_search_enter(self, _event: object) -> None:
        """Execute search immediately when Enter is pressed."""
        self.reload_messages()
        self.message_list.focus_set()

    def reload_messages(self) -> None:
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
            self._search_timer = None

        if self.current_paths:
            self.load_messages(self.current_paths)

    def _reset_column_headers(self) -> None:
        """Reset all column headers to their original labels without sort indicators."""
        for col, label in self.column_labels.items():
            if col == "Num":
                header_anchor = tk.E
            elif col == "Flags":
                header_anchor = tk.CENTER
            else:
                header_anchor = tk.W

            self.message_list.heading(
                col,
                text=label,
                anchor=header_anchor,
                command=lambda c=col: self.sort_column(c, False)
            )

    def load_messages(self, paths: str | list[str]) -> None:
        if isinstance(paths, str):
            paths = [paths]

        # Save current state for potential restoration on failure
        old_messages = self.messages
        old_board_dict = self.board_dict
        old_cache = self._cache
        old_paths = self.current_paths

        try:
            self.status_label.config(text="Loading...")
            self.root.update_idletasks()

            # For now, we only cache single file loads. Multi-file loads are re-processed.
            # In a future version, we could cache per path.
            if len(paths) == 1:
                path = paths[0]
                # If opening a new file, clear stale conference mapping and selection
                if self._cache.get('path') != path:
                    self.conf_mapping = {}
                    self.conf_combo.set("All Conferences")
            else:
                self.conf_mapping = {}
                self.conf_combo.set("All Conferences")
                self._cache = {}

            settings = self._current_settings()

            # Capture current selection to restore it later
            selected_msg_key = None
            current_selection = self.message_list.selection()
            if current_selection:
                prev_iid = current_selection[0]
                try:
                    prev_index = int(prev_iid)
                    if 0 <= prev_index < len(self.messages):
                        m = self.messages[prev_index]
                        # Use conference and message number as a unique key
                        selected_msg_key = (m.header.confnum, m.header.msgnum, m.header.msgsubject, m.header.msgfrom)
                except (ValueError, IndexError):
                    pass

            # Reset headers to remove any previous sort indicators
            self._reset_column_headers()

            all_messages = []
            merged_board_dict = ConferenceMap()
            total_count = 0
            conf_counts = Counter()

            for path in paths:
                if len(paths) == 1 and self._cache.get('path') == path:
                    file_data = self._cache['file_data']
                    board_dict = self._cache['board_dict']
                else:
                    file_data, board_dict = load_data(path, self.logger, settings.encoding)

                bbs_info = getattr(board_dict, "bbs_info", None)
                if not merged_board_dict.bbs_info:
                    merged_board_dict.bbs_info = bbs_info
                user_name = bbs_info.user_name if bbs_info else None

                # Reconstruct/Discovery of conferences
                try:
                    found_confs = set()
                    if isinstance(file_data, list):
                        for parsed_message in file_data:
                            found_confs.add(parsed_message.confnum)
                    else:
                        for parsed_message in parse_messages(
                            file_data, None, settings.encoding, headers_only=True
                        ):
                            found_confs.add(parsed_message.confnum)

                    for cid in found_confs:
                        if cid not in board_dict:
                            board_dict[cid] = f"Conference {cid}"
                except Exception:
                    pass

                # Merge into global board dict
                for cid, name in board_dict.items():
                    if cid not in merged_board_dict:
                        merged_board_dict[cid] = name

                allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)

                if isinstance(file_data, list):
                    messages_to_process = file_data
                else:
                    messages_to_process = parse_messages(file_data, None, settings.encoding)

                # Create a settings object without conference filter for counting
                count_settings = replace(settings, conferences=None)

                for parsed_message in messages_to_process:
                    total_count += 1

                    # Add BBS and source file metadata
                    parsed_message = replace(
                        parsed_message,
                        bbs_name=bbs_info.name if bbs_info else None,
                        bbs_id=bbs_info.bbs_id if bbs_info else None,
                        source_file=os.path.basename(path)
                    )

                    # Check if message matches filters ignoring the conference filter itself
                    if matches_filters(parsed_message, count_settings, set(), user_name):
                        conf_counts[parsed_message.confnum] += 1

                        # Now apply the actual conference filter for the display list
                        if not settings.conferences or parsed_message.confnum in allowed_conferences:
                            processed_buffer = process_message(
                                parsed_message.text,
                                settings.truncate_signatures,
                                settings.cut_quoting,
                                settings.binaries_removal,
                                settings.redact_pii,
                                settings.strip_ansi,
                            )

                            # Ensure attachments are detected for the status icon
                            attachments = parsed_message.attachments
                            if attachments is None and parsed_message.text:
                                found = extract_binaries(parsed_message.text)
                                attachments = [name for name, data in found]

                            all_messages.append(replace(parsed_message, text=processed_buffer, attachments=attachments))

            # Update cache if it was a single file
            if len(paths) == 1:
                self._cache = {
                    'path': paths[0],
                    'file_data': file_data, # From the last iteration
                    'board_dict': board_dict
                }

            # Re-populate conference selector with dynamic counts
            total_filtered = sum(conf_counts.values())
            conf_list = [f"All Conferences ({total_filtered})"]
            new_conf_mapping = {}

            # Map for reverse lookup to preserve the current selection
            old_selection = self.conf_combo.get()
            selected_conf_id = self.conf_mapping.get(old_selection)
            new_selection = conf_list[0]

            for cid, name in sorted(merged_board_dict.items()):
                count = conf_counts.get(cid, 0)
                display_str = f"{cid}: {name} ({count})"
                conf_list.append(display_str)
                new_conf_mapping[display_str] = cid
                if cid == selected_conf_id:
                    new_selection = display_str

            self.conf_combo['values'] = conf_list
            self.conf_mapping = new_conf_mapping
            self.conf_combo.set(new_selection)

            if settings.threaded:
                all_messages = _order_messages_by_thread(all_messages)

            self.messages = all_messages
            self.board_dict = merged_board_dict
            self.current_paths = paths

            self.message_list.delete(*self.message_list.get_children())
            parent_at_depth = {-1: ""}

            # Identify the user's name for highlighting "mine" messages
            bbs_info = getattr(self.board_dict, "bbs_info", None)
            user_name = bbs_info.user_name if bbs_info else None

            for index, message in enumerate(self.messages):
                header = message.header
                conf_name = self.board_dict.get(header.confnum, str(header.confnum))
                subject = header.msgsubject.strip() or "(no subject)"

                flags = ""
                if header.is_private:
                    flags += "🔒"
                if message.attachments:
                    flags += "📎"

                parent_iid = ""
                if settings.threaded:
                    parent_iid = parent_at_depth.get(message.depth - 1, "")

                iid = str(index)
                item_tags = []
                if index % 2 != 0:
                    item_tags.append("even")
                if header.is_private:
                    item_tags.append("private")
                if user_name:
                    is_from_me = user_name.lower() in header.msgfrom.lower()
                    is_to_me = user_name.lower() in header.msgto.lower()
                    if is_from_me or is_to_me:
                        item_tags.append("mine")

                self.message_list.insert(
                    parent_iid,
                    tk.END,
                    iid=iid,
                    text=subject,
                    values=(
                        flags,
                        header.msgnum if header.msgnum is not None else "",
                        header.msgfrom.strip(),
                        header.msgto.strip(),
                        f"{header.msgdate} {header.msgtime}",
                        conf_name,
                        message.bbs_name or message.bbs_id or "",
                    ),
                    open=True,  # Expand by default
                    tags=tuple(item_tags)
                )

                if settings.threaded:
                    parent_at_depth[message.depth] = iid

            bbs_info = getattr(self.board_dict, "bbs_info", None)
            if bbs_info and bbs_info.name:
                source_display = f"{bbs_info.name} ({os.path.basename(path)})"
            else:
                source_display = os.path.basename(path)

            self.status_label.config(
                text=f"Showing {len(self.messages)} of {total_count} messages from {source_display if len(paths) == 1 else str(len(paths)) + ' archives'}"
            )
            self.root.title(f"{source_display if len(paths) == 1 else str(len(paths)) + ' archives'} - PyQWK Reader")

            # Restore selection if possible
            new_iid_to_select = None
            if selected_msg_key:
                for i, m in enumerate(self.messages):
                    if (m.header.confnum, m.header.msgnum, m.header.msgsubject, m.header.msgfrom) == selected_msg_key:
                        new_iid_to_select = str(i)
                        break

            if self.messages:
                if new_iid_to_select and self.message_list.exists(new_iid_to_select):
                    item_to_select = new_iid_to_select
                else:
                    item_to_select = self.message_list.get_children()[0]

                self.message_list.selection_set(item_to_select)
                self.message_list.focus(item_to_select)
                self.message_list.see(item_to_select)
            else:
                self._set_detail_text("No messages found.")
        except Exception as exc:
            # Restore previous state on failure
            self.messages = old_messages
            self.board_dict = old_board_dict
            self._cache = old_cache
            self.current_paths = old_paths
            
            # Reset status and show error
            if self.current_paths:
                source_display = self.root.title().split(" - ")[0]
                self.status_label.config(
                    text=f"Showing {len(self.messages)} messages from {source_display}"
                )
            else:
                self.status_label.config(text="Ready")
                self.root.title("PyQWK Reader")
                
            messagebox.showerror("Failed to load QWK", str(exc))

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)

    def export_messages(self, _event: object | None = None) -> None:
        """Export the currently filtered and sorted messages to a file."""
        if not self.messages:
            messagebox.showwarning("Export", "No messages to export.")
            return

        filetypes = [
            ("Text files", "*.txt"),
            ("HTML files", "*.html"),
            ("Markdown files", "*.md"),
            ("JSON files", "*.json"),
            ("mbox files", "*.mbox"),
            ("EML files", "*.eml"),
            ("CSV files", "*.csv"),
            ("SQLite database", "*.db"),
            ("XML files", "*.xml"),
            ("All files", "*.*"),
        ]

        path = filedialog.asksaveasfilename(
            title="Export Messages",
            filetypes=filetypes,
            defaultextension=".txt",
        )

        if not path:
            return

        try:
            # Determine format from extension
            fmt = resolve_output_format(None, path, "file")

            # Update settings for export
            settings = self._current_settings()
            settings = replace(
                settings,
                format=fmt,
                output_mode="file",
                output_path=path,
                no_header=False,  # We want headers in the export
            )

            # Use messages in their current display order from the treeview
            ordered_item_ids = self._get_all_tree_items()
            
            # Prepare messages for export (add headers if needed, clean text)
            export_list = []
            bbs_info = getattr(self.board_dict, "bbs_info", None)
            
            for iid in ordered_item_ids:
                try:
                    idx = int(iid)
                    msg = self.messages[idx]
                    
                    # Clean the body text using standard processing
                    cleaned_body = process_message(
                        msg.text,
                        settings.truncate_signatures,
                        settings.cut_quoting,
                        settings.binaries_removal,
                        settings.redact_pii,
                        settings.strip_ansi,
                    )
                    
                    # If text format and headers requested, prepend them
                    if settings.format == 'text' and not settings.no_header:
                        header_text = msg.header.format_text(
                            self.board_dict,
                            settings.verbose,
                            include_separator=True,
                            attachments=msg.attachments,
                        )
                        processed_text = header_text + cleaned_body
                    else:
                        processed_text = cleaned_body
                        
                    # Create a processed version of the message for the writer
                    export_msg = replace(msg, text=processed_text)
                    export_list.append(export_msg)
                except (ValueError, IndexError):
                    continue

            write_messages(export_list, path, settings, bbs_info, self.board_dict)

            messagebox.showinfo(
                "Export Successful",
                f"Successfully exported {len(export_list)} messages to {os.path.basename(path)}",
            )
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    def prompt_jump_to_message(self, _event: object | None = None) -> None:
        """Prompt the user for a message number and jump to it."""
        if not self.messages:
            return

        msgnum = simpledialog.askinteger("Jump to Message", "Enter message number:")
        if msgnum is None:
            return

        # Try to find it in the current conference first if something is selected
        current_conf = None
        current_selection = self.message_list.selection()
        if current_selection:
            try:
                idx = int(current_selection[0])
                current_conf = self.messages[idx].header.confnum
            except (ValueError, IndexError):
                pass

        if current_conf is not None:
            for i, m in enumerate(self.messages):
                if m.header.msgnum == msgnum and m.header.confnum == current_conf:
                    self._select_by_index(i)
                    return

        # Otherwise just find the first match
        for i, m in enumerate(self.messages):
            if m.header.msgnum == msgnum:
                self._select_by_index(i)
                return

        messagebox.showinfo(
            "Not Found", f"Message #{msgnum} was not found in the current view."
        )

    def _select_by_index(self, index: int) -> None:
        """Select a message by its index in the current message list."""
        iid = str(index)
        if self.message_list.exists(iid):
            self.message_list.selection_set(iid)
            self.message_list.see(iid)
            self.message_list.focus(iid)

    def jump_to_message(self, confnum: int, msgnum: int) -> None:
        """Find and select a message by conference and message number."""
        for i, m in enumerate(self.messages):
            if m.header.confnum == confnum and m.header.msgnum == msgnum:
                self._select_by_index(i)
                return
        messagebox.showinfo(
            "Not Found",
            f"Referenced message #{msgnum} was not found in the current view.",
        )

    def show_stats_window(self, _event: object | None = None) -> None:
        """Calculate and display statistics for the current archives and filters."""
        if not self.current_paths:
            messagebox.showwarning("Statistics", "Please open an archive first.")
            return

        try:
            self.status_label.config(text="Calculating statistics...")
            self.root.update_idletasks()

            settings = self._current_settings()
            # Ensure stats are calculated correctly by using the same logic as the CLI
            # calculate_archive_stats now expects a list of paths
            stats = calculate_archive_stats(self.current_paths, settings, self.logger)

            # Create a new window for the report
            stats_win = tk.Toplevel(self.root)
            title_suffix = os.path.basename(self.current_paths[0]) if len(self.current_paths) == 1 else f"{len(self.current_paths)} archives"
            stats_win.title(f"Statistics - {title_suffix}")
            stats_win.geometry("750x700")

            main_frame = ttk.Frame(stats_win, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            txt = tk.Text(main_frame, font=("TkFixedFont", 10), wrap=tk.NONE, padx=10, pady=10)
            sb_y = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=txt.yview)
            sb_x = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=txt.xview)
            txt.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

            # Footer for close button
            footer = ttk.Frame(stats_win, padding=(10, 5))
            footer.pack(side=tk.BOTTOM, fill=tk.X)
            ttk.Button(footer, text="Close", command=stats_win.destroy).pack(side=tk.RIGHT)

            txt.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            sb_y.pack(side=tk.RIGHT, fill=tk.Y, before=txt)
            sb_x.pack(side=tk.BOTTOM, fill=tk.X)

            # Define tags for statistics window
            txt.tag_configure("h1", font=("TkDefaultFont", 14, "bold"), foreground="#0055aa")
            txt.tag_configure("h2", font=("TkDefaultFont", 11, "bold"), foreground="#444444")
            txt.tag_configure("bold", font=("TkFixedFont", 10, "bold"))
            txt.tag_configure("dim", foreground="#888888")
            txt.tag_configure("cyan_bar", background="#00aaaa", foreground="#ffffff")
            txt.tag_configure("info_label", font=("TkDefaultFont", 10, "bold"), foreground="#666666")

            # Rendering logic
            display_name = os.path.basename(stats['file']) if len(self.current_paths) == 1 else "Multiple Archives"
            txt.insert(tk.END, f"Statistics for: {display_name}\n\n", "h1")

            def insert_info(label, value):
                txt.insert(tk.END, f"  {label:<15}: ", "info_label")
                txt.insert(tk.END, f"{value}\n")

            insert_info("Messages", f"{stats['matching_messages']} matching / {stats['total_messages']} total")
            if stats['attachments_count'] > 0:
                insert_info("Attachments", f"{stats['attachments_count']} files detected")
            if stats['dates']['earliest']:
                earliest = datetime.datetime.fromisoformat(stats['dates']['earliest']).strftime('%Y-%m-%d')
                latest = datetime.datetime.fromisoformat(stats['dates']['latest']).strftime('%Y-%m-%d')
                insert_info("Date Range", f"{earliest} to {latest}")
            insert_info("Private", f"{stats['private_count']} messages")

            txt.insert(tk.END, "\nVitality & Content\n", "h2")
            insert_info("Reply Rate", f"{stats['reply_rate']}% ({stats['reply_count']} replies)")
            insert_info("Avg Length", f"{int(stats['avg_message_length'])} characters")

            def render_gui_bar_chart(title, data):
                if not data:
                    return
                txt.insert(tk.END, f"\n{title}\n", "h2")
                max_count = max(count for _, count in data) if data else 0
                for label, count in data:
                    truncated_label = f"{str(label)[:25]:<25}"
                    count_str = f"{count:4}"
                    bar_len = int(count * 40 / max_count) if max_count > 0 else 0

                    txt.insert(tk.END, "    ", "")
                    txt.insert(tk.END, truncated_label, "dim")
                    txt.insert(tk.END, " : ", "")
                    txt.insert(tk.END, count_str, "bold")
                    txt.insert(tk.END, " ", "")
                    if bar_len > 0:
                        txt.insert(tk.END, " " * bar_len, "cyan_bar")
                    txt.insert(tk.END, "\n")

            if stats['year_distribution']:
                items = [(y, c) for y, c in sorted(stats['year_distribution'].items())]
                render_gui_bar_chart('Yearly Activity', items)

            if stats['month_distribution'] and len(stats['month_distribution']) <= 24:
                items = [(m, c) for m, c in sorted(stats['month_distribution'].items())]
                render_gui_bar_chart('Monthly Activity', items)

            render_gui_bar_chart('Top Authors', [(a["name"], a["count"]) for a in stats['authors']])
            render_gui_bar_chart('Top Recipients', [(r["name"], r["count"]) for r in stats['recipients']])

            if stats.get('bbses'):
                render_gui_bar_chart('Top BBSes', [(b["name"], b["count"]) for b in stats['bbses']])

            if stats['conferences']:
                items = [(f"{c['number']:3} {c['name']}", c["count"]) for c in stats['conferences']]
                render_gui_bar_chart('Top Conferences', items)

            render_gui_bar_chart('Top Subjects', [(s["subject"], s["count"]) for s in stats['subjects']])
            render_gui_bar_chart('Top Keywords', [(k["word"], k["count"]) for k in stats['keywords']])

            if stats['day_of_week']:
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                items = [(d, stats['day_of_week'].get(d, 0)) for d in days]
                render_gui_bar_chart('Day of Week Distribution', items)

            if stats['hour_of_day']:
                items = [(f"{h:02}:00", stats['hour_of_day'].get(str(h), 0)) for h in range(24)]
                render_gui_bar_chart('Hourly Distribution', items)

            txt.config(state=tk.DISABLED)

            # Re-set status
            source_display = self.root.title().split(" - ")[0]
            self.status_label.config(
                text=f"Showing {len(self.messages)} messages from {source_display}"
            )

        except Exception as e:
            self.status_label.config(text="Error calculating statistics")
            messagebox.showerror("Statistics Error", str(e))

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

    def _apply_zebra_striping(self) -> None:
        """Re-apply alternating 'even' tags to all items in their current display order."""
        def traverse(item_id, count):
            current_tags = list(self.message_list.item(item_id, "tags"))
            # Filter out the 'even' tag to start fresh
            new_tags = [t for t in current_tags if t != "even"]

            if count % 2 != 0:
                new_tags.append("even")

            self.message_list.item(item_id, tags=tuple(new_tags))
            count += 1
            for child in self.message_list.get_children(item_id):
                count = traverse(child, count)
            return count

        current_count = 0
        for root_item in self.message_list.get_children(""):
            current_count = traverse(root_item, current_count)

    def sort_column(self, col: str, reverse: bool) -> None:
        """Sort the treeview contents by the given column."""
        items = []
        try:
            items = [
                (self.message_list.set(k, col), k)
                if col != "#0"
                else (self.message_list.item(k, "text"), k)
                for k in self.message_list.get_children("")
            ]
            if not items:
                return
            if col == "Num":
                items.sort(key=lambda t: int(t[0]) if t[0] and str(t[0]).isdigit() else 0, reverse=reverse)
            elif col == "Date":
                # QWK date is MM-DD-YY HH:MM. Sort chronologically.
                def get_date_key(date_str):
                    parts = date_str.split()
                    date_part = parts[0] if len(parts) > 0 else ""
                    time_part = parts[1] if len(parts) > 1 else "00:00"
                    return _parse_qwk_date(date_part, time_part)
                items.sort(key=lambda item_tuple: get_date_key(item_tuple[0]), reverse=reverse)
            else:
                items.sort(key=lambda t: t[0].lower(), reverse=reverse)
        except Exception:
            # Fallback if sorting fails
            if items:
                items.sort(key=lambda t: t[0], reverse=reverse)

        # Rearrange items in sorted positions
        for index, (_, k) in enumerate(items):
            self.message_list.move(k, "", index)

        # Re-apply alternating tags after sorting to maintain zebra striping
        self._apply_zebra_striping()

        # Update all headings to show indicators and set correct toggle commands
        for c in self.column_labels:
            label = self.column_labels[c]
            if c == col:
                label += " ▼" if reverse else " ▲"
                # If we just sorted this column, the next click should reverse it
                next_reverse = not reverse
            else:
                # If we click a different column, it should start as ascending
                next_reverse = False

            if c == "Num":
                header_anchor = tk.E
            elif c == "Flags":
                header_anchor = tk.CENTER
            else:
                header_anchor = tk.W

            self.message_list.heading(
                c,
                text=label,
                anchor=header_anchor,
                command=lambda _c=c, _r=next_reverse: self.sort_column(_c, _r)
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="PyQWK Graphical Reader")
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to a supported message archive (QWK, REP, JSON, CSV, XML, MBOX, EML, or SQLite) or a MESSAGES.DAT file."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    QwkGuiApp(root, initial_path=args.path)
    root.mainloop()


if __name__ == '__main__':
    main()
