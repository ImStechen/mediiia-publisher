"""
Однократный вход в Mediiia в постоянный профиль браузера.

Логин и пароль берутся из переменных окружения MEDIIIA_EMAIL / MEDIIIA_PASSWORD.
Если их нет — окно просто открывается, и вы входите руками.

    python tools\\login_once.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import BROWSER_PROFILE_DIR, OIDC_STORAGE_KEY, _extract_oidc, save_session


def main() -> int:
    from playwright.sync_api import sync_playwright

    email = os.environ.get("MEDIIIA_EMAIL", "").strip()
    password = os.environ.get("MEDIIIA_PASSWORD", "")
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        kwargs = {
            "headless": False,
            "viewport": {"width": 1280, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        try:
            ctx = p.chromium.launch_persistent_context(
                str(BROWSER_PROFILE_DIR), channel="chrome", **kwargs
            )
            print("Браузер: Chrome")
        except Exception as exc:
            print(f"Chrome недоступен ({exc}); запускаю Chromium")
            ctx = p.chromium.launch_persistent_context(str(BROWSER_PROFILE_DIR), **kwargs)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://mediiia.com/edit", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        if "auth.mediiia.ru" in page.url and email and password:
            print("Заполняю форму входа…")
            try:
                email_box = page.locator("input[placeholder='example@example.com']").first
                email_box.wait_for(timeout=15000)
                email_box.fill(email)
                page.get_by_role("button", name="Далее").click()
                page.wait_for_timeout(2000)

                pwd = page.locator("input[type='password']").first
                pwd.wait_for(timeout=15000)
                pwd.fill(password)
                page.get_by_role("button", name="Войти").click()
            except Exception as exc:
                print(f"Автозаполнение не удалось: {exc}. Войдите вручную.")

        print("Ожидаю завершения входа…")
        session = None
        deadline = time.time() + 240
        while time.time() < deadline:
            try:
                raw = page.evaluate(
                    f"() => window.localStorage.getItem({json.dumps(OIDC_STORAGE_KEY)})"
                )
                candidate = _extract_oidc(raw)
                if candidate and "auth.mediiia.ru" not in page.url:
                    session = candidate
                    break
            except Exception:
                pass
            page.wait_for_timeout(1000)

        ctx.close()

    if not session:
        print("Не удалось получить сессию.")
        return 1

    path = save_session(session)
    print(f"Сессия сохранена: {path}")
    print(f"Почта: {session.get('email')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
