"""Ищем виджеты, где подпись шире отведённого места."""

from __future__ import annotations

import sys
import time
import tkinter.font as tkfont
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import customtkinter as ctk  # noqa: E402

import src.gui as gui  # noqa: E402

SESSION = {"access_token": "x", "email": "editor@example.com", "account_id": "acc"}
gui.load_session = lambda *a, **k: SESSION

app = gui.App(initial_file=Path("9 сентября.docx"), initial_title="Проверка")
app.update()
time.sleep(0.6)
app.update()
app.record_entry.insert(0, "https://vkvideo.ru/video-1_1")
app.video_box.insert("1.0", "<iframe src=\"https://vkvideo.ru/video_ext.php?oid=-1&id=1\"></iframe>")
app.refresh_preview()
app.refresh_readiness()
app.update()

problems: list[tuple[int, str]] = []


def inner_label(widget):
    for attribute in ("_label", "_text_label"):
        inner = getattr(widget, attribute, None)
        if inner is not None:
            return inner
    return None


def walk(widget) -> None:
    for child in widget.winfo_children():
        inner = inner_label(child)
        if not isinstance(child, (ctk.CTkLabel, ctk.CTkButton, ctk.CTkCheckBox)):
            inner = None
        if inner is not None and str(child.cget("text") or ""):
            needed = inner.winfo_reqwidth()
            if isinstance(child, ctk.CTkCheckBox):
                needed += child._checkbox_width + 12
            available = child.winfo_width()
            slack = available - needed
            if slack < 4 or isinstance(child, ctk.CTkButton):
                problems.append(
                    (
                        slack,
                        f"{type(child).__name__} «{child.cget('text')}» "
                        f"нужно={needed} есть={available}",
                    )
                )
        walk(child)


walk(app)
for slack, message in sorted(problems):
    print(f"{slack:7.0f}  {message}")
if not problems:
    print("всё влезает")
app.destroy()
