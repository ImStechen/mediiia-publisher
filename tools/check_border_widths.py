"""Проверяем, замыкается ли рамка: сами рисуем, сами снимаем экран, сами смотрим края."""

from __future__ import annotations

import time

import customtkinter as ctk
from PIL import ImageGrab

BORDER = (216, 219, 224)
TOLERANCE = 8

ctk.set_appearance_mode("Light")

app = ctk.CTk()
app.title("border test")
app.geometry("620x900")
app.configure(fg_color="#FFFFFF")

cases: list[tuple[str, int, int]] = [
    ("entry", 34, 1),
    ("entry", 36, 1),
    ("entry", 36, 2),
    ("textbox", 46, 2),
    ("textbox", 56, 2),
    ("frame", 56, 2),
    ("frame", 132, 2),
    ("frame", 201, 2),
    ("frame", 203, 1),
]

widgets: list[tuple[str, ctk.CTkBaseClass]] = []
row = 0
for kind, height, width in cases:
    ctk.CTkLabel(app, text=f"{kind} h={height} bw={width}", font=("Segoe UI", 11)).grid(
        row=row, column=0, sticky="w", padx=20, pady=(6, 1)
    )
    common = {
        "width": 420,
        "height": height,
        "corner_radius": 0,
        "border_width": width,
        "border_color": "#D8DBE0",
        "fg_color": "#FFFFFF",
    }
    if kind == "entry":
        widget = ctk.CTkEntry(app, **common)
    elif kind == "textbox":
        widget = ctk.CTkTextbox(app, **common)
    else:
        widget = ctk.CTkFrame(app, **common)
    widget.grid(row=row + 1, column=0, padx=20)
    widgets.append((f"{kind} h={height} bw={width}", widget))
    row += 2

app.update()
time.sleep(1.0)
app.update()

shot = ImageGrab.grab()


def close(pixel) -> bool:
    return all(abs(a - b) <= TOLERANCE for a, b in zip(pixel[:3], BORDER))


def edge_share(points) -> float:
    hits = sum(1 for point in points if close(shot.getpixel(point)))
    return hits / max(len(points), 1)


print(f"{'случай':22} {'верх':>6} {'низ':>6} {'лево':>6} {'право':>6}")
for name, widget in widgets:
    x = widget.winfo_rootx()
    y = widget.winfo_rooty()
    w = widget.winfo_width()
    h = widget.winfo_height()
    xs = range(x + 4, x + w - 4)
    ys = range(y + 4, y + h - 4)
    top = max(edge_share([(px, y + d) for px in xs]) for d in (0, 1))
    bottom = max(edge_share([(px, y + h - 1 - d) for px in xs]) for d in (0, 1, 2))
    left = max(edge_share([(x + d, py) for py in ys]) for d in (0, 1))
    right = max(edge_share([(x + w - 1 - d, py) for py in ys]) for d in (0, 1, 2))
    print(f"{name:22} {top:6.2f} {bottom:6.2f} {left:6.2f} {right:6.2f}")

app.destroy()
