"""Диагностика: что лежит в localStorage профиля браузера и живой ли это токен."""

from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import OIDC_STORAGE_KEY, profile_dir_for  # noqa: E402


def describe(raw: str | None, label: str) -> None:
    if not raw:
        print(f"{label}: localStorage пуст")
        return
    user = json.loads(raw)
    access = user.get("access_token") or ""
    parts = access.split(".")
    payload = {}
    if len(parts) >= 2:
        chunk = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(chunk))
    exp = payload.get("exp")
    print(f"{label}:")
    print(f"  expires_at (storage): {user.get('expires_at')}")
    print(f"  exp (token):          {exp} -> {datetime.fromtimestamp(exp) if exp else None}")
    print(f"  now:                  {datetime.now()}")
    print(f"  просрочен:            {bool(exp and time.time() > exp)}")
    print(f"  refresh_token:        {'есть' if user.get('refresh_token') else 'НЕТ'}")


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else None
    profile = profile_dir_for(email, "chrome")
    print(f"профиль: {profile}  существует={profile.exists()}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profile), headless=True, channel="chrome",
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://mediiia.com/edit", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        print(f"url после загрузки: {page.url}")
        raw = page.evaluate(
            f"() => window.localStorage.getItem({json.dumps(OIDC_STORAGE_KEY)})"
        )
        describe(raw, "СРАЗУ ПОСЛЕ ЗАГРУЗКИ")

        page.wait_for_timeout(8000)
        raw2 = page.evaluate(
            f"() => window.localStorage.getItem({json.dumps(OIDC_STORAGE_KEY)})"
        )
        print(f"url через 8 c: {page.url}")
        describe(raw2, "ЧЕРЕЗ 8 СЕКУНД (ждём silent renew)")
        context.close()


if __name__ == "__main__":
    main()
