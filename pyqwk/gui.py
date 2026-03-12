import argparse
import logging
import os
import tkinter as tk
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
)


class QwkGuiApp:
    def __init__(self, root: tk.Tk, initial_path: str | None = None) -> None:
        self.root = root
        self.root.title("PyQWK Reader")
        self.root.geometry("1100x650")

        self.logger = logging.getLogger(__name__)

        self.messages = []
        self.board_dict: dict[int, str] = {}
        self.current_path: str | None = None
        self._cache = {}
        self.conf_mapping = {}

        self.column_labels = {
            "#0": "Subject",
            "Num": "Num",
            "From": "From",
            "To": "To",
            "Date": "Date",
            "Conference": "Conference",
        }

        self.clean_var = tk.BooleanVar(value=False)
        self.private_var = tk.BooleanVar(value=True)
        self.redact_var = tk.BooleanVar(value=False)
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
            self.current_path = initial_path
            self.root.after(100, lambda: self.load_messages(initial_path))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open...", command=self.open_file, accelerator="Ctrl+O"
        )
        file_menu.add_command(
            label="Export Current View...",
            command=self.export_messages,
            accelerator="Ctrl+S",
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
        ttk.Button(actions_frame, text="Export", command=self.export_messages).pack(side=tk.LEFT, padx=2)

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
            ("Hide Personal Info", self.redact_var),
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
            columns=("Num", "From", "To", "Date", "Conference"),
            selectmode="browse",
        )

        for col, label in self.column_labels.items():
            header_anchor = tk.E if col == "Num" else tk.W
            self.message_list.heading(
                col,
                text=label,
                anchor=header_anchor,
                command=lambda c=col: self.sort_column(c, False),
            )

        self.message_list.column("#0", minwidth=200, width=300)
        self.message_list.column("Num", minwidth=50, width=60, anchor=tk.E)
        self.message_list.column("From", minwidth=80, width=120)
        self.message_list.column("To", minwidth=80, width=120)
        self.message_list.column("Date", minwidth=80, width=120)
        self.message_list.column("Conference", minwidth=80, width=100)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.message_list.yview
        )
        self.message_list.configure(yscroll=scrollbar.set)

        self.message_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Alternating row colors for better visual hierarchy
        self.message_list.tag_configure("even", background="#f7f7f7")

        self.message_list.bind("<<TreeviewSelect>>", self.on_message_selected)

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
        self.detail_text.config(state=tk.DISABLED)

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

        selected_conf_name = self.conf_combo.get()
        conferences = None
        if selected_conf_name and selected_conf_name != "All Conferences":
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
            redact_pii=self.redact_var.get(),
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

        self.detail_text.config(state=tk.NORMAL)
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

        self.detail_text.config(state=tk.DISABLED)

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
        path = filedialog.askopenfilename(
            title="Open QWK archive",
            filetypes=filetypes,
        )
        if not path:
            return
        self.current_path = path
        self.load_messages(path)

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

        if self.current_path:
            self.load_messages(self.current_path)

    def _reset_column_headers(self) -> None:
        """Reset all column headers to their original labels without sort indicators."""
        for col, label in self.column_labels.items():
            header_anchor = tk.E if col == "Num" else tk.W
            self.message_list.heading(
                col,
                text=label,
                anchor=header_anchor,
                command=lambda c=col: self.sort_column(c, False)
            )

    def load_messages(self, path: str) -> None:
        # Save current state for potential restoration on failure
        old_messages = self.messages
        old_board_dict = self.board_dict
        old_cache = self._cache
        old_path = self.current_path

        try:
            self.status_label.config(text="Loading...")
            self.root.update_idletasks()
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

            # Cache file data to improve responsiveness during filtering
            if self._cache.get('path') != path:
                file_data, board_dict = load_data(path, self.logger, settings.encoding)

                # Ensure all conferences present in the data are in the dropdown,
                # even if CONTROL.DAT is missing or incomplete.
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

                    for cid in sorted(found_confs):
                        if cid not in board_dict:
                            board_dict[cid] = f"Conference {cid}"
                except Exception:
                    # If discovery fails, we proceed with whatever load_data found
                    pass

                self._cache = {
                    'path': path,
                    'file_data': file_data,
                    'board_dict': board_dict
                }
                # Populate conference selector
                conf_list = ["All Conferences"]
                for cid, name in sorted(board_dict.items()):
                    conf_list.append(f"{cid}: {name}")
                self.conf_combo['values'] = conf_list
                self.conf_combo.set("All Conferences")
                self.conf_mapping = {f"{cid}: {name}": cid for cid, name in board_dict.items()}

            file_data = self._cache['file_data']
            board_dict = self._cache['board_dict']

            messages = []
            total_count = 0
            allowed_conferences = get_allowed_conferences(settings.conferences, board_dict)
            bbs_info = getattr(board_dict, "bbs_info", None)
            user_name = bbs_info.user_name if bbs_info else None

            if isinstance(file_data, list):
                messages_to_process = file_data
            else:
                messages_to_process = parse_messages(file_data, None, settings.encoding)

            for parsed_message in messages_to_process:
                total_count += 1
                if not matches_filters(parsed_message, settings, allowed_conferences, user_name):
                    continue

                processed_buffer = process_message(
                    parsed_message.text,
                    settings.truncate_signatures,
                    settings.cut_quoting,
                    settings.binaries_removal,
                    settings.redact_pii,
                    settings.strip_ansi,
                )
                messages.append(replace(parsed_message, text=processed_buffer))

            if settings.threaded:
                messages = _order_messages_by_thread(messages)

            self.messages = messages
            self.board_dict = board_dict
            self.current_path = path

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
                tags = ("even",) if index % 2 != 0 else ()
                self.message_list.insert(
                    parent_iid,
                    tk.END,
                    iid=iid,
                    text=subject,
                    values=(
                        header.msgnum if header.msgnum is not None else "",
                        header.msgfrom.strip(),
                        header.msgto.strip(),
                        f"{header.msgdate} {header.msgtime}",
                        conf_name,
                    ),
                    open=True,  # Expand by default
                    tags=tags
                )

                if settings.threaded:
                    parent_at_depth[message.depth] = iid

            bbs_info = getattr(self.board_dict, "bbs_info", None)
            if bbs_info and bbs_info.name:
                source_display = f"{bbs_info.name} ({os.path.basename(path)})"
            else:
                source_display = os.path.basename(path)

            self.status_label.config(
                text=f"Showing {len(self.messages)} of {total_count} messages from {source_display}"
            )
            self.root.title(f"{source_display} - PyQWK Reader")

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
            self.current_path = old_path
            
            # Reset status and show error
            if self.current_path:
                source_display = self.root.title().split(" - ")[0]
                self.status_label.config(
                    text=f"Showing {len(self.messages)} messages from {source_display}"
                )
            else:
                self.status_label.config(text="Ready")
                self.root.title("PyQWK Reader")
                
            messagebox.showerror("Failed to load QWK", str(exc))

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)
        self.detail_text.config(state=tk.DISABLED)

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

            write_messages(export_list, path, settings, bbs_info)

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
            tags = ("even",) if count % 2 != 0 else ()
            self.message_list.item(item_id, tags=tags)
            count += 1
            for child in self.message_list.get_children(item_id):
                count = traverse(child, count)
            return count

        current_count = 0
        for root_item in self.message_list.get_children(""):
            current_count = traverse(root_item, current_count)

    def sort_column(self, col: str, reverse: bool) -> None:
        """Sort the treeview contents by the given column."""
        l = []
        try:
            l = [
                (self.message_list.set(k, col), k)
                if col != "#0"
                else (self.message_list.item(k, "text"), k)
                for k in self.message_list.get_children("")
            ]
            if not l:
                return
            if col == "Num":
                l.sort(key=lambda t: int(t[0]) if t[0] and str(t[0]).isdigit() else 0, reverse=reverse)
            elif col == "Date":
                # QWK date is MM-DD-YY HH:MM. Sort chronologically.
                def get_date_key(date_str):
                    parts = date_str.split()
                    date_part = parts[0] if len(parts) > 0 else ""
                    time_part = parts[1] if len(parts) > 1 else "00:00"
                    return _parse_qwk_date(date_part, time_part)
                l.sort(key=lambda item_tuple: get_date_key(item_tuple[0]), reverse=reverse)
            else:
                l.sort(key=lambda t: t[0].lower(), reverse=reverse)
        except Exception:
            # Fallback if sorting fails
            if l:
                l.sort(key=lambda t: t[0], reverse=reverse)

        # Rearrange items in sorted positions
        for index, (_, k) in enumerate(l):
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

            header_anchor = tk.E if c == "Num" else tk.W
            self.message_list.heading(
                c,
                text=label,
                anchor=header_anchor,
                command=lambda _c=c, _r=next_reverse: self.sort_column(_c, _r)
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="PyQWK Graphical Reader")
    parser.add_argument(
        "path", nargs="?", help="Path to a QWK archive or messages.dat file"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    QwkGuiApp(root, initial_path=args.path)
    root.mainloop()


if __name__ == '__main__':
    main()
