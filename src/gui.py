"""Окно публикатора: исходник → блоки Mediiia → черновик."""

from __future__ import annotations

import html
import queue
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import theme as t
from .auth import can_resume, clear_session, ensure_session, forget_account
from .browsers import (
    BROWSERS,
    browser_label,
    load_browser_preference,
    open_in_browser,
    save_browser_preference,
)
from .config import (
    BOTTOM_BANNER_OPTIONS,
    TOP_BANNER_OPTIONS,
    banner_key_for_label,
    banner_labels,
    load_config,
    tag_names_from_config,
    tail_templates,
)
from .credentials import Credentials, clear_credentials, load_credentials, save_credentials
from .mediiia_api import MediiiaClient, MediiiaError
from .parser import Article, Block, TailSettings, article_to_markup, assemble, load_article
from .rich_text import RichTextEditor, parse_markup, safe_url

ctk.set_appearance_mode("Light")

MONTHS = (
    "января февраля марта апреля мая июня июля августа сентября "
    "октября ноября декабря"
).split()
_DATE_IN_NAME = re.compile(r"(\d{1,2})\s*([а-яё]+)", re.I)
_TAGS = re.compile(r"<[^>]+>")

# Tk определяет Ctrl+C/V по символу, поэтому при русской раскладке сочетания
# не работают. Ловим их по коду клавиши.
_CTRL_KEYCODES = {65: "select_all", 67: "<<Copy>>", 86: "<<Paste>>", 88: "<<Cut>>"}

PREVIEW_SNIPPET = 220
SERVICE_SOURCES = {
    "green",
    "green_top",
    "green_bottom",
    "intro",
    "partners",
    "outro",
    "video",
}
EXTRA_MISSING = {"Ссылка": "ссылки на запись", "Видео": "видео"}


def guess_event_date(name: str) -> str:
    """«9 сентября.docx» → «9 сентября 2026 года»."""
    match = _DATE_IN_NAME.search(name)
    if not match:
        return ""
    month = match.group(2).lower()
    if month not in MONTHS:
        return ""
    return f"{int(match.group(1))} {month} {datetime.now().year} года"


def blocks_word(count: int) -> str:
    if 11 <= count % 100 <= 14:
        return f"{count} блоков"
    last = count % 10
    if last == 1:
        return f"{count} блок"
    if 2 <= last <= 4:
        return f"{count} блока"
    return f"{count} блоков"


def plain_text(markup: str) -> str:
    text = markup.replace("<br><br>", "\n").replace("<br>", "\n")
    return html.unescape(_TAGS.sub("", text)).strip()


class LoginDialog(ctk.CTkToplevel):
    """Вход живёт в отдельном окне: он нужен раз в несколько недель."""

    def __init__(self, parent: App) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Вход в Mediiia")
        self.configure(fg_color=t.CARD)
        self.resizable(False, False)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)

        saved = load_credentials()
        browser = parent.browser_channel()
        session = can_resume(browser)

        body = t.row(self)
        body.grid(row=0, column=0, sticky="nsew", padx=t.GAP_XL, pady=t.GAP_XL)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body, text="ВХОД В MEDIIIA", font=t.font(12, bold=True), text_color=t.NAVY
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            body, text="Почта HSE", font=t.font(12), text_color=t.TEXT_MUTED
        ).grid(row=1, column=0, sticky="w", pady=(t.FIELD_GAP, t.GAP_XS))
        self.email = ctk.CTkEntry(body, placeholder_text="name@hse.ru", **t.entry())
        self.email.grid(row=2, column=0, sticky="ew")

        ctk.CTkLabel(body, text="Пароль", font=t.font(12), text_color=t.TEXT_MUTED).grid(
            row=3, column=0, sticky="w", pady=(t.FIELD_GAP, t.GAP_XS)
        )
        self.password = ctk.CTkEntry(body, show="•", placeholder_text="••••••••", **t.entry())
        self.password.grid(row=4, column=0, sticky="ew")

        self.remember = ctk.BooleanVar(value=bool(saved.email))
        ctk.CTkCheckBox(
            body,
            text="Запомнить на этом компьютере",
            variable=self.remember,
            **t.checkbox(),
        ).grid(row=5, column=0, sticky="w", pady=(t.FIELD_GAP, 0))

        self.hint = ctk.CTkLabel(
            body,
            text=f"Откроется {browser_label(browser)} — вход подтвердится там.",
            font=t.font(11),
            text_color=t.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=380,
        )
        self.hint.grid(row=6, column=0, sticky="ew", pady=(t.GAP_M, 0))

        self.login_btn = ctk.CTkButton(
            body,
            text="Войти",
            width=140,
            command=self.on_login,
            **t.primary_button(height=40),
        )
        self.login_btn.grid(row=7, column=0, sticky="e", pady=(t.GAP_M, 0))

        if session:
            current = t.row(body)
            current.grid(row=8, column=0, sticky="ew", pady=(t.GAP_L, 0))
            current.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                current,
                text=f"Сейчас: {session.get('email') or 'сессия есть'}",
                font=t.font(12),
                text_color=t.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkButton(
                current, text="Выйти", width=90, command=self.on_logout, **t.ghost_danger_button()
            ).grid(row=0, column=1, sticky="e")

        if saved.email:
            self.email.insert(0, saved.email)
        if saved.password:
            self.password.insert(0, saved.password)

        for widget in (self.email, self.password):
            t.attach_focus_ring(widget)
        self.parent.install_clipboard_fix(self)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.geometry(self._centered(440, self._needed_height()))
        self.after(120, self._grab)

    def _needed_height(self) -> int:
        """Высота по содержимому: со строкой «Сейчас: …» окно выше."""
        self.update_idletasks()
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        return int(self.winfo_reqheight() / scale) + 8

    def _centered(self, width: int, height: int) -> str:
        self.parent.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 3
        return f"{width}x{height}+{max(x, 0)}+{max(y, 0)}"

    def _grab(self) -> None:
        try:
            self.grab_set()
            self.email.focus_set()
        except tk.TclError:
            pass

    def on_logout(self) -> None:
        forget_account()
        self.parent.refresh_account_chip()
        self.parent.set_status("Вы вышли из аккаунта")
        self.destroy()

    def on_login(self) -> None:
        email = self.email.get().strip()
        password = self.password.get()
        browser = self.parent.browser_channel()
        if not email or not password:
            self.hint.configure(text="Введите почту и пароль.", text_color=t.DANGER)
            return

        if self.remember.get():
            save_credentials(Credentials(email=email, password=password))
        else:
            clear_credentials()

        self.login_btn.configure(state="disabled", text="Вхожу…")
        self.hint.configure(
            text=f"Откройте {browser_label(browser)} и подтвердите вход.",
            text_color=t.TEXT_FAINT,
        )

        def work() -> None:
            try:
                clear_session()
                session = ensure_session(
                    force_login=True,
                    email=email,
                    password=password,
                    browser=browser,
                )
            except Exception as exc:  # сеть, браузер, неверный пароль
                message = str(exc)
                self.parent.post(lambda: self._failed(message))
                return
            self.parent.post(lambda: self._succeeded(session.get("email") or email))

        threading.Thread(target=work, daemon=True).start()

    def _failed(self, message: str) -> None:
        if self.winfo_exists():
            self.login_btn.configure(state="normal", text="Войти")
            self.hint.configure(text=f"Войти не удалось: {message}", text_color=t.DANGER)
        self.parent.set_status("Войти не удалось", kind="error")

    def _succeeded(self, who: str) -> None:
        self.parent.refresh_account_chip()
        self.parent.set_status(f"Вы вошли как {who}")
        self.parent.refresh_readiness()
        if self.winfo_exists():
            self.destroy()
        if self.parent.publish_after_login:
            self.parent.publish_after_login = False
            self.parent.on_publish()


