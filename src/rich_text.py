"""Небольшой визуальный редактор для HTML, который понимает Mediiia."""

from __future__ import annotations

import html
import re
import tkinter as tk
from html.parser import HTMLParser
from tkinter import messagebox, simpledialog
from typing import Callable
from urllib.parse import urlparse

import customtkinter as ctk

from . import theme as t


_LINK_MD = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_BOLD_MD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_MD = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_ALLOWED_LINK = re.compile(r"^https?://", re.I)
_HISTORY_LIMIT = 100
_HISTORY_DELAY_MS = 600


def _markdown_blocks_to_html(markup: str) -> str:
    lines: list[str] = []
    for line in markup.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        prefix = ""
        stripped = line.lstrip()
        if stripped.startswith("# "):
            prefix, line = "h3", stripped[2:]
        elif stripped.startswith("> "):
            prefix, line = "blockquote", stripped[2:]
        line = _LINK_MD.sub(
            lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
            line,
        )
        line = _BOLD_MD.sub(r"<strong>\1</strong>", line)
        line = _ITALIC_MD.sub(r"<em>\1</em>", line)
        if prefix:
            line = f"<{prefix}>{line}</{prefix}>"
        lines.append(line)
    return "\n".join(lines)


class _MarkupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.length = 0
        self.stack: list[tuple[str, int, str]] = []
        self.spans: list[tuple[str, int, int, str]] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            self.handle_data("\n")
            return
        kind = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic"}.get(tag, tag)
        if kind not in {"bold", "italic", "a", "h3", "blockquote"}:
            return
        meta = ""
        if kind == "a":
            meta = dict(attrs).get("href") or ""
        self.stack.append((kind, self.length, meta))

    def handle_endtag(self, tag: str) -> None:
        kind = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic"}.get(
            tag.lower(), tag.lower()
        )
        for index in range(len(self.stack) - 1, -1, -1):
            opened, start, meta = self.stack[index]
            if opened == kind:
                self.stack.pop(index)
                if self.length > start:
                    self.spans.append((opened, start, self.length, meta))
                return

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        self.length += len(data)


def parse_markup(markup: str) -> tuple[str, list[tuple[str, int, int, str]]]:
    parser = _MarkupParser()
    parser.feed(_markdown_blocks_to_html(markup))
    return parser.text, parser.spans


def markup_to_html(markup: str) -> str:
    """Исходная разметка редактора → разрешённый HTML-фрагмент Mediiia."""
    result: list[str] = []
    for line in markup.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("# "):
            result.append(f"<h3>{stripped[2:]}</h3>")
        elif stripped.startswith("> "):
            result.append(stripped[2:])
        else:
            result.append(line)
    return "<br>".join(result).replace("<br><br>", "<br><br>")


def safe_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not _ALLOWED_LINK.match(value):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Нужна обычная ссылка http:// или https://")
    return value


