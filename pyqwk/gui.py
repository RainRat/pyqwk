import argparse
import datetime
import hashlib
import logging
import os
import webbrowser
import tkinter as tk
from tkinter import font
from collections import Counter
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk, simpledialog

from pyqwk.core import (
    ProcessingSettings,
    _order_messages_by_thread,
    format_size,
    load_data,
    parse_messages,
    process_message,
    matches_filters,
    RE_QUOTE_PATTERN,
    RE_URL_PATTERN,
    RE_EMAIL_PATTERN,
    RE_PHONE_PATTERN,
    RE_MSG_LINK_PATTERN,
    get_allowed_conferences,
    _parse_qwk_date,
    resolve_output_format,
    write_messages,
    extract_binaries,
    calculate_archive_stats,
    render_stats_as_text,  # noqa: F401
    expand_paths,
    ConferenceMap,
    _normalize_subject,
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

    def __init__(self, root: tk.Tk, initial_paths: list[str] | None = None) -> None:
        self.root = root
        self.root.title("PyQWK Reader")
        self.root.geometry("1100x650")

        self.logger = logging.getLogger(__name__)

        self.messages = []
        self.total_msg_count = 0
        self.source_display_name = ""
        self.board_dict: dict[int, str] = {}
        self.current_paths: list[str] = []
        self._cache = {}
        self.conf_mapping = {}
        self.bbs_mapping = {}
        self._search_matches = []
        self._current_match_idx = -1
        self._pending_match_idx: int | None = None

        self.column_labels = {
            "#0": "Subject",
            "Flags": "Flags",
            "Num": "Num",
            "From": "From",
            "To": "To",
            "Date": "Date",
            "Size": "Size",
            "Conference": "Conference",
            "BBS": "BBS",
        }

        self.clean_var = tk.BooleanVar(value=False)
        self.wrap_var = tk.BooleanVar(value=True)
        self.private_var = tk.BooleanVar(value=True)
        self.ansi_var = tk.BooleanVar(value=False)
        self.threaded_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.has_attach_var = tk.BooleanVar(value=False)
        self.mine_var = tk.BooleanVar(value=False)
        self.on_this_day_var = tk.BooleanVar(value=False)
        self.has_links_var = tk.BooleanVar(value=False)
        self.has_emails_var = tk.BooleanVar(value=False)
        self.has_phones_var = tk.BooleanVar(value=False)
        self.has_ansi_var = tk.BooleanVar(value=False)
        self.redact_pii_var = tk.BooleanVar(value=False)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.exclude_var = tk.StringVar()
        self.exclude_var.trace_add("write", self._on_search_changed)
        self._search_timer: str | None = None

        # Create custom styles
        self.style = ttk.Style()
        self.style.configure(
            "GroupHeader.TLabel",
            font=font.Font(family="TkDefaultFont", size=9, weight="bold"),
        )

        self._build_menu()
        self._build_toolbar()
        self._build_status_bar()
        self._build_layout()

        if initial_paths:
            self.current_paths = initial_paths
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
        orig_subject = msg.header.msgsubject.strip()
        orig_from = msg.header.msgfrom.strip()
        orig_to = msg.header.msgto.strip()
        orig_num = str(msg.header.msgnum or "")

        menu.add_command(
            label="Copy Subject",
            command=lambda s=orig_subject: self._copy_to_clipboard(s),
        )
        menu.add_command(
            label="Copy From",
            command=lambda f=orig_from: self._copy_to_clipboard(f),
        )
        menu.add_command(
            label="Copy To",
            command=lambda t=orig_to: self._copy_to_clipboard(t),
        )
        menu.add_command(
            label="Copy Num",
            command=lambda n=orig_num: self._copy_to_clipboard(n),
        )
        menu.add_separator()

        # Filter pivoting
        author_label = (orig_from[:20] + "...") if len(orig_from) > 20 else orig_from
        menu.add_command(
            label=f"Filter by Author: {author_label}",
            command=lambda a=orig_from: self._pivot_filter(author=a),
        )
        menu.add_command(
            label="Exclude Author",
            command=lambda a=orig_from: self._pivot_filter(exclude_author=a),
        )

        subj_label = (
            (orig_subject[:20] + "...") if len(orig_subject) > 20 else orig_subject
        )
        menu.add_command(
            label=f"Filter by Subject: {subj_label}",
            command=lambda s=orig_subject: self._pivot_filter(subject=s),
        )
        menu.add_command(
            label="Exclude Subject",
            command=lambda s=orig_subject: self._pivot_filter(exclude_subject=s),
        )

        conf_name = self.board_dict.get(msg.confnum, str(msg.confnum))
        conf_label = (conf_name[:20] + "...") if len(conf_name) > 20 else conf_name
        menu.add_command(
            label=f"Filter by Conference: {conf_label}",
            command=lambda c=msg.confnum: self._pivot_filter(conf_num=c),
        )
        menu.add_command(
            label="Exclude Conference",
            command=lambda c=msg.confnum: self._pivot_filter(exclude_conf_num=c),
        )

        bbs_display = msg.bbs_name or msg.bbs_id
        if bbs_display:
            bbs_label = (
                (bbs_display[:20] + "...") if len(bbs_display) > 20 else bbs_display
            )
            menu.add_command(
                label=f"Filter by BBS: {bbs_label}",
                command=lambda b=bbs_display: self._pivot_filter(bbs_name=b),
            )
            menu.add_command(
                label="Exclude BBS",
                command=lambda b=bbs_display: self._pivot_filter(exclude_bbs_name=b),
            )

        menu.post(event.x_root, event.y_root)

    def _show_text_context_menu(self, event: tk.Event) -> None:
        """Display a context menu for the detail viewer."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label="Copy", command=lambda: self.detail_text.event_generate("<<Copy>>")
        )
        menu.add_command(
            label="Select All",
            command=lambda: self.detail_text.tag_add("sel", "1.0", tk.END),
        )

        # Get current message for information filtering
        current_selection = self.message_list.selection()
        msg = None
        if current_selection:
            try:
                idx = int(current_selection[0])
                msg = self.messages[idx]
            except (ValueError, IndexError):
                pass

        if msg:
            orig_subject = msg.header.msgsubject.strip()
            orig_from = msg.header.msgfrom.strip()
            orig_to = msg.header.msgto.strip()
            orig_num = str(msg.header.msgnum or "")

            menu.add_command(
                label="Copy Subject",
                command=lambda s=orig_subject: self._copy_to_clipboard(s),
            )
            menu.add_command(
                label="Copy From",
                command=lambda f=orig_from: self._copy_to_clipboard(f),
            )
            menu.add_command(
                label="Copy To",
                command=lambda t=orig_to: self._copy_to_clipboard(t),
            )
            menu.add_command(
                label="Copy Num",
                command=lambda n=orig_num: self._copy_to_clipboard(n),
            )

        menu.add_command(
            label="Copy Full Message",
            command=lambda: self._copy_to_clipboard(
                self.detail_text.get("1.0", tk.END).strip()
            ),
        )

        if msg:
            try:
                menu.add_separator()
                author_text = msg.header.msgfrom.strip()
                author_label = (
                    (author_text[:20] + "...") if len(author_text) > 20 else author_text
                )
                menu.add_command(
                    label=f"Filter by Author: {author_label}",
                    command=lambda a=author_text: self._pivot_filter(author=a),
                )
                menu.add_command(
                    label="Exclude Author",
                    command=lambda a=author_text: self._pivot_filter(exclude_author=a),
                )

                subj_text = msg.header.msgsubject.strip()
                subj_label = (
                    (subj_text[:20] + "...") if len(subj_text) > 20 else subj_text
                )
                menu.add_command(
                    label=f"Filter by Subject: {subj_label}",
                    command=lambda s=subj_text: self._pivot_filter(subject=s),
                )
                menu.add_command(
                    label="Exclude Subject",
                    command=lambda s=subj_text: self._pivot_filter(exclude_subject=s),
                )

                conf_name = self.board_dict.get(msg.confnum, str(msg.confnum))
                conf_label = (
                    (conf_name[:20] + "...") if len(conf_name) > 20 else conf_name
                )
                menu.add_command(
                    label=f"Filter by Conference: {conf_label}",
                    command=lambda c=msg.confnum: self._pivot_filter(conf_num=c),
                )
                menu.add_command(
                    label="Exclude Conference",
                    command=lambda c=msg.confnum: self._pivot_filter(exclude_conf_num=c),
                )

                bbs_display = msg.bbs_name or msg.bbs_id
                if bbs_display:
                    bbs_label = (
                        (bbs_display[:20] + "...")
                        if len(bbs_display) > 20
                        else bbs_display
                    )
                    menu.add_command(
                        label=f"Filter by BBS: {bbs_label}",
                        command=lambda b=bbs_display: self._pivot_filter(bbs_name=b),
                    )
                    menu.add_command(
                        label="Exclude BBS",
                        command=lambda b=bbs_display: self._pivot_filter(exclude_bbs_name=b),
                    )
            except (ValueError, IndexError):
                pass

        try:
            sel_range = self.detail_text.tag_ranges("sel")
            if sel_range:
                selected_text = self.detail_text.get(*sel_range).strip()
                if selected_text:
                    display_text = (
                        (selected_text[:20] + "...")
                        if len(selected_text) > 20
                        else selected_text
                    )
                    menu.add_separator()
                    menu.add_command(
                        label=f"Search for '{display_text}'",
                        command=self._search_from_selection,
                    )
        except tk.TclError:
            pass

        menu.post(event.x_root, event.y_root)

    def _search_from_selection(self) -> None:
        """Search for the currently selected text in the detail viewer."""
        try:
            sel_range = self.detail_text.tag_ranges("sel")
            if sel_range:
                selected_text = self.detail_text.get(*sel_range).strip()
                if selected_text:
                    self.search_var.set(selected_text)
                    self.reload_messages()
                    self.message_list.focus_set()
        except tk.TclError:
            pass

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy the given text to the system clipboard."""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _is_any_filter_active(self) -> bool:
        """Return True if any visibility filters are currently active."""
        if self.search_var.get().strip():
            return True

        if self.exclude_var.get().strip():
            return True

        bbs_val = self.bbs_combo.get()
        if bbs_val and not bbs_val.startswith("All BBSes"):
            return True

        conf_val = self.conf_combo.get()
        if conf_val and not conf_val.startswith("All Conferences"):
            return True

        for var in [
            self.has_attach_var,
            self.mine_var,
            self.on_this_day_var,
            self.has_links_var,
            self.has_emails_var,
            self.has_phones_var,
            self.has_ansi_var,
        ]:
            if var.get():
                return True

        if not self.private_var.get():
            return True

        return False

    def _find_message_index(
        self, msgnum: int, confnum: int | None = None
    ) -> int | None:
        """Locate a message index by its number and optional conference."""
        if not self.messages:
            return None

        # 1. Search in the target or current conference
        target_conf = confnum
        if target_conf is None:
            current_selection = self.message_list.selection()
            if current_selection:
                try:
                    idx = int(current_selection[0])
                    target_conf = self.messages[idx].header.confnum
                except (ValueError, IndexError):
                    pass

        if target_conf is not None:
            for i, m in enumerate(self.messages):
                if m.header.msgnum == msgnum and m.header.confnum == target_conf:
                    return i

        # 2. Search in any conference
        for i, m in enumerate(self.messages):
            if m.header.msgnum == msgnum:
                return i

        return None

    def _pivot_filter(
        self,
        author: str | None = None,
        conf_num: int | None = None,
        bbs_name: str | None = None,
        subject: str | None = None,
        exclude_author: str | None = None,
        exclude_conf_num: int | None = None,
        exclude_bbs_name: str | None = None,
        exclude_subject: str | None = None,
    ) -> None:
        """Update filters based on the selected author, conference, BBS, or subject."""
        if author:
            self.search_var.set(author)

        if subject:
            self.search_var.set(_normalize_subject(subject))

        if bbs_name:
            # Find match in BBS combobox
            for i, val in enumerate(self.bbs_combo["values"]):
                if val.startswith(bbs_name):
                    self.bbs_combo.current(i)
                    break

        if conf_num is not None:
            # Find exact match in combobox
            for i, val in enumerate(self.conf_combo["values"]):
                if val.startswith(f"{conf_num}:"):
                    self.conf_combo.current(i)
                    break

        if exclude_author:
            self.exclude_var.set(exclude_author)

        if exclude_subject:
            self.exclude_var.set(_normalize_subject(exclude_subject))

        if exclude_bbs_name:
            self.exclude_var.set(exclude_bbs_name)

        if exclude_conf_num is not None:
            self.exclude_var.set(str(exclude_conf_num))

        self.reload_messages()

    def _block_text_input(self, event: tk.Event) -> str | None:
        """Block keyboard input in the detail view while allowing common shortcuts."""
        # Allow Control+C (copy) and Control+A (select all)
        if event.state & 0x4:  # Control mask
            if event.keysym.lower() in ("c", "a"):
                return None

        # Handle message navigation shortcuts
        key = event.keysym.lower()
        if key in ("j", "n"):
            self._select_relative_message(1)
            return "break"
        if key in ("k", "p"):
            self._select_relative_message(-1)
            return "break"

        # Allow text navigation keys
        if event.keysym in (
            "Up",
            "Down",
            "Left",
            "Right",
            "Prior",
            "Next",
            "Home",
            "End",
        ):
            return None
        return "break"

    def _render_welcome_screen(self) -> None:
        """Render a welcome screen with instructions and shortcuts."""
        self.detail_text.delete("1.0", tk.END)

        self.detail_text.insert(tk.END, "Welcome to PyQWK\n", "header_subject")
        self.detail_text.insert(tk.END, " \n", "header_hr")
        self.detail_text.insert(tk.END, "\n")

        self.detail_text.insert(tk.END, "Getting Started:\n", "header_label")
        self.detail_text.insert(tk.END, "Click ", "header_value")
        self.detail_text.insert(tk.END, "Open Archive", ("link", "header_value", "link_open"))
        self.detail_text.tag_bind("link_open", "<Button-1>", self.open_file)
        self.detail_text.insert(tk.END, " or ", "header_value")
        self.detail_text.insert(tk.END, "Open Folder", ("link", "header_value", "link_folder"))
        self.detail_text.tag_bind("link_folder", "<Button-1>", self.open_folder)
        self.detail_text.insert(
            tk.END,
            " to load messages. You can also use Ctrl+O at any time.\n\n",
            "header_value",
        )

        self.detail_text.insert(tk.END, "Supported Formats:\n", "header_label")
        formats = "QWK, REP, ZIP, TAR, JSON, JSONL, CSV, SQLite (.db), XML, RSS, mbox, EML, Markdown, HTML, Plain Text, and data files (MESSAGES.DAT, REPLY.DAT)"
        self.detail_text.insert(tk.END, f"{formats}\n\n", "header_value")

        self.detail_text.insert(tk.END, "Keyboard Shortcuts:\n", "header_label")

        shortcut_groups = [
            (
                "Archive & Stats",
                [
                    ("Ctrl + O", "Open Archive"),
                    ("Ctrl + S", "Export Current View"),
                    ("Ctrl + I", "Archive Statistics"),
                    ("Ctrl + Q", "Quit Application"),
                ],
            ),
            (
                "Search & Filters",
                [
                    ("Ctrl + F", "Search / Find"),
                    ("F3", "Find Next Match"),
                    ("Shift + F3", "Find Previous Match"),
                    ("Enter", "Find Next (Search)"),
                    ("Shift+Enter", "Find Previous (Search)"),
                    ("Esc", "Clear Search / Filters"),
                ],
            ),
            (
                "Navigation",
                [
                    ("J / N", "Next Message"),
                    ("K / P", "Previous Message"),
                    ("Space", "Scroll Down / Next"),
                    ("Shift+Space", "Scroll Up / Prev"),
                    ("BackSpace", "Scroll Up / Prev"),
                    ("Ctrl + G", "Go to Message Number"),
                ],
            ),
        ]

        for group_name, shortcuts in shortcut_groups:
            self.detail_text.insert(tk.END, f"\n  {group_name}\n", "header_meta")
            for key, desc in shortcuts:
                self.detail_text.insert(tk.END, f"    {key:<15}", "header_label")
                self.detail_text.insert(tk.END, f"{desc}\n", "header_value")

    def _render_empty_state(self) -> None:
        """Render an interactive empty state when no messages match the filters."""
        self.detail_text.delete("1.0", tk.END)
        self._update_status_bar()
        self.search_count_label.config(text="")

        self.detail_text.insert(tk.END, "No Messages Found\n", "header_subject")
        self.detail_text.insert(tk.END, " \n", "header_hr")
        self.detail_text.insert(tk.END, "\n")

        self.detail_text.insert(
            tk.END,
            "Your current filters returned no results. Check the settings below:\n\n",
            "body",
        )

        # List active filters
        search_val = self.search_var.get().strip()
        if search_val:
            label = "Regex Search" if self.regex_var.get() else "Search"
            self.detail_text.insert(tk.END, f"  {label:<15}: ", "header_label")
            self.detail_text.insert(tk.END, f"'{search_val}'\n", "body")

        bbs_val = self.bbs_combo.get()
        if bbs_val and not bbs_val.startswith("All BBSes"):
            self.detail_text.insert(tk.END, f"  {'BBS':<15}: ", "header_label")
            self.detail_text.insert(tk.END, f"{bbs_val}\n", "body")

        conf_val = self.conf_combo.get()
        if conf_val and not conf_val.startswith("All Conferences"):
            self.detail_text.insert(tk.END, f"  {'Conference':<15}: ", "header_label")
            self.detail_text.insert(tk.END, f"{conf_val}\n", "body")

        active_bools = []
        for text, var in [
            ("Attachments", self.has_attach_var),
            ("My Messages", self.mine_var),
            ("On This Day", self.on_this_day_var),
            ("Links", self.has_links_var),
            ("Emails", self.has_emails_var),
            ("Phones", self.has_phones_var),
            ("Colors", self.has_ansi_var),
        ]:
            if var.get():
                active_bools.append(text)

        if active_bools:
            self.detail_text.insert(tk.END, f"  {'Filters':<15}: ", "header_label")
            self.detail_text.insert(tk.END, f"{', '.join(active_bools)}\n", "body")

        self.detail_text.insert(tk.END, "\n")

        # Action links
        self.detail_text.insert(
            tk.END, "Reset all filters and search", ("link", "body", "reset_all")
        )
        self.detail_text.tag_bind("reset_all", "<Button-1>", self.clear_filters)

        self.detail_text.insert(tk.END, "\n\n", "body")
        self.detail_text.insert(tk.END, "Tip: Press ", "body")
        self.detail_text.insert(tk.END, "Esc", "header_label")
        self.detail_text.insert(
            tk.END, " to progressively clear search and filters.", "body"
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open Archive(s)...", command=self.open_file, accelerator="Ctrl+O"
        )
        file_menu.add_command(label="Open Folder...", command=self.open_folder)
        file_menu.add_command(
            label="Export Current View...",
            command=self.export_messages,
            accelerator="Ctrl+S",
        )
        file_menu.add_command(
            label="Extract All Attachments...",
            command=self.extract_all_attachments,
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
            label="Find Next",
            command=lambda: self._navigate_search_matches(1),
            accelerator="F3",
        )
        edit_menu.add_command(
            label="Find Previous",
            command=lambda: self._navigate_search_matches(-1),
            accelerator="Shift+F3",
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
        self.root.bind("<F3>", lambda e: self._navigate_search_matches(1))
        self.root.bind("<Shift-F3>", lambda e: self._navigate_search_matches(-1))
        self.root.bind("j", lambda e: self._select_relative_message(1))
        self.root.bind("n", lambda e: self._select_relative_message(1))
        self.root.bind("k", lambda e: self._select_relative_message(-1))
        self.root.bind("p", lambda e: self._select_relative_message(-1))
        self.root.bind("<space>", self._on_space_pressed)
        self.root.bind("<Shift-space>", self._on_space_pressed)
        self.root.bind("<BackSpace>", self._on_space_pressed)

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

    def _select_relative_message(self, delta: int, force: bool = False) -> bool:
        """Move the selection up or down in the treeview display order.

        Returns:
            True if the selection changed, False otherwise.
        """
        if not self.messages:
            return False

        # If the search entry has focus, don't hijack keyboard navigation unless forced
        if not force and self.root.focus_get() == self.search_entry:
            return False

        all_items = self._get_all_tree_items()
        if not all_items:
            return False

        current_selection = self.message_list.selection()
        if not current_selection:
            new_item = all_items[0]
        else:
            current_iid = current_selection[0]
            try:
                current_idx = all_items.index(current_iid)
                new_idx = max(0, min(len(all_items) - 1, current_idx + delta))
                new_item = all_items[new_idx]
                if new_item == current_iid:
                    return False
            except ValueError:
                new_item = all_items[0]

        self.message_list.selection_set(new_item)
        self.message_list.see(new_item)
        self.message_list.focus(new_item)
        return True

    def _on_space_pressed(self, event: tk.Event) -> str | None:
        """Handle Space, Shift+Space, and BackSpace for continuous reading."""
        # If the search entry has focus, let it handle the keys
        if self.root.focus_get() == self.search_entry:
            return None

        # Check scroll position: (top, bottom) as fractions of the whole
        top, bottom = self.detail_text.yview()

        # Space (Forward)
        if event.keysym == "space" and not (event.state & 0x1):
            if bottom < 1.0:
                self.detail_text.yview_scroll(1, "pages")
            else:
                self._select_relative_message(1)
            return "break"

        # Shift+Space or BackSpace (Backward)
        elif (
            event.keysym == "space" and (event.state & 0x1)
        ) or event.keysym == "BackSpace":
            if top > 0.0:
                self.detail_text.yview_scroll(-1, "pages")
            else:
                self._select_relative_message(-1)
            return "break"

        return None

    def clear_search(self, _event: object | None = None) -> None:
        """Clear the search and exclude bars first, and if already empty, reset all filters."""
        if self.search_var.get() or self.exclude_var.get():
            self.search_var.set("")
            self.exclude_var.set("")
            self.reload_messages()
            self.message_list.focus_set()
        else:
            self.clear_filters()

    def _focus_search(self, _event: object | None = None) -> None:
        """Focus the search bar and select all text for quick replacement."""
        try:
            sel_range = self.detail_text.tag_ranges("sel")
            if sel_range:
                selected_text = self.detail_text.get(*sel_range).strip()
                if selected_text:
                    self.search_var.set(selected_text)
        except tk.TclError:
            pass

        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)

    def clear_filters(self, _event: object | None = None) -> None:
        """Reset all filters and search to their default state."""
        self.search_var.set("")
        self.exclude_var.set("")
        try:
            self.bbs_combo.current(0)
        except Exception:
            self.bbs_combo.set("All BBSes")
        try:
            self.conf_combo.current(0)
        except Exception:
            self.conf_combo.set("All Conferences")
        self.has_attach_var.set(False)
        self.mine_var.set(False)
        self.on_this_day_var.set(False)
        self.has_links_var.set(False)
        self.has_emails_var.set(False)
        self.has_phones_var.set(False)
        self.has_ansi_var.set(False)
        self.redact_pii_var.set(False)
        self.wrap_var.set(True)
        self._update_wrap()
        self.reload_messages()
        self.message_list.focus_set()

    def quit_app(self, _event: object | None = None) -> None:
        self.root.quit()

    def _update_wrap(self) -> None:
        """Toggle text wrapping in the detail view."""
        if self.wrap_var.get():
            self.detail_text.config(wrap=tk.WORD)
            self.detail_h_scrollbar.grid_forget()
        else:
            self.detail_text.config(wrap=tk.NONE)
            self.detail_h_scrollbar.grid(row=1, column=0, sticky="ew")

    def _build_status_bar(self) -> None:
        status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(status_bar, text="Ready", padding=(5, 2))
        self.status_label.pack(side=tk.LEFT)

        ttk.Sizegrip(status_bar).pack(side=tk.RIGHT)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(10, 5))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Row 1: Primary Actions and Search
        row1 = ttk.Frame(toolbar)
        row1.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        actions_frame = ttk.Frame(row1)
        actions_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            actions_frame, text="Actions", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)
        ttk.Button(actions_frame, text="Open", width=8, command=self.open_file).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(actions_frame, text="Folder", width=8, command=self.open_folder).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(actions_frame, text="Export", width=8, command=self.export_messages).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(actions_frame, text="Stats", width=8, command=self.show_stats_window).pack(
            side=tk.LEFT, padx=2
        )

        ttk.Separator(row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        nav_frame = ttk.Frame(row1)
        nav_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            nav_frame, text="Navigation", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)
        ttk.Button(
            nav_frame,
            text="Prev",
            width=8,
            command=lambda: self._select_relative_message(-1),
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            nav_frame,
            text="Next",
            width=8,
            command=lambda: self._select_relative_message(1),
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            nav_frame, text="Jump", width=8, command=self.prompt_jump_to_message
        ).pack(side=tk.LEFT, padx=2)

        ttk.Separator(row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        search_frame = ttk.Frame(row1)
        search_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            search_frame, text="Search", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, width=18
        )
        self.search_entry.pack(side=tk.LEFT, padx=(0, 0))
        ttk.Button(
            search_frame, text="✕", width=2, command=lambda: self.search_var.set("")
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.search_count_label = ttk.Label(
            search_frame, text="", width=12, anchor=tk.CENTER
        )
        self.search_count_label.pack(side=tk.LEFT)

        ttk.Button(
            search_frame,
            text="▲",
            width=2,
            command=lambda: self._navigate_search_matches(-1),
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(
            search_frame,
            text="▼",
            width=2,
            command=lambda: self._navigate_search_matches(1),
        ).pack(side=tk.LEFT, padx=(1, 5))

        ttk.Separator(search_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=10
        )

        ttk.Label(
            search_frame, text="Exclude", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)
        self.exclude_entry = ttk.Entry(
            search_frame, textvariable=self.exclude_var, width=18
        )
        self.exclude_entry.pack(side=tk.LEFT, padx=(0, 0))
        ttk.Button(
            search_frame, text="✕", width=2, command=lambda: self.exclude_var.set("")
        ).pack(side=tk.LEFT, padx=(0, 2))

        ttk.Checkbutton(
            search_frame,
            text="Regex",
            variable=self.regex_var,
            command=self.reload_messages,
        ).pack(side=tk.LEFT, padx=5)

        # Row 2: Refinement and Filters
        row2 = ttk.Frame(toolbar)
        row2.pack(side=tk.TOP, fill=tk.X)

        archives_frame = ttk.Frame(row2)
        archives_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            archives_frame, text="Archives", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)
        self.bbs_combo = ttk.Combobox(archives_frame, state="readonly", width=18)
        self.bbs_combo.pack(side=tk.LEFT, padx=2)
        self.conf_combo = ttk.Combobox(archives_frame, state="readonly", width=18)
        self.conf_combo.pack(side=tk.LEFT, padx=2)

        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        filters_frame = ttk.Frame(row2)
        filters_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            filters_frame, text="Filters", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)
        for i, (text, var) in enumerate(
            [
                ("Attachments", self.has_attach_var),
                ("My Messages", self.mine_var),
                ("On This Day", self.on_this_day_var),
                ("Links", self.has_links_var),
                ("Emails", self.has_emails_var),
                ("Phones", self.has_phones_var),
                ("Colors", self.has_ansi_var),
            ]
        ):
            ttk.Checkbutton(
                filters_frame, text=text, variable=var, command=self.reload_messages
            ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        options_frame = ttk.Frame(row2)
        options_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(
            options_frame, text="View", style="GroupHeader.TLabel", padding=(0, 0, 10, 0)
        ).pack(side=tk.LEFT)

        for i, (text, var, cmd) in enumerate(
            [
                ("Threaded", self.threaded_var, self.reload_messages),
                ("Clean", self.clean_var, self.reload_messages),
                ("Wrap", self.wrap_var, self._update_wrap),
                ("Remove Colors", self.ansi_var, self.reload_messages),
                ("Hide Personal Info", self.redact_pii_var, self.reload_messages),
            ]
        ):
            ttk.Checkbutton(options_frame, text=text, variable=var, command=cmd).pack(
                side=tk.LEFT, padx=5
            )

        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(row2, text="Reset All", width=10, command=self.clear_filters).pack(
            side=tk.LEFT, padx=5
        )

        # Binds
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Shift-Return>", self._on_search_shift_enter)
        self.exclude_entry.bind("<Return>", self._on_search_enter)
        self.exclude_entry.bind("<Shift-Return>", self._on_search_shift_enter)
        self.search_entry.bind("<Escape>", self.clear_search)
        self.search_entry.bind(
            "<Up>", lambda e: self._select_relative_message(-1, force=True)
        )
        self.search_entry.bind(
            "<Down>", lambda e: self._select_relative_message(1, force=True)
        )
        self.root.bind("<Control-f>", self._focus_search)
        self.bbs_combo.bind("<<ComboboxSelected>>", lambda e: self.reload_messages())
        self.bbs_combo.bind("<Escape>", lambda e: self.clear_filters())
        self.conf_combo.bind("<<ComboboxSelected>>", lambda e: self.reload_messages())
        self.conf_combo.bind("<Escape>", lambda e: self.clear_filters())

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
            columns=("Flags", "Num", "From", "To", "Date", "Size", "Conference", "BBS"),
            selectmode="browse",
        )

        self._reset_column_headers()

        self.message_list.column("#0", minwidth=200, width=300)
        self.message_list.column(
            "Flags", minwidth=60, width=60, stretch=False, anchor=tk.CENTER
        )
        self.message_list.column(
            "Num", minwidth=60, width=60, stretch=False, anchor=tk.E
        )
        self.message_list.column("From", minwidth=80, width=150)
        self.message_list.column("To", minwidth=80, width=150)
        self.message_list.column("Date", minwidth=80, width=120)
        self.message_list.column(
            "Size", minwidth=70, width=70, stretch=False, anchor=tk.E
        )
        self.message_list.column("Conference", minwidth=80, width=120)
        self.message_list.column("BBS", minwidth=80, width=120)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.message_list.yview
        )
        h_scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.HORIZONTAL, command=self.message_list.xview
        )
        self.message_list.configure(
            yscrollcommand=scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        self.message_list.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

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
        self.detail_h_scrollbar = ttk.Scrollbar(
            detail_frame, orient=tk.HORIZONTAL, command=self.detail_text.xview
        )
        self.detail_text.configure(
            yscrollcommand=detail_scrollbar.set,
            xscrollcommand=self.detail_h_scrollbar.set,
        )

        detail_scrollbar.grid(row=0, column=1, sticky="ns")
        self.detail_text.grid(row=0, column=0, sticky="nsew")

        detail_frame.grid_rowconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(0, weight=1)
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
        self.detail_text.tag_configure(
            "header_meta", font=("TkDefaultFont", 9), foreground="#888888"
        )
        self.detail_text.tag_configure(
            "header_hr", font=("TkDefaultFont", 1), background="#eeeeee"
        )
        self.detail_text.tag_configure("header_area", background="#f9f9f9")
        self.detail_text.tag_configure("header_value", font=("TkDefaultFont", 10))
        self.detail_text.tag_configure(
            "header_subject", font=("TkDefaultFont", 14, "bold")
        )
        self.detail_text.tag_configure("header_separator", foreground="#cccccc")
        self.detail_text.tag_configure(
            "badge_private",
            background="#ffcccc",
            foreground="#990000",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.detail_text.tag_configure(
            "badge_mine",
            background="#cce5ff",
            foreground="#004085",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.detail_text.tag_configure("body", font=("TkFixedFont", 10))
        self.detail_text.tag_configure("quote", foreground="#4e9a06")
        self.detail_text.tag_configure(
            "search_highlight", background="#ffff00", foreground="#000000"
        )
        self.detail_text.tag_configure(
            "current_search_highlight", background="#ff9900", foreground="#ffffff"
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

        exclude_val = self.exclude_var.get().strip()
        if not exclude_val:
            exclude_val = None

        selected_bbs_name = self.bbs_combo.get()
        bbs_names = None
        if selected_bbs_name and not selected_bbs_name.startswith("All BBSes"):
            bbs_id = self.bbs_mapping.get(selected_bbs_name)
            if bbs_id is not None:
                bbs_names = [bbs_id]

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
            redact_pii=self.redact_pii_var.get(),
            strip_ansi=clean or self.ansi_var.get(),
            format="text",
            separator="none",
            output_mode="stdout",
            output_path=None,
            encoding="cp437",
            regex=self.regex_var.get(),
            quiet=True,
            search_term=search_val if search_val else None,
            exclude_search=exclude_val if exclude_val else None,
            conferences=conferences,
            bbs_names=bbs_names,
            has_attachments=self.has_attach_var.get(),
            mine=self.mine_var.get(),
            on_this_day=self.on_this_day_var.get(),
            oneline=False,
            oneline_pattern=None,
            has_links=self.has_links_var.get(),
            has_emails=self.has_emails_var.get(),
            has_phones=self.has_phones_var.get(),
            has_ansi=self.has_ansi_var.get(),
        )

    def _render_message(self, message_index: int) -> None:
        """Render a message with rich formatting in the detail view."""
        msg = self.messages[message_index]
        header = msg.header
        conf_name = self.board_dict.get(header.confnum, str(header.confnum))
        settings = self._current_settings()

        self.detail_text.delete("1.0", tk.END)

        # Apply header area background
        header_start = "1.0"

        # Subject as a prominent title
        orig_subject = header.msgsubject.strip() or "(no subject)"
        orig_from = header.msgfrom.strip()
        orig_to = header.msgto.strip()

        subject = orig_subject
        msg_from = orig_from
        msg_to = orig_to

        if settings.redact_pii:
            from pyqwk.core import _redact_pii

            subject = _redact_pii(subject)
            msg_from = _redact_pii(msg_from)
            msg_to = _redact_pii(msg_to)

        subject_tag = f"subject_link_{id(msg)}"
        self.detail_text.insert(
            tk.END, subject + "\n", ("link", "header_subject", subject_tag)
        )
        self.detail_text.tag_bind(
            subject_tag,
            "<Button-1>",
            lambda e, s=orig_subject: self._pivot_filter(subject=s),
        )

        self.detail_text.insert(tk.END, " \n", "header_hr")
        self.detail_text.insert(tk.END, "\n")

        # Primary fields
        self.detail_text.insert(tk.END, "From: ", "header_label")
        from_tag = f"from_link_{id(msg)}"
        self.detail_text.insert(tk.END, msg_from, ("link", "header_value", from_tag))
        self.detail_text.tag_bind(
            from_tag,
            "<Button-1>",
            lambda e, a=orig_from: self._pivot_filter(author=a),
        )
        self.detail_text.insert(tk.END, "\n")

        self.detail_text.insert(tk.END, "To:   ", "header_label")
        to_tag = f"to_link_{id(msg)}"
        self.detail_text.insert(tk.END, msg_to, ("link", "header_value", to_tag))
        self.detail_text.tag_bind(
            to_tag,
            "<Button-1>",
            lambda e, a=orig_to: self._pivot_filter(author=a),
        )
        self.detail_text.insert(tk.END, "\n\n")

        # Information line (Date, Conference, BBS, Msg #)
        self.detail_text.insert(
            tk.END, f"{header.msgdate} {header.msgtime}", "header_meta"
        )

        # Badges
        if header.is_private:
            self.detail_text.insert(tk.END, "  ")
            self.detail_text.insert(tk.END, " PRIVATE ", "badge_private")

        bbs_info = getattr(self.board_dict, "bbs_info", None)
        user_name = bbs_info.user_name if bbs_info else None
        if user_name:
            is_from_me = user_name.lower() in header.msgfrom.lower()
            is_to_me = user_name.lower() in header.msgto.lower()
            if is_from_me or is_to_me:
                self.detail_text.insert(tk.END, "  ")
                self.detail_text.insert(tk.END, " MINE ", "badge_mine")

        self.detail_text.insert(tk.END, "  •  ", "header_meta")

        conf_tag = f"conf_link_{id(msg)}"
        self.detail_text.insert(tk.END, conf_name, ("link", "header_meta", conf_tag))
        self.detail_text.tag_bind(
            conf_tag,
            "<Button-1>",
            lambda e, c=header.confnum: self._pivot_filter(conf_num=c),
        )

        if msg.bbs_name:
            self.detail_text.insert(tk.END, "  •  ", "header_meta")
            bbs_tag = f"bbs_link_{id(msg)}"
            self.detail_text.insert(
                tk.END, msg.bbs_name, ("link", "header_meta", bbs_tag)
            )
            self.detail_text.tag_bind(
                bbs_tag,
                "<Button-1>",
                lambda e, b=msg.bbs_name: self._pivot_filter(bbs_name=b),
            )

        if header.msgnum is not None:
            self.detail_text.insert(tk.END, "  •  ", "header_meta")
            self.detail_text.insert(tk.END, f"Msg #{header.msgnum}", "header_meta")

        if msg.refnum:
            self.detail_text.insert(tk.END, "  •  ", "header_meta")
            ref_tag = f"ref_link_{id(msg)}"
            self.detail_text.insert(tk.END, f"Ref #{msg.refnum}", ("link", ref_tag))
            self.detail_text.tag_bind(
                ref_tag,
                "<Button-1>",
                lambda e, c=header.confnum, r=msg.refnum: self.jump_to_message(
                    c, r
                ),
            )

        self.detail_text.insert(tk.END, "\n")

        if msg.source_file:
            self.detail_text.insert(
                tk.END, f"Source: {msg.source_file}\n", "header_meta"
            )

        if msg.attachments:
            self.detail_text.insert(tk.END, "Attachments: ", "header_label")
            for i, filename in enumerate(msg.attachments):
                tag = f"attach_link_{id(msg)}_{i}"
                self.detail_text.insert(tk.END, filename, ("link", tag))
                self.detail_text.tag_bind(
                    tag,
                    "<Button-1>",
                    lambda e, f=filename, idx=i: self.save_attachment(f, idx),
                )
                if i < len(msg.attachments) - 1:
                    self.detail_text.insert(tk.END, ", ", "header_value")
            self.detail_text.insert(tk.END, "\n")

        header_end = self.detail_text.index(tk.INSERT)
        self.detail_text.tag_add("header_area", header_start, header_end)

        # Visual separator
        self.detail_text.insert(tk.END, "\n")
        self.detail_text.insert(tk.END, "\n")

        # Insert body with quote highlighting
        for line in msg.text.splitlines(keepends=True):
            tags = ["body"]
            if RE_QUOTE_PATTERN.match(line):
                tags.append("quote")

            # Unified discovery loop for URLs, Emails, and Phone numbers
            entities = []
            for match in RE_URL_PATTERN.finditer(line):
                entities.append((match.start(), match.end(), "url", match.group(0)))
            for match in RE_EMAIL_PATTERN.finditer(line):
                entities.append((match.start(), match.end(), "email", match.group(0)))
            for match in RE_PHONE_PATTERN.finditer(line):
                entities.append((match.start(), match.end(), "phone", match.group(0)))
            for match in RE_MSG_LINK_PATTERN.finditer(line):
                entities.append((match.start(), match.end(), "msg_link", match.group(0)))

            # Sort entities: primary sort by start position (ascending),
            # secondary sort by end position (descending) to prefer longer matches.
            entities.sort(key=lambda x: (x[0], -x[1]))

            last_idx = 0
            for start, end, etype, evalue in entities:
                if start < last_idx:
                    continue  # Skip overlapping entities

                # Insert text before entity
                if start > last_idx:
                    self.detail_text.insert(tk.END, line[last_idx:start], tuple(tags))

                # Determine URI or Action
                if etype == "url":
                    uri = evalue if "://" in evalue else f"http://{evalue}"

                    def open_url(e, u=uri):
                        return webbrowser.open(u)

                    cmd = open_url
                elif etype == "email":
                    uri = f"mailto:{evalue}"

                    def open_email(e, u=uri):
                        return webbrowser.open(u)

                    cmd = open_email
                elif etype == "phone":
                    uri = "tel:" + "".join(c for c in evalue if c.isdigit() or c == "+")

                    def open_phone(e, u=uri):
                        return webbrowser.open(u)

                    cmd = open_phone
                else:  # msg_link
                    # Extract message number from text (e.g. "msg #123" -> 123)
                    msg_num_match = RE_MSG_LINK_PATTERN.search(evalue)
                    msg_num = int(msg_num_match.group(1)) if msg_num_match else 0

                    def jump_msg(e, c=header.confnum, n=msg_num):
                        return self.jump_to_message(c, n)

                    cmd = jump_msg

                # Insert Entity
                entity_tag = f"{etype}_{id(evalue)}_{start}"
                # Combine link/body tags with the existing line tags (e.g. 'quote')
                link_tags = ("link", "body", entity_tag) + tuple(
                    t for t in tags if t != "body"
                )
                self.detail_text.insert(tk.END, evalue, link_tags)
                self.detail_text.tag_bind(entity_tag, "<Button-1>", cmd)

                last_idx = end

            # Insert remaining text
            if last_idx < len(line):
                self.detail_text.insert(tk.END, line[last_idx:], tuple(tags))

        # Highlight search terms if present
        search_term = self.search_var.get().strip()
        self._search_matches = []
        self._current_match_idx = -1

        if not search_term:
            self.search_count_label.config(text="")
        else:
            start_pos = "1.0"
            is_regex = self.regex_var.get()
            count_var = tk.IntVar()

            while True:
                try:
                    start_pos = self.detail_text.search(
                        search_term,
                        start_pos,
                        stopindex=tk.END,
                        nocase=True,
                        regexp=is_regex,
                        count=count_var,
                    )
                except tk.TclError:
                    # Invalid regex
                    break
                if not start_pos:
                    break

                match_count = count_var.get()
                if match_count == 0:  # Avoid infinite loop on zero-width match
                    start_pos = f"{start_pos}+1c"
                    continue
                end_pos = f"{start_pos}+{match_count}c"
                self.detail_text.tag_add("search_highlight", start_pos, end_pos)
                self._search_matches.append((start_pos, end_pos))
                start_pos = end_pos

            self.detail_text.tag_raise("search_highlight")
            if self._search_matches:
                # Determine initial match index
                if self._pending_match_idx is not None:
                    self._current_match_idx = self._pending_match_idx % len(
                        self._search_matches
                    )
                    self._pending_match_idx = None
                else:
                    self._current_match_idx = 0

                start_pos, end_pos = self._search_matches[self._current_match_idx]
                self.detail_text.see(start_pos)
                self.detail_text.tag_add("current_search_highlight", start_pos, end_pos)
                self.detail_text.tag_raise("current_search_highlight")

                # Update counters
                self.search_count_label.config(
                    text=f"{self._current_match_idx + 1} / {len(self._search_matches)}"
                )

                # Update status feedback
                self._update_status_bar(message_index)
            else:
                self.search_count_label.config(text="0 / 0")

    def _navigate_search_matches(
        self, delta: int, _event: object | None = None
    ) -> None:
        """Cycle through search matches in the detail view, navigating across messages if needed."""
        if not self._search_matches:
            # If no matches in current message, but search is active, try to find in other messages
            if self.search_var.get().strip():
                if self._select_relative_message(delta, force=True):
                    self._pending_match_idx = 0 if delta > 0 else -1
                    return
            return

        new_idx = self._current_match_idx + delta

        # Cross-message navigation
        if new_idx < 0 or new_idx >= len(self._search_matches):
            if self._select_relative_message(delta, force=True):
                self._pending_match_idx = 0 if delta > 0 else -1
                return
            else:
                # Boundary reached, implement archive-wide wrap-around
                all_items = self._get_all_tree_items()
                if not all_items:
                    return
                target_iid = all_items[0] if delta > 0 else all_items[-1]

                # Handle case where the wrap-around target is the current message
                current_sel = self.message_list.selection()
                if current_sel and current_sel[0] == target_iid:
                    # Manually trigger render since selection_set won't trigger event
                    self._pending_match_idx = 0 if delta > 0 else -1
                    try:
                        self._render_message(int(target_iid))
                    except (ValueError, IndexError):
                        pass
                else:
                    self.message_list.selection_set(target_iid)
                    self.message_list.see(target_iid)
                    self.message_list.focus(target_iid)
                    self._pending_match_idx = 0 if delta > 0 else -1
                return

        # Single-message navigation
        self.detail_text.tag_remove("current_search_highlight", "1.0", tk.END)
        self._current_match_idx = new_idx
        start_pos, end_pos = self._search_matches[self._current_match_idx]
        self.detail_text.tag_add("current_search_highlight", start_pos, end_pos)
        self.detail_text.tag_raise("current_search_highlight")
        self.detail_text.see(start_pos)

        # Update counters and status
        self.search_count_label.config(
            text=f"{self._current_match_idx + 1} / {len(self._search_matches)}"
        )
        current_selection = self.message_list.selection()
        current_index = None
        if current_selection:
            try:
                current_index = int(current_selection[0])
            except (ValueError, IndexError):
                pass
        self._update_status_bar(current_index)

    def open_file(self, _event: object | None = None) -> None:
        filetypes = [
            (
                "All supported formats",
                "*.qwk *.rep *.json *.jsonl *.csv *.db *.sqlite *.xml *.rss *.mbox *.eml *.md *.markdown *.html *.htm *.tar *.tar.gz *.tar.bz2 *.tgz *.txt",
            ),
            ("QWK archives", "*.qwk"),
            ("REP archives", "*.rep"),
            ("JSON archives", "*.json"),
            ("JSONL archives", "*.jsonl"),
            ("CSV archives", "*.csv"),
            ("SQLite databases", "*.db *.sqlite"),
            ("XML archives", "*.xml"),
            ("RSS feeds", "*.rss"),
            ("mbox files", "*.mbox"),
            ("EML files", "*.eml"),
            ("Markdown files", "*.md *.markdown"),
            ("HTML archives", "*.html *.htm"),
            ("Plain Text", "*.txt"),
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
            messagebox.showinfo(
                "Open Folder",
                "No supported message archives found in the selected folder.",
            )
            return

        self.current_paths = paths
        self.load_messages(self.current_paths)

    def _on_search_changed(self, *args: object) -> None:
        """Handle search term changes with a short delay to keep the interface fast."""
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
        self._search_timer = self.root.after(250, self.reload_messages)

    def _on_search_enter(self, _event: object) -> None:
        """Run the search or move through matches when Enter is pressed."""
        # If a delayed search is pending, run it immediately and focus the list
        if self._search_timer is not None:
            self.reload_messages()
            self.message_list.focus_set()
            return

        # Only navigate matches if the search entry is focused
        if self.root.focus_get() == self.search_entry and self._search_matches:
            self._navigate_search_matches(1)
        else:
            self.reload_messages()
            self.message_list.focus_set()

    def _on_search_shift_enter(self, _event: object) -> None:
        """Move back through matches when Shift+Enter is pressed."""
        # Only navigate matches if the search entry is focused
        if self.root.focus_get() == self.search_entry and self._search_matches:
            self._navigate_search_matches(-1)
        else:
            self.reload_messages()
            self.message_list.focus_set()

    def reload_messages(self) -> None:
        if self._search_timer is not None:
            self.root.after_cancel(self._search_timer)
            self._search_timer = None

        if self.current_paths:
            self.load_messages(self.current_paths)

    def _reset_column_headers(
        self, sort_col: str | None = None, reverse: bool = False
    ) -> None:
        """Reset column headers to their original labels and optionally apply sort indicators."""
        for col, label in self.column_labels.items():
            if col == sort_col:
                label += " ▼" if reverse else " ▲"
                # If we just sorted this column, the next click should reverse it
                next_reverse = not reverse
            else:
                # If we click a different column, it should start as ascending
                next_reverse = False

            if col in ("Num", "Size"):
                header_anchor = tk.E
            elif col == "Flags":
                header_anchor = tk.CENTER
            else:
                header_anchor = tk.W

            self.message_list.heading(
                col,
                text=label,
                anchor=header_anchor,
                command=lambda c=col, r=next_reverse: self.sort_column(c, r),
            )

    def load_messages(self, paths: str | list[str]) -> None:
        if isinstance(paths, str):
            paths = [paths]

        # Save current state for potential restoration on failure
        old_messages = self.messages
        old_total_msg_count = self.total_msg_count
        old_source_display_name = self.source_display_name
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
                if self._cache.get("path") != path:
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
                        selected_msg_key = (
                            m.header.confnum,
                            m.header.msgnum,
                            m.header.msgsubject,
                            m.header.msgfrom,
                        )
                except (ValueError, IndexError):
                    pass

            # Reset headers to remove any previous sort indicators
            self._reset_column_headers()

            all_messages = []
            merged_board_dict = ConferenceMap()
            total_count = 0
            conf_counts = Counter()
            bbs_counts = Counter()
            bbs_identities = {}

            for path in paths:
                if len(paths) == 1 and self._cache.get("path") == path:
                    file_data = self._cache["file_data"]
                    board_dict = self._cache["board_dict"]
                else:
                    file_data, board_dict = load_data(
                        path, self.logger, settings.encoding
                    )

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

                allowed_conferences = get_allowed_conferences(
                    settings.conferences, board_dict
                )

                if isinstance(file_data, list):
                    messages_to_process = file_data
                else:
                    messages_to_process = parse_messages(
                        file_data, None, settings.encoding
                    )

                # Create settings objects without conference/BBS filters for counting
                count_settings = replace(settings, conferences=None)
                bbs_count_settings = replace(settings, bbs_names=None)

                for parsed_message in messages_to_process:
                    total_count += 1

                    # Add BBS and source file information
                    parsed_message = replace(
                        parsed_message,
                        bbs_name=parsed_message.bbs_name
                        or (bbs_info.name if bbs_info else None),
                        bbs_id=parsed_message.bbs_id
                        or (bbs_info.bbs_id if bbs_info else None),
                        source_file=parsed_message.source_file
                        or os.path.basename(path),
                    )

                    # Check if message matches filters ignoring the BBS filter itself
                    if matches_filters(
                        parsed_message, bbs_count_settings, set(), user_name
                    ):
                        bbs_display = (
                            parsed_message.bbs_name
                            or parsed_message.bbs_id
                            or "Unknown BBS"
                        )
                        # Use ID for exact filtering if available, else name
                        bbs_val = parsed_message.bbs_id or parsed_message.bbs_name or ""
                        bbs_counts[bbs_display] += 1
                        bbs_identities[bbs_display] = bbs_val

                    # Check if message matches filters ignoring the conference filter itself
                    if matches_filters(
                        parsed_message, count_settings, set(), user_name
                    ):
                        conf_counts[parsed_message.confnum] += 1

                        # Now apply the actual filters for the display list
                        if matches_filters(
                            parsed_message, settings, allowed_conferences, user_name
                        ):
                            processed_buffer = process_message(
                                parsed_message.text,
                                settings.truncate_signatures,
                                settings.cut_quoting,
                                settings.binaries_removal,
                                settings.redact_pii,
                                settings.strip_ansi,
                            )

                            # Ensure attachments are detected for the status icon
                            attachments = parsed_message.discover_attachments()

                            all_messages.append(
                                replace(
                                    parsed_message,
                                    text=processed_buffer,
                                    attachments=attachments,
                                )
                            )

            # Update cache if it was a single file
            if len(paths) == 1:
                self._cache = {
                    "path": paths[0],
                    "file_data": file_data,  # From the last iteration
                    "board_dict": board_dict,
                }

            # Re-populate BBS selector with dynamic counts
            total_bbs_filtered = sum(bbs_counts.values())
            bbs_list = [f"All BBSes ({total_bbs_filtered})"]
            new_bbs_mapping = {}

            old_bbs_selection = self.bbs_combo.get()
            selected_bbs_id = self.bbs_mapping.get(old_bbs_selection)
            new_bbs_selection = bbs_list[0]

            for b_name, count in sorted(bbs_counts.items()):
                b_val = bbs_identities[b_name]
                display_str = f"{b_name} ({count})"
                bbs_list.append(display_str)
                new_bbs_mapping[display_str] = b_val
                if b_val == selected_bbs_id:
                    new_bbs_selection = display_str

            self.bbs_combo["values"] = bbs_list
            self.bbs_mapping = new_bbs_mapping
            self.bbs_combo.set(new_bbs_selection)

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

            self.conf_combo["values"] = conf_list
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
                msg_from = header.msgfrom.strip()
                msg_to = header.msgto.strip()

                if settings.redact_pii:
                    from pyqwk.core import _redact_pii

                    subject = _redact_pii(subject)
                    msg_from = _redact_pii(msg_from)
                    msg_to = _redact_pii(msg_to)

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
                        msg_from,
                        msg_to,
                        f"{header.msgdate} {header.msgtime}",
                        format_size(len(message.text)) if message.text else "0 B",
                        conf_name,
                        message.bbs_name or message.bbs_id or "",
                    ),
                    open=True,  # Expand by default
                    tags=tuple(item_tags),
                )

                if settings.threaded:
                    parent_at_depth[message.depth] = iid

            bbs_info = getattr(self.board_dict, "bbs_info", None)
            if bbs_info and bbs_info.name:
                source_display = f"{bbs_info.name} ({os.path.basename(path)})"
            else:
                source_display = os.path.basename(path)

            self.total_msg_count = total_count
            self.source_display_name = (
                source_display if len(paths) == 1 else str(len(paths)) + " archives"
            )

            self._update_status_bar()
            self.root.title(f"{self.source_display_name} - PyQWK Reader")

            # Restore selection if possible
            new_iid_to_select = None
            if selected_msg_key:
                for i, m in enumerate(self.messages):
                    if (
                        m.header.confnum,
                        m.header.msgnum,
                        m.header.msgsubject,
                        m.header.msgfrom,
                    ) == selected_msg_key:
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
                self._render_empty_state()
        except Exception as exc:
            # Restore previous state on failure
            self.messages = old_messages
            self.total_msg_count = old_total_msg_count
            self.source_display_name = old_source_display_name
            self.board_dict = old_board_dict
            self._cache = old_cache
            self.current_paths = old_paths

            # Reset status and show error
            if self.current_paths:
                self._update_status_bar()
            else:
                self.status_label.config(text="Ready")
                self.root.title("PyQWK Reader")

            messagebox.showerror("Failed to load QWK", str(exc))

    def save_attachment(self, filename: str, attachment_index: int) -> None:
        """Save a specific attachment from the currently selected message."""
        current_selection = self.message_list.selection()
        if not current_selection:
            return

        try:
            idx = int(current_selection[0])
            msg = self.messages[idx]

            # Re-extract to get the original bytes
            if not msg.text:
                return
            found = extract_binaries(msg.text)
            if attachment_index >= len(found):
                return

            _, data = found[attachment_index]

            initial_file = os.path.basename(filename)
            path = filedialog.asksaveasfilename(
                title=f"Save Attachment: {initial_file}",
                initialfile=initial_file,
            )

            if path:
                with open(path, "wb") as f:
                    f.write(data)
                self.status_label.config(
                    text=f"Saved attachment to {os.path.basename(path)}"
                )
        except Exception as e:
            messagebox.showerror("Save Attachment", f"Failed to save attachment: {e}")

    def extract_all_attachments(self, _event: object | None = None) -> None:
        """Batch-extract all attachments from the current filtered view."""
        if not self.messages:
            messagebox.showwarning("Extract Attachments", "No messages to process.")
            return

        folder = filedialog.askdirectory(title="Select Folder to Extract Attachments")
        if not folder:
            return

        try:
            count = 0
            # Use messages in their current display order from the treeview
            ordered_item_ids = self._get_all_tree_items()

            for iid in ordered_item_ids:
                try:
                    idx = int(iid)
                    msg = self.messages[idx]
                    if not msg.text:
                        continue

                    found = extract_binaries(msg.text)
                    for filename, data in found:
                        # Sanitize filename
                        filename = os.path.basename(filename)
                        if not filename:
                            filename = "attachment.bin"

                        target_path = os.path.join(folder, filename)
                        # Avoid duplicate filenames
                        if os.path.exists(target_path):
                            base, ext = os.path.splitext(filename)
                            counter = 1
                            while os.path.exists(target_path):
                                target_path = os.path.join(
                                    folder, f"{base}_{counter}{ext}"
                                )
                                counter += 1

                        with open(target_path, "wb") as f:
                            f.write(data)
                        count += 1
                except (ValueError, IndexError):
                    continue

            messagebox.showinfo(
                "Extraction Successful",
                f"Successfully extracted {count} attachments to {folder}",
            )
            self.status_label.config(text=f"Extracted {count} attachments")
        except Exception as e:
            messagebox.showerror(
                "Extraction Failed", f"Failed to extract attachments: {e}"
            )

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
            ("JSONL files", "*.jsonl"),
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
                    if settings.format == "text" and not settings.no_header:
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
        if not self.messages and not self.current_paths:
            return

        msgnum = simpledialog.askinteger("Jump to Message", "Enter message number:")
        if msgnum is None:
            return

        idx = self._find_message_index(msgnum)
        if idx is not None:
            self._select_by_index(idx)
            return

        if self._is_any_filter_active():
            if messagebox.askyesno(
                "Not Found",
                f"Message #{msgnum} was not found in the current view. "
                "Would you like to reset all filters to find it?",
            ):
                self.clear_filters()
                idx = self._find_message_index(msgnum)
                if idx is not None:
                    self._select_by_index(idx)
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
        idx = self._find_message_index(msgnum, confnum)
        if idx is not None:
            self._select_by_index(idx)
            return

        if self._is_any_filter_active():
            if messagebox.askyesno(
                "Not Found",
                f"Referenced message #{msgnum} was not found in the current view. "
                "Would you like to reset all filters to find it?",
            ):
                self.clear_filters()
                idx = self._find_message_index(msgnum, confnum)
                if idx is not None:
                    self._select_by_index(idx)
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
            title_suffix = (
                os.path.basename(self.current_paths[0])
                if len(self.current_paths) == 1
                else f"{len(self.current_paths)} archives"
            )
            stats_win.title(f"Statistics - {title_suffix}")
            stats_win.geometry("750x700")
            stats_win.bind("<Escape>", lambda e: stats_win.destroy())

            main_frame = ttk.Frame(stats_win, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            txt = tk.Text(
                main_frame, font=("TkFixedFont", 10), wrap=tk.NONE, padx=10, pady=10
            )
            sb_y = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=txt.yview)
            sb_x = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=txt.xview)
            txt.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

            # Footer for close button
            footer = ttk.Frame(stats_win, padding=(10, 5))
            footer.pack(side=tk.BOTTOM, fill=tk.X)
            ttk.Button(footer, text="Close", command=stats_win.destroy).pack(
                side=tk.RIGHT
            )

            txt.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            sb_y.pack(side=tk.RIGHT, fill=tk.Y, before=txt)
            sb_x.pack(side=tk.BOTTOM, fill=tk.X)

            # Define tags for statistics window
            txt.tag_configure(
                "h1", font=("TkDefaultFont", 14, "bold"), foreground="#0055aa"
            )
            txt.tag_configure(
                "h2", font=("TkDefaultFont", 11, "bold"), foreground="#444444"
            )
            txt.tag_configure("bold", font=("TkFixedFont", 10, "bold"))
            txt.tag_configure("dim", foreground="#888888")
            txt.tag_configure("cyan_bar", background="#00aaaa", foreground="#ffffff")
            txt.tag_configure(
                "info_label", font=("TkFixedFont", 10, "bold"), foreground="#666666"
            )
            txt.tag_configure("link", foreground="blue", underline=True)
            txt.tag_bind("link", "<Enter>", lambda e: txt.config(cursor="hand2"))
            txt.tag_bind("link", "<Leave>", lambda e: txt.config(cursor=""))

            # Rendering logic
            display_name = (
                os.path.basename(stats["file"])
                if len(self.current_paths) == 1
                else "Multiple Archives"
            )
            txt.insert(tk.END, f"Statistics for: {display_name}\n\n", "h1")
            txt.insert(
                tk.END,
                "Tip: Click on any chart label to filter the main view.\n",
                "dim",
            )

            def insert_info(label, value):
                txt.insert(tk.END, f"  {label:<15}: ", "info_label")
                txt.insert(tk.END, f"{value}\n")

            insert_info(
                "Messages",
                f"{stats['matching_messages']} matching / {stats['total_messages']} total",
            )
            if stats["attachments_count"] > 0:
                insert_info(
                    "Attachments", f"{stats['attachments_count']} files detected"
                )
            if stats["dates"]["earliest"]:
                earliest = datetime.datetime.fromisoformat(
                    stats["dates"]["earliest"]
                ).strftime("%Y-%m-%d")
                latest = datetime.datetime.fromisoformat(
                    stats["dates"]["latest"]
                ).strftime("%Y-%m-%d")
                insert_info("Date Range", f"{earliest} to {latest}")
            insert_info("Private", f"{stats['private_count']} messages")

            txt.insert(tk.END, "\nActivity & Content\n", "h2")
            insert_info(
                "Reply Rate", f"{stats['reply_rate']}% ({stats['reply_count']} replies)"
            )
            insert_info("Avg Length", f"{int(stats['avg_message_length'])} characters")

            def render_gui_bar_chart(title, data, filter_type=None):
                if not data:
                    return
                txt.insert(tk.END, f"\n{title}\n", "h2")
                max_count = max(item[1] for item in data) if data else 0
                for i, item in enumerate(data):
                    label = item[0]
                    count = item[1]
                    filter_val = item[2] if len(item) > 2 else label

                    truncated_label = f"{str(label)[:25]:<25}"
                    count_str = f"{count:4}"
                    bar_len = int(count * 40 / max_count) if max_count > 0 else 0

                    txt.insert(tk.END, "    ", "")

                    label_tags = ["dim"]
                    if filter_type:
                        label_tags.append("link")
                        # Create a unique tag for this specific label to bind the click event
                        # Include title hash to ensure uniqueness across different charts
                        title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                        item_tag = f"filter_{filter_type}_{title_hash}_{i}"
                        label_tags.append(item_tag)

                        def make_callback(ft, fv):
                            def callback(e):
                                stats_win.destroy()
                                if ft == "author":
                                    self._pivot_filter(author=fv)
                                elif ft == "conf":
                                    self._pivot_filter(conf_num=fv)
                                elif ft == "bbs":
                                    self._pivot_filter(bbs_name=fv)
                                elif ft == "search":
                                    self.search_var.set(fv)
                                    self.reload_messages()

                            return callback

                        txt.tag_bind(
                            item_tag,
                            "<Button-1>",
                            make_callback(filter_type, filter_val),
                        )

                    txt.insert(tk.END, truncated_label, tuple(label_tags))
                    txt.insert(tk.END, " : ", "")
                    txt.insert(tk.END, count_str, "bold")
                    txt.insert(tk.END, " ", "")
                    if bar_len > 0:
                        txt.insert(tk.END, " " * bar_len, "cyan_bar")
                    txt.insert(tk.END, "\n")

            if stats["year_distribution"]:
                items = [(y, c) for y, c in sorted(stats["year_distribution"].items())]
                render_gui_bar_chart("Yearly Activity", items)

            if stats["month_distribution"] and len(stats["month_distribution"]) <= 24:
                items = [(m, c) for m, c in sorted(stats["month_distribution"].items())]
                render_gui_bar_chart("Monthly Activity", items)

            render_gui_bar_chart(
                "Top Authors",
                [(a["name"], a["count"], a["name"]) for a in stats["authors"]],
                filter_type="author",
            )
            render_gui_bar_chart(
                "Top Recipients",
                [(r["name"], r["count"], r["name"]) for r in stats["recipients"]],
                filter_type="author",
            )

            if stats.get("bbses"):
                render_gui_bar_chart(
                    "Top BBSes",
                    [(b["name"], b["count"], b["name"]) for b in stats["bbses"]],
                    filter_type="bbs",
                )

            if stats["conferences"]:
                items = [
                    (f"{c['number']:3} {c['name']}", c["count"], c["number"])
                    for c in stats["conferences"]
                ]
                render_gui_bar_chart("Top Conferences", items, filter_type="conf")

            render_gui_bar_chart(
                "Top Subjects",
                [(s["subject"], s["count"]) for s in stats["subjects"]],
                filter_type="search",
            )
            render_gui_bar_chart(
                "Top Keywords",
                [(k["word"], k["count"]) for k in stats["keywords"]],
                filter_type="search",
            )

            if stats.get("links"):
                render_gui_bar_chart(
                    "Top Links",
                    [(link["url"], link["count"]) for link in stats["links"]],
                    filter_type="search",
                )

            if stats.get("emails"):
                render_gui_bar_chart(
                    "Top Emails",
                    [(e["email"], e["count"]) for e in stats["emails"]],
                    filter_type="search",
                )

            if stats.get("phones"):
                render_gui_bar_chart(
                    "Top Phone Numbers",
                    [(p["phone"], p["count"]) for p in stats["phones"]],
                    filter_type="search",
                )

            if stats.get("top_attachments"):
                render_gui_bar_chart(
                    "Top Attachments",
                    [
                        (a["name"], a["count"], a["name"])
                        for a in stats["top_attachments"]
                    ],
                    filter_type="search",
                )

            if stats.get("top_attachment_types"):
                render_gui_bar_chart(
                    "Top Attachment Types",
                    [
                        (t["extension"], t["count"])
                        for t in stats["top_attachment_types"]
                    ],
                    filter_type="search",
                )

            if stats["day_of_week"]:
                days = [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]
                items = [(d, stats["day_of_week"].get(d, 0)) for d in days]
                render_gui_bar_chart("Day of Week Distribution", items)

            if stats["hour_of_day"]:
                items = [
                    (f"{h:02}:00", stats["hour_of_day"].get(str(h), 0))
                    for h in range(24)
                ]
                render_gui_bar_chart("Hourly Distribution", items)

            txt.config(state=tk.DISABLED)

            # Re-set status
            self._update_status_bar()

        except Exception as e:
            self.status_label.config(text="Error calculating statistics")
            messagebox.showerror("Statistics Error", str(e))

    def _update_status_bar(self, message_index: int | None = None) -> None:
        """Update the status label with relevant information.

        This builds a detailed status message that includes search matches,
        message selection, and archive summary.
        """
        parts = []

        # 1. Search Progress
        if self._search_matches:
            parts.append(
                f"Match {self._current_match_idx + 1} of {len(self._search_matches)}"
            )

        # 2. Message Selection Progress
        if message_index is not None and len(self.messages) > 0:
            parts.append(f"Message {message_index + 1} of {len(self.messages)}")

        # 3. Archive Summary
        summary = f"Showing {len(self.messages)} of {self.total_msg_count} messages"
        if self.source_display_name:
            summary += f" from {self.source_display_name}"
        parts.append(summary)

        # Build final string
        self.status_label.config(text="  •  ".join(parts))

    def on_message_selected(self, _event: object | None = None) -> None:
        selected_items = self.message_list.selection()
        if not selected_items:
            return
        # Use the first selected item
        iid = selected_items[0]
        try:
            index = int(iid)
            self._render_message(index)
            self._update_status_bar(index)
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
            # We want to sort the items that are currently in the treeview
            # (which might be a subset of self.messages due to filtering)
            item_ids = self.message_list.get_children("")
            if not item_ids:
                return

            def get_sort_key(iid):
                # Try to use the underlying message data for accurate sorting
                try:
                    idx = int(iid)
                    msg = self.messages[idx]

                    if col == "Num":
                        return msg.header.msgnum or 0
                    elif col == "Size":
                        return len(msg.text) if msg.text else 0
                    elif col == "Date":
                        return _parse_qwk_date(msg.header.msgdate, msg.header.msgtime)
                    elif col == "From":
                        return msg.header.msgfrom.lower()
                    elif col == "To":
                        return msg.header.msgto.lower()
                    elif col == "Conference":
                        return self.board_dict.get(msg.header.confnum, "").lower()
                    elif col == "BBS":
                        return (msg.bbs_name or msg.bbs_id or "").lower()
                    elif col == "Flags":
                        return (
                            msg.header.status
                            + (";".join(msg.attachments) if msg.attachments else "")
                        ).lower()
                    elif col == "#0":
                        return msg.header.msgsubject.lower()
                except (ValueError, IndexError):
                    pass

                # Fallback to displayed text for items not mapping to self.messages (e.g. in tests)
                val = (
                    self.message_list.set(iid, col)
                    if col != "#0"
                    else self.message_list.item(iid, "text")
                )
                if col == "Num":
                    return int(val) if val and str(val).isdigit() else 0
                elif col == "Size":
                    try:
                        return float(val.split()[0])
                    except (ValueError, IndexError, AttributeError):
                        return 0
                elif col == "Date":
                    try:
                        parts = val.split()
                        date_part = parts[0] if len(parts) > 0 else ""
                        time_part = parts[1] if len(parts) > 1 else "00:00"
                        return _parse_qwk_date(date_part, time_part)
                    except Exception:
                        return datetime.datetime.min
                return str(val).lower()

            items = [(get_sort_key(iid), iid) for iid in item_ids]
            items.sort(key=lambda t: t[0], reverse=reverse)
        except Exception:
            # Fallback if sorting fails
            if items:
                try:
                    items.sort(key=lambda t: str(t[0]), reverse=reverse)
                except Exception:
                    pass

        # Rearrange items in sorted positions
        for index, (_, k) in enumerate(items):
            self.message_list.move(k, "", index)

        # Re-apply alternating tags after sorting to maintain zebra striping
        self._apply_zebra_striping()

        # Update all headings to show indicators and set correct toggle commands
        self._reset_column_headers(col, reverse)


def main() -> None:
    parser = argparse.ArgumentParser(description="PyQWK Graphical Reader")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Path to message archives, ZIP and TAR archives, or folders. Supports QWK, REP, JSON, JSONL, CSV, XML, RSS, mbox, EML, SQLite, Markdown, HTML, Plain Text, and data files (MESSAGES.DAT, REPLY.DAT).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    input_paths = expand_paths(args.paths)

    root = tk.Tk()
    QwkGuiApp(root, initial_paths=input_paths)
    root.mainloop()


if __name__ == "__main__":
    main()
