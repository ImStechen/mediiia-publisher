"""Проверяем в живом окне: у каждого поля и карточки рамка замкнута?"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import customtkinter as ctk  # noqa: E402
from PIL import ImageGrab  # noqa: E402

import src.gui as gui  # noqa: E402

TOLERANCE = 10
SESSION = {"access_token": "x", "email": "editor@example.com", "account_id": "acc"}
gui.load_session = lambda *a, **k: SESSION

app = gui.App(initial_file=Path("9 сентября.docx"), initial_title="Проверка")
app.geometry("+6+0")
app.update()
time.sleep(1.0)
app.record_entry.insert(0, "https://vkvideo.ru/video-1_1")
app.video_box.insert("1.0", "<iframe src=\"https://vkvideo.ru/x\"></iframe>")
app.refresh_preview()
app.refresh_readiness()
app.update()
time.sleep(0.6)
app.update()

shot = ImageGrab.grab()
screen_w, screen_h = shot.size


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def close(pixel, target) -> bool:
    return all(abs(a - b) <= TOLERANCE for a, b in zip(pixel[:3], target))


def share(points, target) -> float:
    inside = [p for p in points if 0 <= p[0] < screen_w and 0 <= p[1] < screen_h]
    if not inside:
        return -1.0
    hits = sum(1 for point in inside if close(shot.getpixel(point), target))
    return hits / len(inside)


def check(widget, name: str) -> None:
    try:
        border_width = widget.cget("border_width")
        color = widget.cget("border_color")
    except (ValueError, AttributeError):
        return
    if not border_width or not isinstance(color, str) or not color.startswith("#"):
        return
    if not widget.winfo_ismapped():
        return
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    if w < 10 or h < 10:
        return
    # Виджет, вылезающий за окно, проверять бессмысленно: под ним чужие пиксели.
    win_x, win_y = app.winfo_rootx(), app.winfo_rooty()
    if x < win_x or y < win_y:
        return
    if x + w > win_x + app.winfo_width() or y + h > win_y + app.winfo_height():
        print(f"{name:34} {w:4}x{h:<4} — не влезает в окно, пропуск")
        return
    target = hex_to_rgb(color)
    depth = range(int(border_width) + 2)
    xs = range(x + 6, x + w - 6)
    ys = range(y + 6, y + h - 6)
    edges = {
        "верх": max(share([(px, y + d) for px in xs], target) for d in depth),
        "низ": max(share([(px, y + h - 1 - d) for px in xs], target) for d in depth),
        "лево": max(share([(x + d, py) for py in ys], target) for d in depth),
        "право": max(share([(x + w - 1 - d, py) for py in ys], target) for d in depth),
    }
    broken = {edge: value for edge, value in edges.items() if 0 <= value < 0.8}
    if len(broken) == 4 and all(value == 0 for value in broken.values()):
        status = "не видно (прокрутка), пропуск"
    elif broken:
        status = "ОБРЫВ " + ", ".join(f"{edge}={value:.2f}" for edge, value in broken.items())
    else:
        status = "OK"
    print(f"{name:34} {w:4}x{h:<4} bw={border_width} {status}")


def check_overflow(widget, name: str) -> None:
    """Содержимое не должно налезать на рамку контейнера с фиксированной высотой."""
    # У сегментед-кнопки внутренние кнопки закрывают рамку по задумке CTk.
    if isinstance(widget, ctk.CTkSegmentedButton) or not isinstance(widget, ctk.CTkFrame):
        return
    if not widget.winfo_ismapped():
        return
    children = [c for c in widget.winfo_children() if c.winfo_ismapped()]
    if not children:
        return
    height = widget.winfo_height()
    inner = 0
    for child in children:
        if child.winfo_class() == "Canvas":  # подложка самого CTkFrame
            continue
        inner = max(inner, child.winfo_y() + child.winfo_height())
    limit = height - int(widget.cget("border_width") or 0)
    if inner > limit:
        print(f"{name:34} содержимое {inner} > {limit} — налезает на рамку")


def walk(widget, path: str = "") -> None:
    for index, child in enumerate(widget.winfo_children()):
        name = f"{type(child).__name__}"
        if isinstance(child, (ctk.CTkEntry, ctk.CTkTextbox, ctk.CTkFrame, ctk.CTkButton)):
            check(child, f"{path}{name}#{index}")
            check_overflow(child, f"{path}{name}#{index}")
        walk(child, path)


walk(app)
app.destroy()
