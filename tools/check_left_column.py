"""Смотрим низ левой колонки и считаем, сколько содержимого не влезает."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import customtkinter as ctk  # noqa: E402
from PIL import ImageGrab  # noqa: E402

import src.gui as gui  # noqa: E402

app = gui.App()
app.geometry("+6+0")
app.lift()
app.focus_force()
app.update()
time.sleep(0.8)
app.update()

def find_scrollable(widget):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkScrollableFrame):
            return child
        found = find_scrollable(child)
        if found is not None:
            return found
    return None


scroll = find_scrollable(app)
if scroll is None:
    raise SystemExit("не нашёл левую колонку")

canvas = scroll._parent_canvas
inner = scroll
scale = ctk.ScalingTracker.get_widget_scaling(app)
content = sum(
    child.winfo_reqheight() for child in inner.winfo_children()
) + 2 * gui.t.GAP_M * scale
print(f"содержимое ≈ {content / scale:.0f}, видимая часть = {canvas.winfo_height() / scale:.0f}")

canvas.yview_moveto(1.0)
app.update()
time.sleep(0.5)
app.update()

x, y = app.winfo_rootx(), app.winfo_rooty()
shot = ImageGrab.grab()
shot.crop((x + 10, y + 60, x + 600, y + app.winfo_height() - 100)).save(
    r"C:\Users\ASA\AppData\Local\Temp\mp_left_bottom.png"
)
print("снимок низа колонки сохранён")
app.destroy()