class PartnerDialog(ctk.CTkToplevel):
    def __init__(self, parent: App) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Добавить инфопартнёра")
        self.configure(fg_color=t.CARD)
        self.resizable(False, False)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)

        body = t.row(self)
        body.grid(row=0, column=0, sticky="nsew", padx=t.GAP_XL, pady=t.GAP_XL)
        body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            body, text="Название", font=t.font(12), text_color=t.TEXT_MUTED
        ).grid(row=0, column=0, sticky="w")
        self.name = ctk.CTkEntry(body, width=420, **t.entry())
        self.name.grid(row=1, column=0, sticky="ew", pady=(t.GAP_XS, t.GAP_M))
        ctk.CTkLabel(
            body, text="Ссылка", font=t.font(12), text_color=t.TEXT_MUTED
        ).grid(row=2, column=0, sticky="w")
        self.url = ctk.CTkEntry(body, placeholder_text="https://…", **t.entry())
        self.url.grid(row=3, column=0, sticky="ew", pady=(t.GAP_XS, t.GAP_S))
        self.error = ctk.CTkLabel(
            body, text="", font=t.font(11), text_color=t.DANGER, anchor="w"
        )
        self.error.grid(row=4, column=0, sticky="ew")
        buttons = t.row(body)
        buttons.grid(row=5, column=0, sticky="e", pady=(t.GAP_M, 0))
        ctk.CTkButton(
            buttons, text="Отмена", width=100, command=self.destroy, **t.secondary_button()
        ).grid(row=0, column=0)
        ctk.CTkButton(
            buttons, text="Добавить", width=110, command=self.save, **t.primary_button()
        ).grid(row=0, column=1, padx=(t.GAP_S, 0))

        parent.install_clipboard_fix(self)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.save())
        self.after(30, self._finish_open)

    def _finish_open(self) -> None:
        self.update_idletasks()
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        self.geometry(f"480x{int(self.winfo_reqheight() / scale)}")
        self.grab_set()
        self.name.focus_set()

    def save(self) -> None:
        name = self.name.get().strip()
        if not name:
            self.error.configure(text="Введите название партнёра.")
            return
        try:
            url = safe_url(self.url.get())
        except ValueError as exc:
            self.error.configure(text=str(exc))
            return
        if not url:
            self.error.configure(text="Введите ссылку партнёра.")
            return
        self.parent.insert_partner(name, url)
        self.destroy()


