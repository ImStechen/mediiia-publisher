"""Дизайн-токены Креативного хаба: палитра, типографика, метрики.

Зелёный #00AA01 и синий #182D66 сняты с фирменных макетов. Зелёный
работает только акцентом: на большой площади он слепит, а мелкий текст
на нём не читается, поэтому текст на зелёном — чёрный, как в логотипе.
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

# ---------- палитра ----------

BG = "#F2F3F5"  # фон окна
CARD = "#FFFFFF"  # фон карточки
SUNKEN = "#F7F8FA"  # утопленный блок: чип файла, пустое состояние

BORDER_CARD = "#E3E5E9"
BORDER_CTRL = "#D8DBE0"
BORDER_STRONG = "#B9BEC7"

TEXT = "#111318"
TEXT_MUTED = "#5B6270"
TEXT_FAINT = "#9AA0AB"

NAVY = "#182D66"  # структурный акцент: аппбар, заголовки секций
NAVY_HOVER = "#22376F"
NAVY_SOFT = "#EAEDF5"
NAVY_SUBTLE = "#A9B4D6"  # подпись на синем

GREEN = "#00AA01"  # акцент бренда, только CTA и мелкие риски
GREEN_HOVER = "#009301"
GREEN_TEXT = "#0A7A0B"  # зелёный, пригодный для текста
GREEN_SOFT = "#E8F6E8"

DANGER = "#C4162B"
DANGER_SOFT = "#FBE9EC"

DISABLED_BG = "#E3E5E9"
DISABLED_TEXT = "#9AA0AB"

SCROLLBAR = "#C6CAD2"

# ---------- метрики ----------

RADIUS = 0  # ноль скруглений — главный носитель фирменного стиля
# При толщине 1 CustomTkinter теряет нижнюю линию рамки на «неудачных»
# высотах и дробном масштабе экрана — прямоугольник получается разомкнутым.
BORDER_WIDTH = 2
FIELD_HEIGHT = 36
GAP_XS, GAP_S, GAP_M, GAP_L, GAP_XL = 4, 8, 12, 16, 24
CARD_PAD_X, CARD_PAD_TOP, CARD_PAD_BOTTOM = 16, 12, 12
FIELD_GAP = 10
APPBAR_HEIGHT = 56
FOOTER_HEIGHT = 76
FORM_WIDTH = 468


# ---------- типографика ----------


def font(size: int = 13, *, bold: bool = False, mono: bool = False) -> ctk.CTkFont:
    family = "Consolas" if mono else ("Segoe UI Semibold" if bold else "Segoe UI")
    return ctk.CTkFont(family=family, size=size, weight="bold" if bold else "normal")


# ---------- стили виджетов ----------


def entry(**overrides: Any) -> dict[str, Any]:
    style = {
        "height": FIELD_HEIGHT,
        "corner_radius": RADIUS,
        "border_width": BORDER_WIDTH,
        "border_color": BORDER_CTRL,
        "fg_color": CARD,
        "text_color": TEXT,
        "placeholder_text_color": TEXT_FAINT,
        "font": font(13),
    }
    style.update(overrides)
    return style


def textbox(**overrides: Any) -> dict[str, Any]:
    style = {
        "corner_radius": RADIUS,
        "border_width": BORDER_WIDTH,
        "border_color": BORDER_CTRL,
        "fg_color": CARD,
        "text_color": TEXT,
        "font": font(12),
        "wrap": "word",
    }
    style.update(overrides)
    return style


def primary_button(**overrides: Any) -> dict[str, Any]:
    style = {
        "height": 48,
        "corner_radius": RADIUS,
        "border_width": 0,
        "fg_color": GREEN,
        "hover_color": GREEN_HOVER,
        "text_color": "#000000",
        "text_color_disabled": DISABLED_TEXT,
        "font": font(15, bold=True),
    }
    style.update(overrides)
    return style


def secondary_button(**overrides: Any) -> dict[str, Any]:
    style = {
        "height": FIELD_HEIGHT,
        "corner_radius": RADIUS,
        "fg_color": CARD,
        "hover_color": NAVY_SOFT,
        "border_width": BORDER_WIDTH,
        "border_color": BORDER_STRONG,
        "text_color": NAVY,
        "font": font(13),
    }
    style.update(overrides)
    return style


def ghost_danger_button(**overrides: Any) -> dict[str, Any]:
    style = {
        "height": FIELD_HEIGHT,
        "corner_radius": RADIUS,
        "fg_color": "transparent",
        "hover_color": DANGER_SOFT,
        "border_width": 0,
        "text_color": DANGER,
        "font": font(13),
    }
    style.update(overrides)
    return style


def checkbox(**overrides: Any) -> dict[str, Any]:
    style = {
        "checkbox_width": 20,
        "checkbox_height": 20,
        "corner_radius": RADIUS,
        "border_width": BORDER_WIDTH,
        "border_color": BORDER_STRONG,
        "fg_color": GREEN,
        "hover_color": GREEN_HOVER,
        "checkmark_color": "#000000",
        "text_color": TEXT,
        "font": font(13),
    }
    style.update(overrides)
    return style


def card(**overrides: Any) -> dict[str, Any]:
    style = {
        "corner_radius": RADIUS,
        "fg_color": CARD,
        "border_width": BORDER_WIDTH,
        "border_color": BORDER_CARD,
        "width": 1,
        "height": 1,
    }
    style.update(overrides)
    return style


def row(parent: Any, **overrides: Any) -> ctk.CTkFrame:
    """Контейнер, размер которого задаёт содержимое.

    Внутренний canvas CTkFrame всегда просит свои width/height, а по
    умолчанию это 200×200 — такой контейнер распирает строку сетки.
    """
    options: dict[str, Any] = {
        "fg_color": "transparent",
        "corner_radius": RADIUS,
        "width": 1,
        "height": 1,
    }
    options.update(overrides)
    return ctk.CTkFrame(parent, **options)


def attach_focus_ring(widget: Any) -> None:
    """Рамка в фокусе меняет только цвет: ширину трогать нельзя, поедет вёрстка."""
    inner = getattr(widget, "_entry", None) or getattr(widget, "_textbox", None) or widget
    inner.bind("<FocusIn>", lambda _e: widget.configure(border_color=NAVY), add="+")
    inner.bind("<FocusOut>", lambda _e: widget.configure(border_color=BORDER_CTRL), add="+")
