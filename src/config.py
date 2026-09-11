"""Конфиг приложения рядом с exe / корнем репозитория."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


def application_dir() -> Path:
    """Корень проекта или каталог рядом с собранным exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = application_dir()
DEFAULT_CONFIG = APP_DIR / "config.json"
EXAMPLE_CONFIG = (
    Path(getattr(sys, "_MEIPASS")) / "config.example.json"
    if getattr(sys, "frozen", False)
    else APP_DIR / "config.example.json"
)

# Шаблоны служебных блоков — сняты с уже опубликованных статей хаба.
DEFAULT_TAIL_TEMPLATES: dict[str, str] = {
    "promo_banner": "«CREATIVE HUB» — промокод на скидку 5% на все курсы ДПО",
    "intro_template": (
        '<strong>{date}</strong> в пространстве '
        '<a href="https://creative.hse.ru/hub" target="_blank" '
        'rel="noopener noreferrer">Креативный хаб / HSE CREATIVE HUB</a> '
        "прошло мероприятие {title}.<br><br>"
        "Вкратце рассказываем, как прошло мероприятие."
    ),
    "record_channel": "HSE CREATIVE HUB",
    "record_channel_url": "https://vkvideo.ru/@creativehub_hse",
    "record_template": (
        "Послушать полные выступления спикеров можно в записи дискуссии в канале "
        "{record_link}."
    ),
    "partners_intro": "Благодарим наших информационных партнёров за поддержку этого мероприятия:",
    "event_template": (
        "Мероприятие прошло {date} с {time_from} до {time_to} в пространстве "
        "Креативный хаб / HSE CREATIVE HUB. Подробнее об этом и других событиях, "
        "проходящих на площадке, можно узнать на сайте https://creative.hse.ru/hub."
    ),
    "default_time_from": "18:30",
    "default_time_to": "21:00",
}

# Зелёные плашки из опубликованных референсов хаба. Ключи хранятся
# отдельно от подписей, чтобы смена текста в интерфейсе не ломала настройки.
TOP_BANNER_OPTIONS: dict[str, tuple[str, str]] = {
    "none": ("Без верхней плашки", ""),
    "promo": (
        "Промокод CREATIVE HUB",
        "«CREATIVE HUB» — промокод на скидку 5% на все курсы ДПО",
    ),
    "telegram_bot": (
        "Telegram-бот с материалами",
        "Чтобы не пропускать интересные мероприятия и получать фотографии, "
        "презентации и другие материалы по итогам ивента, подписывайтесь на "
        '<a href="https://t.me/crehub_hse_bot" target="_blank" '
        'rel="noopener noreferrer">Телеграм-бот Креативного хаба</a>.',
    ),
    "webinars": (
        "Открытые вебинары",
        "Если интересуетесь курсами по дизайну, приглашаем на открытые вебинары "
        "каждый день в 19:00 по Москве. Для тех, кто присутствовал на мероприятии "
        "{date} — скидка 5% на обучение. "
        '<a href="https://design.hse.ru/dop/online-marathon" target="_blank" '
        'rel="noopener noreferrer">Выбирайте и подключайтесь</a>.',
    ),
    "custom": ("Свой текст…", ""),
}

BOTTOM_BANNER_OPTIONS: dict[str, tuple[str, str]] = {
    "site": (
        "Сайт Креативного хаба",
        "Мероприятие прошло {date} с {time_from} до {time_to} в пространстве "
        "Креативный хаб / HSE CREATIVE HUB. Подробнее об этом и других событиях, "
        "проходящих на площадке, можно узнать на сайте https://creative.hse.ru/hub.",
    ),
    "telegram_channel": (
        "Telegram-канал хаба",
        "Мероприятие прошло {date} с {time_from} до {time_to} в пространстве "
        "Креативный хаб / HSE CREATIVE HUB. Подробнее об этом и других событиях, "
        "проходящих на площадке, можно узнать в нашем "
        '<a href="https://t.me/creativehub_hse" target="_blank" '
        'rel="noopener noreferrer">Telegram-канале</a>.',
    ),
    "custom": ("Свой текст…", ""),
    "none": ("Без нижней плашки", ""),
}


def banner_labels(options: dict[str, tuple[str, str]]) -> list[str]:
    return [label for label, _template in options.values()]


def banner_key_for_label(
    label: str, options: dict[str, tuple[str, str]], default: str
) -> str:
    return next((key for key, item in options.items() if item[0] == label), default)


def ensure_config(path: Path | None = None) -> Path:
    path = path or DEFAULT_CONFIG
    if not path.exists():
        if EXAMPLE_CONFIG.exists():
            shutil.copy(EXAMPLE_CONFIG, path)
        else:
            path.write_text(
                json.dumps(
                    {
                        "default_tags": {
                            "required_education": "о креативных индустриях",
                            "common": ["event factory", "архив ивентов", "пост-релиз"],
                        },
                        "default_coauthor_ids": [],
                        "open_draft_after_create": True,
                        "visibility": "public",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    return path


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = ensure_config(path)
    return json.loads(path.read_text(encoding="utf-8"))


def tail_templates(cfg: dict[str, Any]) -> dict[str, str]:
    """Шаблоны концовки: значения из config.json перекрывают встроенные."""
    templates = dict(DEFAULT_TAIL_TEMPLATES)
    for key, value in (cfg.get("article_tail") or {}).items():
        if isinstance(value, str) and value.strip():
            templates[key] = value
    return templates


def tag_names_from_config(cfg: dict[str, Any]) -> list[str]:
    tags_cfg = cfg.get("default_tags") or {}
    names: list[str] = []
    req = tags_cfg.get("required_education")
    if req:
        names.append(str(req))
    for name in tags_cfg.get("common") or []:
        if name and str(name) not in names:
            names.append(str(name))
    return names