class App(ctk.CTk):
    def __init__(self, initial_file: Path | None = None, initial_title: str | None = None) -> None:
        super().__init__()
        self.title("Mediiia публикатор")
        self.geometry("1360x780")
        self.minsize(1180, 660)
        self.configure(fg_color=t.BG)

        self.cfg = load_config()
        self.templates = tail_templates(self.cfg)
        configured_browser = str(self.cfg.get("browser") or "chrome")
        preferred_browser = load_browser_preference(configured_browser)
        self.browser_choice = ctk.StringVar(value=browser_label(preferred_browser))
        self.top_banner_choice = ctk.StringVar(value=TOP_BANNER_OPTIONS["promo"][0])
        self.bottom_banner_choice = ctk.StringVar(value=BOTTOM_BANNER_OPTIONS["site"][0])
        self.article: Article | None = None
        self.source_path: Path | None = None
        self.publish_after_login = False
        self._busy = False
        self._parse_job: str | None = None
        self._preview_job: str | None = None
        self._ui_queue: queue.Queue = queue.Queue()

        # minsize уходит в Tk напрямую, в физических пикселях, — масштаб экрана
        # приходится учитывать руками, иначе колонка окажется уже задуманной.
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        self.grid_columnconfigure(0, weight=0, minsize=int(t.FORM_WIDTH * scale))
        self.grid_columnconfigure(1, weight=1, minsize=int(620 * scale))
        self.grid_rowconfigure(2, weight=1)

        self._build_appbar()
        self._build_progress()
        self._build_form()
        self._build_preview()
        self._build_footer()
        self.install_clipboard_fix(self)
        self._bind_hotkeys()
        self._enable_drop()
        self.after(80, self._pump)

        if initial_title:
            self.title_entry.insert(0, initial_title)
        if initial_file:
            self.after(200, lambda: self.load_path(Path(initial_file), keep_title=True))
        else:
            self.refresh_preview()
            self.refresh_readiness()

    # ---------- аппбар и прогресс ----------

    def _build_appbar(self) -> None:
        bar = ctk.CTkFrame(self, height=t.APPBAR_HEIGHT, corner_radius=0, fg_color=t.NAVY)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkFrame(
            bar, width=10, height=t.APPBAR_HEIGHT, corner_radius=0, fg_color=t.GREEN
        ).grid(row=0, column=0, sticky="ns")
        ctk.CTkLabel(
            bar,
            text="MEDIIIA ПУБЛИКАТОР",
            font=t.font(15, bold=True),
            text_color="#FFFFFF",
        ).grid(row=0, column=1, sticky="w", padx=(t.GAP_L, t.GAP_M))
        ctk.CTkLabel(
            bar,
            text="Черновик на Mediiia. Фото и публикация — вручную",
            font=t.font(12),
            text_color=t.NAVY_SUBTLE,
        ).grid(row=0, column=2, sticky="w")

        self.account_btn = ctk.CTkButton(
            bar,
            text="",
            height=32,
            corner_radius=0,
            fg_color="transparent",
            hover_color=t.NAVY_HOVER,
            text_color="#FFFFFF",
            font=t.font(13),
            command=self.open_login,
        )
        self.account_btn.grid(row=0, column=3, sticky="e", padx=(0, t.GAP_L))
        self.refresh_account_chip()

    def _build_progress(self) -> None:
        self.progress = ctk.CTkProgressBar(
            self, height=3, corner_radius=0, fg_color=t.BORDER_CARD, progress_color=t.GREEN
        )
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.progress.set(0)
        self.progress.grid_remove()

    # ---------- левая колонка: форма ----------

    def _section_title(self, parent, text: str, row: int) -> None:
        holder = t.row(parent)
        holder.grid(row=row, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.CARD_PAD_TOP, t.GAP_M))
        ctk.CTkFrame(holder, width=3, height=14, corner_radius=0, fg_color=t.GREEN).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(holder, text=text, font=t.font(12, bold=True), text_color=t.NAVY).grid(
            row=0, column=1, sticky="w", padx=(t.GAP_S, 0)
        )

    def _field_label(self, parent, text: str, row: int, *, required: bool = False,
                     note: str = "", first: bool = False) -> None:
        holder = t.row(parent)
        holder.grid(
            row=row,
            column=0,
            sticky="ew",
            padx=t.CARD_PAD_X,
            pady=(0 if first else t.FIELD_GAP, t.GAP_XS),
        )
        ctk.CTkLabel(holder, text=text, font=t.font(12), text_color=t.TEXT_MUTED).grid(
            row=0, column=0, sticky="w"
        )
        if required:
            ctk.CTkLabel(
                holder,
                text="нужно",
                font=t.font(10, bold=True),
                text_color=t.GREEN_TEXT,
                fg_color=t.GREEN_SOFT,
                corner_radius=0,
                width=58,
                height=20,
            ).grid(row=0, column=1, sticky="w", padx=(t.GAP_S, 0))
        elif note:
            ctk.CTkLabel(holder, text=note, font=t.font(11), text_color=t.TEXT_FAINT).grid(
                row=0, column=1, sticky="w", padx=(t.GAP_XS, 0)
            )

    def _build_form(self) -> None:
        column = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=t.SCROLLBAR,
            scrollbar_button_hover_color=t.BORDER_STRONG,
        )
        column.grid(row=2, column=0, sticky="nsew", padx=(t.GAP_L, t.GAP_M), pady=t.GAP_L)
        column.grid_columnconfigure(0, weight=1)
        self.form_column = column

        self._build_source_card(column)
        self._build_tail_card(column)
        self._build_options_card(column)

    def _build_source_card(self, parent) -> None:
        card = ctk.CTkFrame(parent, **t.card())
        card.grid(row=0, column=0, sticky="ew", pady=(0, t.GAP_M))
        card.grid_columnconfigure(0, weight=1)
        self._section_title(card, "1 · ИСХОДНИК", row=0)

        self.dropzone = ctk.CTkFrame(
            card,
            height=104,
            corner_radius=0,
            fg_color=t.SUNKEN,
            border_width=t.BORDER_WIDTH,
            border_color=t.BORDER_STRONG,
        )
        self.dropzone.grid(row=1, column=0, sticky="ew", padx=t.CARD_PAD_X)
        self.dropzone.grid_propagate(False)
        self.dropzone.grid_columnconfigure(0, weight=1)
        self.dropzone.grid_rowconfigure(0, weight=1)
        self.dropzone.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            self.dropzone,
            text="Перетащите .docx сюда",
            font=t.font(15, bold=True),
            text_color=t.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="s")
        ctk.CTkLabel(
            self.dropzone,
            text="или Ctrl+V, или выберите файл",
            font=t.font(12),
            text_color=t.TEXT_FAINT,
        ).grid(row=1, column=0, sticky="n", pady=(t.GAP_XS, 0))

        self.file_chip = ctk.CTkFrame(
            card, height=74, corner_radius=0, fg_color=t.SUNKEN,
            border_width=t.BORDER_WIDTH, border_color=t.BORDER_STRONG,
        )
        self.file_chip.grid(row=2, column=0, sticky="ew", padx=t.CARD_PAD_X)
        self.file_chip.grid_propagate(False)
        self.file_chip.grid_columnconfigure(0, weight=1)
        self.file_chip.grid_remove()

        self.chip_name = ctk.CTkLabel(
            self.file_chip, text="", font=t.font(13, bold=True), text_color=t.TEXT, anchor="w"
        )
        self.chip_name.grid(row=0, column=0, sticky="sw", padx=t.GAP_M, pady=(t.GAP_M, 0))
        self.chip_meta = ctk.CTkLabel(
            self.file_chip, text="", font=t.font(11), text_color=t.TEXT_MUTED, anchor="w"
        )
        self.chip_meta.grid(row=1, column=0, sticky="nw", padx=t.GAP_M, pady=(0, t.GAP_M))
        ctk.CTkButton(
            self.file_chip,
            text="Перечитать",
            width=100,
            command=self.reload_file,
            **t.secondary_button(height=28),
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=t.GAP_M)

        buttons = t.row(card)
        buttons.grid(row=3, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.GAP_M, t.CARD_PAD_BOTTOM))
        ctk.CTkButton(
            buttons, text="Выбрать файл…", width=150, command=self.open_file, **t.secondary_button()
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            buttons, text="Вставить", width=110, command=self.paste_from_clipboard,
            **t.secondary_button(),
        ).grid(row=0, column=1, sticky="w", padx=(t.GAP_S, 0))

    def _build_tail_card(self, parent) -> None:
        card = ctk.CTkFrame(parent, **t.card())
        card.grid(row=1, column=0, sticky="ew", pady=(0, t.GAP_M))
        card.grid_columnconfigure(0, weight=1)
        self._section_title(card, "2 · ЗАГОЛОВОК И КОНЦОВКА", row=0)

        self._field_label(card, "Заголовок статьи", row=1, required=True, first=True)
        self.title_entry = ctk.CTkEntry(
            card, placeholder_text="Первая строка файла", **t.entry()
        )
        self.title_entry.grid(row=2, column=0, sticky="ew", padx=t.CARD_PAD_X)

        self._field_label(card, "Дата ивента", row=3, required=True)
        dates = t.row(card)
        dates.grid(row=4, column=0, sticky="ew", padx=t.CARD_PAD_X)
        dates.grid_columnconfigure(0, weight=1)
        self.date_entry = ctk.CTkEntry(
            dates, placeholder_text="9 сентября 2026 года", **t.entry()
        )
        self.date_entry.grid(row=0, column=0, sticky="ew")
        self.time_from = ctk.CTkEntry(dates, **t.entry(width=74))
        self.time_from.grid(row=0, column=1, padx=(t.GAP_S, t.GAP_XS))
        self.time_from.insert(0, self.templates.get("default_time_from", "18:30"))
        ctk.CTkLabel(dates, text="–", font=t.font(13), text_color=t.TEXT_MUTED).grid(row=0, column=2)
        self.time_to = ctk.CTkEntry(dates, **t.entry(width=74))
        self.time_to.grid(row=0, column=3, padx=(t.GAP_XS, 0))
        self.time_to.insert(0, self.templates.get("default_time_to", "21:00"))

        self._field_label(card, "Ссылка на запись", row=5, note="· необязательно")
        self.record_entry = ctk.CTkEntry(
            card, placeholder_text="https://vkvideo.ru/video-…", **t.entry()
        )
        self.record_entry.grid(row=6, column=0, sticky="ew", padx=t.CARD_PAD_X)

        self._field_label(card, "Код вставки VK Видео", row=7, note="· необязательно")
        self.video_box = ctk.CTkTextbox(card, height=56, **t.textbox())
        self.video_box.grid(row=8, column=0, sticky="ew", padx=t.CARD_PAD_X)
        ctk.CTkLabel(
            card,
            text="На странице записи: Поделиться → Экспортировать",
            font=t.font(11),
            text_color=t.TEXT_FAINT,
            anchor="w",
        ).grid(row=9, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.GAP_XS, 0))

        self._field_label(card, "Дополнительно", row=10, note="· необязательно")
        self.extra_editor = RichTextEditor(
            card,
            height=72,
            toolbar=("bold", "italic", "link", "heading", "quote"),
            on_change=self.schedule_preview,
        )
        self.extra_editor.grid(row=11, column=0, sticky="ew", padx=t.CARD_PAD_X)

        self._field_label(card, "Инфопартнёры", row=12, note="· необязательно")
        self.partners_box = ctk.CTkTextbox(card, height=44, **t.textbox())
        self.partners_box.grid(row=13, column=0, sticky="ew", padx=t.CARD_PAD_X)
        ctk.CTkButton(
            card,
            text="+ Добавить партнёра",
            width=156,
            command=self.add_partner,
            **t.secondary_button(height=28),
        ).grid(
            row=14,
            column=0,
            sticky="w",
            padx=t.CARD_PAD_X,
            pady=(t.GAP_XS, t.CARD_PAD_BOTTOM),
        )

        self.tail_inputs = [
            self.title_entry,
            self.date_entry,
            self.time_from,
            self.time_to,
            self.record_entry,
            self.video_box,
            self.partners_box,
        ]
        for widget in self.tail_inputs:
            t.attach_focus_ring(widget)
            inner = getattr(widget, "_entry", None) or getattr(widget, "_textbox", None)
            if inner is not None:
                inner.bind("<KeyRelease>", lambda _e: self.schedule_preview(), add="+")

    def _build_options_card(self, parent) -> None:
        card = ctk.CTkFrame(parent, **t.card())
        card.grid(row=2, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._section_title(card, "3 · ПЛАШКИ И ПАРАМЕТРЫ", row=0)

        self._field_label(card, "Верхняя зелёная плашка", row=1, first=True)
        self.top_banner_menu = ctk.CTkOptionMenu(
            card,
            values=banner_labels(TOP_BANNER_OPTIONS),
            variable=self.top_banner_choice,
            command=lambda selected: self.on_banner_changed("top", selected),
            **t.option_menu(),
        )
        self.top_banner_menu.grid(row=2, column=0, sticky="ew", padx=t.CARD_PAD_X)
        self.top_banner_hint = ctk.CTkLabel(
            card,
            text="",
            font=t.font(11),
            text_color=t.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=380,
        )
        self.top_banner_hint.grid(
            row=3, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.GAP_XS, 0)
        )
        self.top_banner_editor = RichTextEditor(
            card,
            height=82,
            toolbar=("bold", "italic", "link"),
            on_change=self.schedule_preview,
        )
        self.top_banner_editor.grid(
            row=4, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.GAP_XS, 0)
        )
        self.top_banner_editor.grid_remove()

        self._field_label(card, "Нижняя зелёная плашка", row=5)
        self.bottom_banner_menu = ctk.CTkOptionMenu(
            card,
            values=banner_labels(BOTTOM_BANNER_OPTIONS),
            variable=self.bottom_banner_choice,
            command=lambda selected: self.on_banner_changed("bottom", selected),
            **t.option_menu(),
        )
        self.bottom_banner_menu.grid(row=6, column=0, sticky="ew", padx=t.CARD_PAD_X)
        self.bottom_banner_hint = ctk.CTkLabel(
            card,
            text="",
            font=t.font(11),
            text_color=t.TEXT_FAINT,
            anchor="w",
            justify="left",
            wraplength=380,
        )
        self.bottom_banner_hint.grid(
            row=7, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.GAP_XS, 0)
        )
        self.bottom_banner_editor = RichTextEditor(
            card,
            height=82,
            toolbar=("bold", "italic", "link"),
            on_change=self.schedule_preview,
        )
        self.bottom_banner_editor.grid(
            row=8, column=0, sticky="ew", padx=t.CARD_PAD_X, pady=(t.GAP_XS, 0)
        )
        self.bottom_banner_editor.grid_remove()
        self.on_banner_changed("top", self.top_banner_choice.get())
        self.on_banner_changed("bottom", self.bottom_banner_choice.get())

        self.open_browser_var = ctk.BooleanVar(
            value=bool(self.cfg.get("open_draft_after_create", True))
        )
        ctk.CTkCheckBox(
            card,
            text="Открыть черновик после создания",
            variable=self.open_browser_var,
            **t.checkbox(),
        ).grid(row=9, column=0, sticky="w", padx=t.CARD_PAD_X, pady=(t.GAP_L, 0))

        browser_row = t.row(card)
        browser_row.grid(
            row=10,
            column=0,
            sticky="ew",
            padx=t.CARD_PAD_X,
            pady=(t.GAP_M, 0),
        )
        browser_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            browser_row,
            text="Браузер",
            font=t.font(12),
            text_color=t.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w", padx=(0, t.GAP_M))
        ctk.CTkOptionMenu(
            browser_row,
            values=list(BROWSERS.values()),
            variable=self.browser_choice,
            command=self.on_browser_changed,
            height=t.FIELD_HEIGHT,
            corner_radius=0,
            fg_color=t.NAVY,
            button_color=t.NAVY,
            button_hover_color=t.NAVY_HOVER,
            dropdown_fg_color=t.CARD,
            dropdown_hover_color=t.NAVY_SOFT,
            dropdown_text_color=t.TEXT,
            text_color="#FFFFFF",
            font=t.font(12),
            dropdown_font=t.font(12),
        ).grid(row=0, column=1, sticky="ew")

        tags = tag_names_from_config(self.cfg)
        summary = f"Теги: {len(tags)} · {tags[0]}" if tags else "Теги не заданы"
        if len(tags) > 1:
            summary += f", +{len(tags) - 1}"
        ctk.CTkLabel(card, text=summary, font=t.font(11), text_color=t.TEXT_FAINT, anchor="w").grid(
            row=11, column=0, sticky="ew", padx=t.CARD_PAD_X,
            pady=(t.GAP_M, t.CARD_PAD_BOTTOM),
        )

    # ---------- правая колонка: предпросмотр ----------

    def _build_preview(self) -> None:
        panel = t.row(self)
        panel.grid(row=2, column=1, sticky="nsew", padx=(0, t.GAP_L), pady=t.GAP_L)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = t.row(panel)
        header.grid(row=0, column=0, sticky="ew", pady=(0, t.GAP_S))
        header.grid_columnconfigure(1, weight=1)

        badge = t.row(header)
        badge.grid(row=0, column=0, sticky="w")
        ctk.CTkFrame(badge, width=3, height=14, corner_radius=0, fg_color=t.GREEN).grid(
            row=0, column=0, sticky="w"
        )
        self.preview_title = ctk.CTkLabel(
            badge, text="ЧЕРНОВИК", font=t.font(12, bold=True), text_color=t.NAVY
        )
        self.preview_title.grid(row=0, column=1, sticky="w", padx=(t.GAP_S, 0))

        self.view_switch = ctk.CTkSegmentedButton(
            header,
            values=["Блоки", "Исходник"],
            width=250,
            height=t.FIELD_HEIGHT,
            corner_radius=0,
            border_width=2,
            dynamic_resizing=False,
            fg_color="#E9EBEF",
            selected_color=t.NAVY,
            selected_hover_color=t.NAVY_HOVER,
            unselected_color="#6B7280",
            unselected_hover_color=t.TEXT_MUTED,
            text_color="#FFFFFF",
            font=t.font(12),
            command=self.switch_view,
        )
        self.view_switch.grid(row=0, column=2, sticky="e")
        self.view_switch.set("Блоки")

        self.preview = ctk.CTkTextbox(panel, **t.textbox(font=t.font(12)))
        self.preview.grid(row=1, column=0, sticky="nsew")
        self.preview.configure(state="disabled")
        self._configure_preview_tags()

        self.source_editor = RichTextEditor(
            panel,
            height=400,
            font=t.font(13),
            on_change=self.schedule_parse,
        )
        self.source_editor.grid(row=1, column=0, sticky="nsew")
        self.source_editor.grid_remove()

    def _configure_preview_tags(self) -> None:
        box = getattr(self.preview, "_textbox", None)
        if box is None:
            return
        box.configure(spacing1=4, spacing3=6, padx=14, pady=10)
        box.tag_config("num", foreground=t.TEXT_FAINT, font=("Consolas", 11))
        box.tag_config("kind", foreground=t.NAVY, font=("Segoe UI Semibold", 10))
        box.tag_config("kind_service", foreground=t.GREEN_TEXT, font=("Segoe UI Semibold", 10))
        box.tag_config(
            "body", foreground=t.TEXT, font=("Segoe UI", 12), lmargin1=34, lmargin2=34, spacing3=8
        )
        box.tag_config("h3", foreground=t.TEXT, font=("Segoe UI Semibold", 13), lmargin1=34)
        box.tag_config(
            "quote",
            foreground="#3A4150",
            font=("Segoe UI", 12, "italic"),
            lmargin1=44,
            lmargin2=44,
            spacing3=8,
        )
        box.tag_config("headline", foreground=t.TEXT, font=("Segoe UI Semibold", 16), spacing3=10)
        box.tag_config("empty", foreground=t.TEXT_FAINT, font=("Segoe UI", 12), justify="center")
        box.tag_config("preview_bold", font=("Segoe UI Semibold", 12))
        box.tag_config("preview_italic", font=("Segoe UI", 12, "italic"))
        self._preview_link_counter = 0

    # ---------- футер ----------

    def _build_footer(self) -> None:
        ctk.CTkFrame(self, height=1, corner_radius=0, fg_color=t.BORDER_CARD).grid(
            row=3, column=0, columnspan=2, sticky="ew"
        )
        footer = ctk.CTkFrame(self, height=t.FOOTER_HEIGHT, corner_radius=0, fg_color=t.CARD)
        footer.grid(row=4, column=0, columnspan=2, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_columnconfigure(0, weight=1)

        self.status_area = t.row(footer)
        self.status_area.grid(row=0, column=0, sticky="w", padx=t.GAP_L)

        self.reset_btn = ctk.CTkButton(
            footer, text="Сбросить всё", width=150, command=self.reset_all,
            **t.ghost_danger_button(),
        )
        self.reset_btn.grid(row=0, column=1, sticky="e", padx=(0, t.GAP_M))

        self.publish_btn = ctk.CTkButton(
            footer, text="Создать черновик", width=300, command=self.on_publish,
            **t.primary_button(),
        )
        self.publish_btn.grid(row=0, column=2, sticky="e", padx=(0, t.GAP_L))

        self.status_kind = "idle"
        self.status_message = "Перетащите .docx или нажмите Ctrl+V"

    # ---------- буфер обмена и горячие клавиши ----------

    def install_clipboard_fix(self, root) -> None:
        """Ctrl+C/V/X/A во всех полях — независимо от раскладки клавиатуры."""

        def walk(widget) -> None:
            for child in widget.winfo_children():
                if child.winfo_class() in {"Text", "Entry", "TEntry"}:
                    child.bind("<Control-KeyPress>", self._on_ctrl_key, add="+")
                walk(child)

        walk(root)

    def _on_ctrl_key(self, event):
        action = _CTRL_KEYCODES.get(event.keycode)
        if not action:
            return None
        widget = event.widget
        try:
            if action == "select_all":
                if widget.winfo_class() == "Text":
                    widget.tag_add("sel", "1.0", "end-1c")
                else:
                    widget.select_range(0, tk.END)
            else:
                widget.event_generate(action)
        except tk.TclError:
            return None
        return "break"

    def _bind_hotkeys(self) -> None:
        self.bind("<Control-KeyPress>", self._on_global_ctrl, add="+")
        self.bind("<F5>", lambda _e: self.reload_file())
        self.bind("<Control-Return>", lambda _e: self.on_publish())

    def _on_global_ctrl(self, event):
        # Поля перехватывают Ctrl+V сами; сюда событие доходит только вне полей.
        if event.keycode == 86:
            self.paste_from_clipboard()
            return "break"
        if event.keycode == 79:
            self.open_file()
            return "break"
        return None

    def _enable_drop(self) -> None:
        """windnd вешаем на всё окно: зона сброса схлопывается после загрузки."""
        try:
            import windnd

            def dropped(files):
                if not files:
                    return
                path = files[0]
                if isinstance(path, bytes):
                    path = path.decode("utf-8", errors="ignore")
                self.load_path(Path(path))

            windnd.hook_dropfiles(self, func=dropped)
        except Exception:
            pass

    # ---------- обмен с рабочими потоками ----------

    def post(self, action) -> None:
        """Отложить действие до главного потока: Tk из потоков дёргать нельзя."""
        self._ui_queue.put(action)

    def _pump(self) -> None:
        while True:
            try:
                action = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except tk.TclError:
                pass
        self.after(80, self._pump)

    # ---------- состояние ----------

    def refresh_account_chip(self) -> None:
        session = can_resume(self.browser_channel())
        if session:
            who = session.get("email") or session.get("name") or "аккаунт"
            self.account_btn.configure(text=f"{who}  ▾", text_color="#FFFFFF")
        else:
            self.account_btn.configure(text="Войти в Mediiia  ▾", text_color="#FF9E9E")

    def browser_channel(self) -> str:
        selected = self.browser_choice.get()
        return next(
            (channel for channel, label in BROWSERS.items() if label == selected),
            "chrome",
        )

    def on_browser_changed(self, selected: str) -> None:
        channel = next(
            (key for key, label in BROWSERS.items() if label == selected),
            "chrome",
        )
        save_browser_preference(channel)
        self.set_status(f"Браузер: {browser_label(channel)}")

    def on_banner_changed(self, position: str, selected: str) -> None:
        is_top = position == "top"
        options = TOP_BANNER_OPTIONS if is_top else BOTTOM_BANNER_OPTIONS
        default = "promo" if is_top else "site"
        key = banner_key_for_label(selected, options, default)
        editor = self.top_banner_editor if is_top else self.bottom_banner_editor
        hint = self.top_banner_hint if is_top else self.bottom_banner_hint
        template = options[key][1]
        if key == "custom":
            editor.grid()
            hint.configure(
                text="Можно использовать жирный, курсив и встроенные ссылки."
            )
        else:
            editor.grid_remove()
            sample_values = {
                "date": self.date_entry.get().strip() or "дату ивента",
                "time_from": self.time_from.get().strip() or "начало",
                "time_to": self.time_to.get().strip() or "конец",
                "title": self.title_entry.get().strip() or "название события",
            }
            rendered = template
            for placeholder, value in sample_values.items():
                rendered = rendered.replace("{" + placeholder + "}", value)
            summary = plain_text(rendered)
            if len(summary) > 170:
                summary = summary[:169].rstrip() + "…"
            hint.configure(text=summary or "Плашка не добавится.")
        self.schedule_preview(delay=50)

    def open_login(self) -> None:
        LoginDialog(self)

    def add_partner(self) -> None:
        PartnerDialog(self)

    def insert_partner(self, name: str, url: str) -> None:
        current = self.partners_box.get("1.0", tk.END).strip()
        separator = "\n" if current else ""
        self.partners_box.insert(tk.END, f"{separator}{name} ({url})")
        self.schedule_preview(delay=50)

    def tail_settings(self) -> TailSettings:
        top = banner_key_for_label(
            self.top_banner_choice.get(), TOP_BANNER_OPTIONS, "promo"
        )
        bottom = banner_key_for_label(
            self.bottom_banner_choice.get(), BOTTOM_BANNER_OPTIONS, "site"
        )
        return TailSettings(
            event_date=self.date_entry.get().strip(),
            time_from=self.time_from.get().strip(),
            time_to=self.time_to.get().strip(),
            record_url=self.record_entry.get().strip(),
            partners_raw=self.partners_box.get("1.0", tk.END),
            extra_info=self.extra_editor.get_html(),
            video_embed=self.video_box.get("1.0", tk.END),
            top_banner=top,
            top_banner_custom=self.top_banner_editor.get_html(),
            bottom_banner=bottom,
            bottom_banner_custom=self.bottom_banner_editor.get_html(),
        )

    def assembled(self) -> Article | None:
        if self.article is None:
            return None
        article = Article(
            title=self.title_entry.get().strip() or self.article.title,
            blocks=self.article.blocks,
        )
        return assemble(article, self.tail_settings(), self.templates)

    def schedule_parse(self, delay: int = 400) -> None:
        if self._parse_job:
            self.after_cancel(self._parse_job)
        self._parse_job = self.after(delay, self._parse_source)

    def schedule_preview(self, delay: int = 300) -> None:
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(delay, self.refresh_preview)

    def _parse_source(self) -> None:
        self._parse_job = None
        raw = self.source_editor.get_markup()
        if not raw.strip():
            self.article = None
            self.refresh_preview()
            self.refresh_readiness()
            return
        try:
            article = load_article(raw, is_path=False)
        except Exception as exc:
            self.set_status(f"Разобрать не удалось: {exc}", kind="error")
            return
        self.article = article
        if article.title and not self.title_entry.get().strip():
            self.title_entry.insert(0, article.title)
        self.set_status(f"Разобрано: {blocks_word(len(article.blocks))}")
        self.refresh_preview()
        self.refresh_readiness()

    # ---------- предпросмотр ----------

    def switch_view(self, value: str) -> None:
        if value == "Исходник":
            self.preview.grid_remove()
            self.source_editor.grid()
        else:
            self.source_editor.grid_remove()
            self.preview.grid()

    def refresh_preview(self) -> None:
        self._preview_job = None
        article = self.assembled()
        box = getattr(self.preview, "_textbox", None)
        self._preview_link_counter = 0
        self.preview.configure(state="normal")
        self.preview.delete("1.0", tk.END)

        if article is None or not article.blocks:
            self.preview_title.configure(text="ЧЕРНОВИК")
            if box is not None:
                box.insert(
                    tk.END,
                    "\n\nЗдесь будут блоки черновика\n"
                    "Абзацы, подзаголовки, цитаты и служебная концовка\n",
                    "empty",
                )
            else:
                self.preview.insert("1.0", "Здесь будут блоки черновика")
            self.preview.configure(state="disabled")
            return

        service = sum(1 for block in article.blocks if block.source in SERVICE_SOURCES)
        self.preview_title.configure(
            text=f"ЧЕРНОВИК · {blocks_word(len(article.blocks)).upper()}"
        )

        if box is None:
            self.preview.insert("1.0", "\n".join(article.preview_lines()))
            self.preview.configure(state="disabled")
            return

        box.insert(tk.END, (article.title or "Без заголовка") + "\n", "headline")
        for index, block in enumerate(article.blocks, 1):
            box.insert(tk.END, f"{index:02d}  ", "num")
            label = self._block_label(block)
            if label:
                tag = "kind_service" if block.source in SERVICE_SOURCES else "kind"
                box.insert(tk.END, label + "\n", tag)
            else:
                box.insert(tk.END, "\n")
            self._insert_body(box, block)

        self.preview.configure(state="disabled")
        self.set_status(
            f"{blocks_word(len(article.blocks) - service)} текста + {service} служебных",
            keep_kind=True,
        )

    def _block_label(self, block: Block) -> str:
        labels = {
            "quote": "ЦИТАТА",
            "green": "ЗЕЛЁНАЯ ПЛАШКА",
            "green_top": "ВЕРХНЯЯ ЗЕЛЁНАЯ ПЛАШКА",
            "green_bottom": "НИЖНЯЯ ЗЕЛЁНАЯ ПЛАШКА",
            "intro": "ВСТУПЛЕНИЕ",
            "partners": "ИНФОПАРТНЁРЫ",
            "outro": "ЗАПИСЬ + ДОП. ИНФО",
            "video": "ВИДЕО",
            "heading": "ПОДЗАГОЛОВОК",
        }
        label = labels.get(block.source, "")
        if block.source == "quote" and block.quote_author:
            label += f" · {block.quote_author}"
        return label

    def _insert_body(self, box, block: Block) -> None:
        body, spans = parse_markup(block.text)
        if len(body) > PREVIEW_SNIPPET:
            body = body[: PREVIEW_SNIPPET - 1].rstrip() + "…"
        if not body:
            return
        # В tk.Text индекс ``end`` стоит после служебного последнего перевода
        # строки, а вставка происходит перед ним. Для диапазонов нужен end-1c.
        start = box.index("end-1c")
        base_tag = "quote" if block.source == "quote" else "body"
        box.insert(tk.END, body + "\n", base_tag)
        body_len = len(body)
        for kind, first, last, meta in spans:
            if first >= body_len:
                continue
            last = min(last, body_len)
            tag = {
                "bold": "preview_bold",
                "italic": "preview_italic",
                "h3": "h3",
            }.get(kind)
            if kind == "a" and meta:
                self._preview_link_counter += 1
                tag = f"preview_link_{self._preview_link_counter}"
                box.tag_config(tag, foreground=t.NAVY, underline=True)
                box.tag_bind(
                    tag,
                    "<Button-1>",
                    lambda _event, url=meta: open_in_browser(url, self.browser_channel()),
                )
                box.tag_bind(tag, "<Enter>", lambda _event: box.configure(cursor="hand2"))
                box.tag_bind(tag, "<Leave>", lambda _event: box.configure(cursor="xterm"))
            if tag:
                box.tag_add(tag, f"{start}+{first}c", f"{start}+{last}c")

    # ---------- готовность и статус ----------

    def readiness(self) -> list[tuple[str, bool]]:
        blocks = len(self.article.blocks) if self.article else 0
        return [
            (blocks_word(blocks) if blocks else "Нет текста", blocks > 0),
            ("Заголовок", bool(self.title_entry.get().strip())),
            ("Дата", bool(self.date_entry.get().strip())),
        ]

    def extras(self) -> list[tuple[str, bool]]:
        """Запись и видео есть не у каждого ивента — отправку они не держат."""
        video = self.video_box.get("1.0", tk.END)
        return [
            ("Ссылка", bool(self.record_entry.get().strip())),
            ("Видео", "<iframe" in video.lower()),
        ]

    def refresh_readiness(self) -> None:
        checks = self.readiness()
        ready = all(ok for _, ok in checks)
        has_session = bool(can_resume(self.browser_channel()))

        if self._busy:
            return

        self.reset_btn.configure(state="normal" if self.filled_items() else "disabled")

        if ready:
            self.publish_btn.configure(
                state="normal",
                text="Создать черновик" if has_session else "Войти и создать черновик",
                fg_color=t.GREEN,
                hover_color=t.GREEN_HOVER,
            )
        else:
            self.publish_btn.configure(
                state="disabled", text="Создать черновик", fg_color=t.DISABLED_BG
            )

        self._render_checklist(checks, ready)

    def _render_checklist(self, checks: list[tuple[str, bool]], ready: bool) -> None:
        for child in self.status_area.winfo_children():
            child.destroy()

        indicator = {
            "idle": t.TEXT_FAINT,
            "success": t.GREEN,
            "error": t.DANGER,
        }.get(self.status_kind, t.TEXT_FAINT)
        ctk.CTkFrame(self.status_area, width=8, height=8, corner_radius=0, fg_color=indicator).grid(
            row=0, column=0, padx=(0, t.GAP_M)
        )

        extras = self.extras()
        if ready:
            assembled = self.assembled()
            total = len(assembled.blocks) if assembled else 0
            missing = [EXTRA_MISSING[label] for label, ok in extras if not ok]
            without = f" · без {' и '.join(missing)}" if missing else ""
            ctk.CTkLabel(
                self.status_area,
                text=f"✓ Готово к отправке · {blocks_word(total)}{without}",
                font=t.font(12),
                text_color=t.GREEN_TEXT,
            ).grid(row=0, column=1, sticky="w")
        else:
            column = 0
            for column, (label, ok) in enumerate(checks, start=1):
                mark = "✓" if ok else "×"
                ctk.CTkLabel(
                    self.status_area,
                    text=f"{mark} {label}",
                    font=t.font(12),
                    text_color=t.GREEN_TEXT if ok else t.DANGER,
                ).grid(row=0, column=column, sticky="w", padx=(0, t.GAP_M))
            # Необязательное показываем тускло: его отсутствие ничего не ломает.
            for column, (label, ok) in enumerate(extras, start=column + 1):
                ctk.CTkLabel(
                    self.status_area,
                    text=f"{'✓' if ok else '·'} {label}",
                    font=t.font(12),
                    text_color=t.GREEN_TEXT if ok else t.TEXT_FAINT,
                ).grid(row=0, column=column, sticky="w", padx=(0, t.GAP_M))

        ctk.CTkLabel(
            self.status_area,
            text=self.status_message,
            font=t.font(11),
            text_color=t.TEXT_FAINT,
        ).grid(row=1, column=1, columnspan=6, sticky="w", pady=(2, 0))

    def set_status(self, message: str, *, kind: str = "idle", keep_kind: bool = False) -> None:
        self.status_message = message
        if not keep_kind:
            self.status_kind = kind
        if not self._busy:
            self.refresh_readiness()

    def _show_result(self, url: str, blocks: int) -> None:
        for child in self.status_area.winfo_children():
            child.destroy()

        bar = t.row(self.status_area, fg_color=t.GREEN_SOFT)
        bar.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            bar,
            text=f"✓ Черновик создан · {blocks_word(blocks)}",
            font=t.font(12, bold=True),
            text_color=t.GREEN_TEXT,
        ).grid(row=0, column=0, padx=t.GAP_M, pady=t.GAP_XS)
        ctk.CTkButton(
            self.status_area,
            text=f"Открыть в {browser_label(self.browser_channel())}",
            width=160,
            command=lambda: open_in_browser(url, self.browser_channel()),
            **t.secondary_button(),
        ).grid(row=0, column=1, padx=(t.GAP_M, t.GAP_S))
        ctk.CTkButton(
            self.status_area,
            text="Копировать ссылку",
            width=160,
            command=lambda: self._copy(url),
            **t.secondary_button(border_width=0, hover_color=t.NAVY_SOFT),
        ).grid(row=0, column=2)
        ctk.CTkLabel(
            self.status_area,
            text="Осталось вручную: обложка, фото, публикация",
            font=t.font(11),
            text_color=t.TEXT_FAINT,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 0))

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    # ---------- действия ----------

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите файл со статьёй",
            filetypes=[
                ("Документы", "*.docx *.txt *.md"),
                ("Word", "*.docx"),
                ("Текст", "*.txt *.md"),
                ("Все файлы", "*.*"),
            ],
        )
        if path:
            self.load_path(Path(path))

    def reload_file(self) -> None:
        if self.source_path:
            self.load_path(self.source_path, keep_title=True)

    def paste_from_clipboard(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            self.set_status("В буфере обмена нет текста", kind="error")
            return
        if not text.strip():
            return
        self.source_path = None
        self.file_chip.grid_remove()
        self.dropzone.grid()
        self.source_editor.set_markup(text)
        self.set_status("Разбираю…")
        self.schedule_parse(delay=50)

    def load_path(self, path: Path, *, keep_title: bool = False) -> None:
        title_hint = self.title_entry.get().strip() if keep_title else None
        try:
            article = load_article(path, is_path=True, title_hint=title_hint)
        except Exception as exc:
            self.set_status(f"Файл не прочитался: {exc}", kind="error")
            return

        self.source_path = path
        self.article = article

        try:
            if path.suffix.lower() == ".docx":
                raw = article_to_markup(article)
            else:
                raw = path.read_text(encoding="utf-8")
        except Exception:
            raw = ""
        self.source_editor.set_markup(raw)

        self.dropzone.grid_remove()
        self.file_chip.grid()
        self.chip_name.configure(text=path.name)
        self.chip_meta.configure(
            text=f"{blocks_word(len(article.blocks))} · {datetime.now():%H:%M}"
        )

        guessed = guess_event_date(path.stem)
        if guessed and not self.date_entry.get().strip():
            self.date_entry.insert(0, guessed)
        if article.title and not self.title_entry.get().strip():
            self.title_entry.insert(0, article.title)

        self.set_status(f"{blocks_word(len(article.blocks))} из файла")
        self.refresh_preview()
        self.refresh_readiness()

    def filled_items(self) -> list[str]:
        """Что именно потеряется при сбросе — это же показываем в подтверждении."""
        items = []
        if self.article:
            items.append(f"текст статьи ({blocks_word(len(self.article.blocks))})")
        elif self.source_editor.get_markup().strip():
            items.append("текст статьи")
        for label, value in (
            ("заголовок", self.title_entry.get()),
            ("дата ивента", self.date_entry.get()),
            ("ссылка на запись", self.record_entry.get()),
            ("код VK Видео", self.video_box.get("1.0", tk.END)),
            ("доп. информация", self.extra_editor.get_markup()),
            ("инфопартнёры", self.partners_box.get("1.0", tk.END)),
        ):
            if value.strip():
                items.append(label)
        if self.top_banner_choice.get() != TOP_BANNER_OPTIONS["promo"][0]:
            items.append("выбор верхней зелёной плашки")
        if self.bottom_banner_choice.get() != BOTTOM_BANNER_OPTIONS["site"][0]:
            items.append("выбор нижней зелёной плашки")
        if self.top_banner_editor.get_markup().strip():
            items.append("свой текст верхней плашки")
        if self.bottom_banner_editor.get_markup().strip():
            items.append("свой текст нижней плашки")
        return items

    def reset_all(self) -> None:
        if self._busy:
            return
        items = self.filled_items()
        if not items:
            self.set_status("Сбрасывать нечего")
            return

        listing = "\n".join(f"— {item}" for item in items)
        confirmed = messagebox.askyesno(
            "Сбросить всё",
            f"Будет стёрто:\n\n{listing}\n\nВосстановить это будет нельзя. Сбросить?",
            default=messagebox.NO,
            icon=messagebox.WARNING,
            parent=self,
        )
        if not confirmed:
            self.set_status("Сброс отменён")
            return

        self.article = None
        self.source_path = None
        self.source_editor.clear()
        self.file_chip.grid_remove()
        self.dropzone.grid()
        for widget in (self.title_entry, self.date_entry, self.record_entry):
            widget.delete(0, tk.END)
        for widget in (self.video_box, self.partners_box):
            widget.delete("1.0", tk.END)
        self.extra_editor.clear()
        self.top_banner_editor.clear()
        self.bottom_banner_editor.clear()
        self.time_from.delete(0, tk.END)
        self.time_from.insert(0, self.templates.get("default_time_from", "18:30"))
        self.time_to.delete(0, tk.END)
        self.time_to.insert(0, self.templates.get("default_time_to", "21:00"))
        self.top_banner_choice.set(TOP_BANNER_OPTIONS["promo"][0])
        self.bottom_banner_choice.set(BOTTOM_BANNER_OPTIONS["site"][0])
        self.on_banner_changed("top", self.top_banner_choice.get())
        self.on_banner_changed("bottom", self.bottom_banner_choice.get())
        self.view_switch.set("Блоки")
        self.switch_view("Блоки")
        self.set_status("Всё сброшено. Перетащите .docx или нажмите Ctrl+V")
        self.refresh_preview()

    def on_publish(self) -> None:
        if self._busy:
            return
        if not all(ok for _, ok in self.readiness()):
            return

        article = self.assembled()
        if article is None or not article.blocks:
            return

        if not can_resume(self.browser_channel()):
            self.publish_after_login = True
            self.open_login()
            return

        cfg = self.cfg
        total = len(article.blocks)
        # Переменные Tk читаем только в главном потоке.
        open_browser = bool(self.open_browser_var.get())
        browser = self.browser_channel()
        # Если вход придётся подтверждать заново, форму заполнит сама программа.
        saved = load_credentials()
        self._busy = True
        self.publish_btn.configure(
            state="disabled", text="Создаю черновик…", fg_color=t.DISABLED_BG
        )
        self.reset_btn.configure(state="disabled")
        self.progress.grid()
        self.progress.set(0)
        self.status_kind = "idle"
        self._set_busy_message(f"Заливаю блок 0 из {total}")

        def progress(done: int, count: int) -> None:
            self.post(lambda: self._on_progress(done, count))

        def work() -> None:
            try:
                self.post(lambda: self._set_busy_message("Проверяю вход в Mediiia"))
                session = ensure_session(
                    email=saved.email or None,
                    password=saved.password or None,
                    browser=browser,
                )
                account_id = (session.get("account_id") or "").strip()
                configured_email = (cfg.get("account_email") or "").strip().lower()
                session_email = (session.get("email") or "").strip().lower()
                if not account_id and (
                    not configured_email or session_email == configured_email
                ):
                    account_id = (cfg.get("account_id") or "").strip()
                if not account_id:
                    raise MediiiaError("Аккаунт не распознан. Нужно войти заново.")

                with MediiiaClient(session["access_token"], account_id) as client:
                    result = client.create_draft_from_article(
                        article,
                        tag_names=tag_names_from_config(cfg),
                        coauthor_ids=list(cfg.get("default_coauthor_ids") or []),
                        open_browser=open_browser,
                        browser=browser,
                        tag_ids_map=cfg.get("default_tag_ids") or {},
                        on_progress=progress,
                    )
            except MediiiaError as exc:
                if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                    clear_session()
                    message = "Вход в Mediiia больше не действует. Войдите заново и повторите."
                else:
                    message = f"Mediiia не приняла запрос: {exc}"
                self.post(lambda: self._finish_publish(error=message))
                return
            except Exception as exc:
                message = f"Что-то пошло не так: {exc}"
                self.post(lambda: self._finish_publish(error=message))
                return
            self.post(
                lambda: self._finish_publish(url=result.edit_url, blocks=result.blocks_created)
            )

        threading.Thread(target=work, daemon=True).start()

    def _set_busy_message(self, message: str) -> None:
        for child in self.status_area.winfo_children():
            child.destroy()
        ctk.CTkFrame(self.status_area, width=8, height=8, corner_radius=0, fg_color=t.GREEN).grid(
            row=0, column=0, padx=(0, t.GAP_M)
        )
        self.busy_label = ctk.CTkLabel(
            self.status_area, text=message, font=t.font(12), text_color=t.TEXT
        )
        self.busy_label.grid(row=0, column=1, sticky="w")

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.set(done / max(total, 1))
        if hasattr(self, "busy_label") and self.busy_label.winfo_exists():
            self.busy_label.configure(text=f"Заливаю блок {done} из {total}")

    def _finish_publish(
        self, *, url: str = "", blocks: int = 0, error: str = ""
    ) -> None:
        self._busy = False
        self.progress.grid_remove()
        self.reset_btn.configure(state="normal" if self.filled_items() else "disabled")

        if error:
            self.status_kind = "error"
            self.status_message = error
            self.refresh_readiness()
            for child in self.status_area.winfo_children():
                child.destroy()
            ctk.CTkFrame(
                self.status_area, width=8, height=8, corner_radius=0, fg_color=t.DANGER
            ).grid(row=0, column=0, padx=(0, t.GAP_M))
            ctk.CTkLabel(
                self.status_area,
                text=error,
                font=t.font(12),
                text_color=t.DANGER,
                wraplength=620,
                justify="left",
            ).grid(row=0, column=1, sticky="w")
            ctk.CTkButton(
                self.status_area,
                text="Повторить",
                width=120,
                command=self.on_publish,
                **t.secondary_button(),
            ).grid(row=0, column=2, padx=(t.GAP_M, 0))
            self.publish_btn.configure(
                state="normal", text="Создать черновик", fg_color=t.GREEN
            )
            return

        self.status_kind = "success"
        self.status_message = f"Черновик создан · {blocks_word(blocks)}"
        self.publish_btn.configure(
            state="disabled", text="Создать черновик", fg_color=t.DISABLED_BG
        )
        self._show_result(url, blocks)


def run(initial_file: Path | None = None, initial_title: str | None = None) -> None:
    app = App(initial_file=initial_file, initial_title=initial_title)
    app.mainloop()