class RichTextEditor(ctk.CTkFrame):
    """tk.Text с компактной панелью и безопасной сериализацией разметки."""

    def __init__(
        self,
        parent,
        *,
        height: int = 100,
        on_change: Callable[[], None] | None = None,
        toolbar: tuple[str, ...] = ("bold", "italic", "link", "heading", "quote"),
        font=None,
    ) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0, width=1, height=1)
        self.on_change = on_change
        self.links: dict[str, str] = {}
        self._link_counter = 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bar = t.row(self)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, t.GAP_XS))
        definitions = [
            ("bold", "B", 34, self.toggle_bold),
            ("italic", "I", 34, self.toggle_italic),
            ("link", "Ссылка", 68, self.edit_link),
            ("heading", "H3", 38, self.toggle_heading),
            ("quote", "Цитата", 62, self.toggle_quote),
        ]
        column = 0
        for key, label, width, command in definitions:
            if key not in toolbar:
                continue
            button = ctk.CTkButton(
                bar, text=label, width=width, command=command, **t.secondary_button(height=28)
            )
            if key == "bold":
                button.configure(font=t.font(12, bold=True))
            elif key == "italic":
                button.configure(font=("Segoe UI", 12, "italic"))
            button.grid(row=0, column=column, padx=(0, t.GAP_XS))
            column += 1

        ctk.CTkButton(
            bar, text="↶", width=32, command=self.undo, **t.secondary_button(height=28)
        ).grid(row=0, column=column, padx=(t.GAP_XS, 0))
        ctk.CTkButton(
            bar, text="↷", width=32, command=self.redo, **t.secondary_button(height=28)
        ).grid(row=0, column=column + 1, padx=(t.GAP_XS, 0))

        editor_font = font or t.font(12)
        font_size = (
            abs(int(editor_font.cget("size")))
            if hasattr(editor_font, "cget")
            else 12
        )
        self.textbox = ctk.CTkTextbox(
            self, height=height, **t.textbox(font=editor_font)
        )
        self.textbox.grid(row=1, column=0, sticky="nsew")
        self.text: tk.Text = self.textbox._textbox
        # Своя история: tk.Text запоминает только текст, но не теги форматирования.
        self.text.configure(undo=False)
        self._restoring = False
        self._history_job: str | None = None
        self._history: list[tuple[str, str]] = [("", "1.0")]
        self._history_index = 0
        self.text.tag_configure("bold", font=("Segoe UI Semibold", font_size))
        self.text.tag_configure("italic", font=("Segoe UI", font_size, "italic"))
        self.text.tag_configure(
            "heading",
            font=("Segoe UI Semibold", font_size + 2),
            spacing1=5,
            spacing3=3,
        )
        self.text.tag_configure(
            "quote",
            font=("Segoe UI", font_size, "italic"),
            lmargin1=14,
            lmargin2=14,
        )
        self.text.bind("<KeyRelease>", self._changed, add="+")
        self.text.bind("<<Paste>>", lambda _e: self.after_idle(self._changed), add="+")
        self.text.bind("<<Cut>>", lambda _e: self.after_idle(self._changed), add="+")
        self.text.bind("<Control-KeyPress>", self._ctrl_key, add="+")
        t.attach_focus_ring(self.textbox)

    def _ctrl_key(self, event: tk.Event) -> str | None:
        # Keycodes не зависят от русской раскладки.
        keycode = int(event.keycode)
        if keycode == 90:
            self.redo() if event.state & 0x1 else self.undo()
            return "break"
        if keycode == 89:
            self.redo()
            return "break"
        actions = {66: self.toggle_bold, 73: self.toggle_italic, 75: self.edit_link}
        action = actions.get(keycode)
        if action:
            action()
            return "break"
        return None

    def _changed(self, _event=None) -> None:
        self._schedule_history()
        self._notify()

    def _snapshot(self) -> tuple[str, str]:
        return self.get_markup(), self.text.index("insert")

    def _cancel_pending_history(self) -> None:
        if self._history_job is not None:
            self.after_cancel(self._history_job)
            self._history_job = None

    def _schedule_history(self) -> None:
        # Серия нажатий подряд отменяется одним шагом.
        if self._restoring:
            return
        self._cancel_pending_history()
        self._history_job = self.after(_HISTORY_DELAY_MS, self._push_history)

    def _push_history(self) -> None:
        if self._restoring:
            return
        self._cancel_pending_history()
        state = self._snapshot()
        if state[0] == self._history[self._history_index][0]:
            self._history[self._history_index] = state
            return
        del self._history[self._history_index + 1 :]
        self._history.append(state)
        if len(self._history) > _HISTORY_LIMIT:
            del self._history[0]
        self._history_index = len(self._history) - 1

    def _reset_history(self) -> None:
        self._cancel_pending_history()
        self._history = [self._snapshot()]
        self._history_index = 0

    def _restore(self, state: tuple[str, str]) -> None:
        markup, insert = state
        self._restoring = True
        try:
            self.set_markup(markup, keep_history=True)
            try:
                self.text.mark_set("insert", insert)
                self.text.see("insert")
            except tk.TclError:
                pass
        finally:
            self._restoring = False
        self._notify()

    def _notify(self) -> None:
        if self.on_change:
            self.on_change()

    def _selection(self, *, word_fallback: bool = True) -> tuple[str, str] | None:
        try:
            return self.text.index("sel.first"), self.text.index("sel.last")
        except tk.TclError:
            if not word_fallback:
                return None
            start = self.text.index("insert wordstart")
            end = self.text.index("insert wordend")
            return (start, end) if self.text.compare(start, "<", end) else None

    def _toggle(self, tag: str, *, lines: bool = False) -> None:
        selected = self._selection()
        if not selected:
            return
        self._push_history()
        start, end = selected
        if lines:
            start = self.text.index(f"{start} linestart")
            end = self.text.index(f"{end} lineend")
        ranges = self.text.tag_ranges(tag)
        covered = any(
            self.text.compare(start, ">=", ranges[i])
            and self.text.compare(end, "<=", ranges[i + 1])
            for i in range(0, len(ranges), 2)
        )
        if covered:
            self.text.tag_remove(tag, start, end)
        else:
            if tag == "heading":
                self.text.tag_remove("quote", start, end)
            elif tag == "quote":
                self.text.tag_remove("heading", start, end)
            self.text.tag_add(tag, start, end)
        self._push_history()
        self._notify()

    def toggle_bold(self) -> None:
        self._toggle("bold")

    def toggle_italic(self) -> None:
        self._toggle("italic")

    def toggle_heading(self) -> None:
        self._toggle("heading", lines=True)

    def toggle_quote(self) -> None:
        self._toggle("quote", lines=True)

    def _link_at_selection(self, start: str, end: str) -> tuple[str, str] | None:
        for tag in self.text.tag_names(start):
            if tag.startswith("link_"):
                return tag, self.links.get(tag, "")
        for tag in self.text.tag_names(f"{end}-1c"):
            if tag.startswith("link_"):
                return tag, self.links.get(tag, "")
        return None

    def edit_link(self) -> None:
        selected = self._selection()
        if not selected:
            return
        start, end = selected
        self._push_history()
        existing = self._link_at_selection(start, end)
        initial = existing[1] if existing else ""
        value = simpledialog.askstring(
            "Встроить ссылку",
            "Адрес ссылки (оставьте пустым, чтобы убрать):",
            initialvalue=initial,
            parent=self.winfo_toplevel(),
        )
        if value is None:
            return
        url = ""
        if value.strip():
            try:
                url = safe_url(value)
            except ValueError as exc:
                messagebox.showerror("Неверная ссылка", str(exc), parent=self)
                return
        if existing:
            ranges = self.text.tag_ranges(existing[0])
            self.text.tag_delete(existing[0])
            self.links.pop(existing[0], None)
            if ranges:
                start, end = str(ranges[0]), str(ranges[1])
        if url:
            self._add_link(start, end, url)
        self._push_history()
        self._notify()

    def _add_link(self, start: str, end: str, url: str) -> str:
        # Один символ не может вести сразу по двум адресам.
        for old_tag in tuple(self.links):
            ranges = self.text.tag_ranges(old_tag)
            for index in range(0, len(ranges), 2):
                if self.text.compare(ranges[index], "<", end) and self.text.compare(
                    ranges[index + 1], ">", start
                ):
                    self.text.tag_remove(old_tag, start, end)
        self._link_counter += 1
        tag = f"link_{self._link_counter}"
        self.links[tag] = url
        self.text.tag_add(tag, start, end)
        self.text.tag_configure(tag, foreground=t.NAVY, underline=True)
        return tag

    def undo(self) -> None:
        self._push_history()
        if self._history_index == 0:
            return
        self._history_index -= 1
        self._restore(self._history[self._history_index])

    def redo(self) -> None:
        self._cancel_pending_history()
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._restore(self._history[self._history_index])

    def set_markup(self, markup: str, *, keep_history: bool = False) -> None:
        text, spans = parse_markup(markup)
        self.text.delete("1.0", tk.END)
        for stale in tuple(self.links):
            self.text.tag_delete(stale)
        self.links.clear()
        self.text.insert("1.0", text)
        for kind, start, end, meta in spans:
            first = f"1.0+{start}c"
            last = f"1.0+{end}c"
            if kind == "a" and meta:
                try:
                    self._add_link(first, last, safe_url(meta))
                except ValueError:
                    pass
            elif kind in {"bold", "italic", "h3", "blockquote"}:
                self.text.tag_add(
                    {"h3": "heading", "blockquote": "quote"}.get(kind, kind), first, last
                )
        if not keep_history:
            self._reset_history()

    def get_markup(self) -> str:
        end = self.text.index("end-1c")
        line_count = int(end.split(".")[0])
        output: list[str] = []
        for line_no in range(1, line_count + 1):
            start = f"{line_no}.0"
            finish = f"{line_no}.end"
            prefix = ""
            tags = self.text.tag_names(start)
            if "heading" in tags:
                prefix = "# "
            elif "quote" in tags:
                prefix = "> "
            output.append(prefix + self._serialize_inline(start, finish))
        return "\n".join(output)

    def get_html(self) -> str:
        return markup_to_html(self.get_markup()).strip()

    def _serialize_inline(self, start: str, end: str) -> str:
        result: list[str] = []
        active: list[tuple[str, str]] = []
        index = start
        while self.text.compare(index, "<", end):
            names = set(self.text.tag_names(index))
            wanted: list[tuple[str, str]] = []
            if "bold" in names:
                wanted.append(("strong", ""))
            if "italic" in names:
                wanted.append(("em", ""))
            link = next((name for name in names if name.startswith("link_")), "")
            if link and self.links.get(link):
                wanted.append(("a", self.links[link]))
            common = 0
            while common < min(len(active), len(wanted)) and active[common] == wanted[common]:
                common += 1
            for tag, _meta in reversed(active[common:]):
                result.append(f"</{tag}>")
            for tag, meta in wanted[common:]:
                if tag == "a":
                    result.append(
                        f'<a href="{html.escape(meta, quote=True)}" '
                        'target="_blank" rel="noopener noreferrer">'
                    )
                else:
                    result.append(f"<{tag}>")
            active = wanted
            result.append(html.escape(self.text.get(index)))
            index = self.text.index(f"{index}+1c")
        for tag, _meta in reversed(active):
            result.append(f"</{tag}>")
        return "".join(result)

    def clear(self) -> None:
        self.set_markup("")
        self._notify()

