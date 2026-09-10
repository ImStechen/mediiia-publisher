"""Поддерживаемые браузеры для входа и открытия черновика."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

BROWSERS = {
    "chrome": "Google Chrome",
    "msedge": "Microsoft Edge",
}
DEFAULT_BROWSER = "chrome"
PREFERENCES_PATH = Path.home() / ".mediiia-publisher" / "preferences.json"


def normalize_browser(value: str | None) -> str:
    value = (value or "").strip().lower()
    return value if value in BROWSERS else DEFAULT_BROWSER


def browser_label(channel: str) -> str:
    return BROWSERS[normalize_browser(channel)]


def load_browser_preference(default: str = DEFAULT_BROWSER) -> str:
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        return normalize_browser(data.get("browser"))
    except (OSError, ValueError, TypeError):
        return normalize_browser(default)


def save_browser_preference(channel: str) -> None:
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_PATH.write_text(
        json.dumps({"browser": normalize_browser(channel)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def executable_for(channel: str) -> Path | None:
    channel = normalize_browser(channel)
    names = ("chrome", "chrome.exe") if channel == "chrome" else ("msedge", "msedge.exe")
    candidates = [shutil.which(name) for name in names]

    if channel == "chrome":
        relative = Path("Google/Chrome/Application/chrome.exe")
        env_vars = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
    else:
        relative = Path("Microsoft/Edge/Application/msedge.exe")
        env_vars = ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")

    candidates.extend(
        str(Path(base) / relative)
        for key in env_vars
        if (base := os.environ.get(key))
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def open_in_browser(url: str, channel: str = DEFAULT_BROWSER) -> None:
    executable = executable_for(channel)
    if executable:
        subprocess.Popen([str(executable), url])
        return
    # Последний шанс для уже созданного черновика. Вход всё равно выдаст
    # понятную ошибку, если выбранный Chrome/Edge отсутствует.
    webbrowser.open(url)
