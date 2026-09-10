"""Авторизация Mediiia через браузер (OIDC), без хранения пароля."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from .browsers import browser_label, normalize_browser


AUTH_URL = (
    "https://auth.mediiia.ru/Account/Login"
    "?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback"
    "%3Fclient_id%3DMediiiaCom"
    "%26redirect_uri%3Dhttps%253A%252F%252Fmediiia.com%252Flogin%252Fcallback"
    "%26response_type%3Dcode"
    "%26scope%3Dopenid%2520api2.full_access%2520offline_access%2520email%2520profile"
    "%26code_challenge_method%3DS256"
)
OIDC_STORAGE_KEY = "oidc.user:https://auth.mediiia.ru:MediiiaCom"
APP_DATA_DIR = Path.home() / ".mediiia-publisher"
DEFAULT_TOKEN_PATH = APP_DATA_DIR / "session.json"
BROWSER_PROFILE_DIR = APP_DATA_DIR / "browser"


def token_path() -> Path:
    return DEFAULT_TOKEN_PATH


def load_session(path: Path | None = None) -> dict[str, Any] | None:
    path = path or token_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expires_at = data.get("expires_at")
    if expires_at and time.time() > float(expires_at) - 60:
        return None
    if not data.get("access_token"):
        return None
    return data


def save_session(data: dict[str, Any], path: Path | None = None) -> Path:
    path = path or token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_session(path: Path | None = None) -> None:
    path = path or token_path()
    if path.exists():
        path.unlink()


def _extract_oidc(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        user = json.loads(raw)
    except json.JSONDecodeError:
        return None
    access = user.get("access_token")
    if not access:
        return None
    profile = user.get("profile") or {}
    access_profile: dict[str, Any] = {}
    try:
        payload = access.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        access_profile = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        pass
    return {
        "access_token": access,
        "expires_at": user.get("expires_at"),
        "token_type": user.get("token_type") or "Bearer",
        "account_id": access_profile.get("account_id") or profile.get("accountId"),
        "identity_sub": profile.get("sub"),
        "email": profile.get("email"),
        "name": profile.get("name") or profile.get("preferred_username"),
        "raw_profile_keys": list(profile.keys()),
    }


def _account_id_from_page(page: Any) -> str:
    """Находит публичный account_id в ссылке профиля после входа."""
    try:
        hrefs = page.locator("a[href*='/account/']").evaluate_all(
            "nodes => nodes.map(node => node.href)"
        )
    except Exception:
        return ""
    for href in hrefs:
        match = re.search(r"([0-9a-f]{32})(?:[/?#]|$)", str(href), re.I)
        if match:
            return match.group(1).lower()
    return ""


def profile_dir_for(email: str | None, browser: str = "chrome") -> Path:
    """Отдельный профиль браузера на каждый аккаунт — чтобы сессии не смешивались."""
    key = (email or "").strip().lower()
    browser = normalize_browser(browser)
    root = BROWSER_PROFILE_DIR if browser == "chrome" else BROWSER_PROFILE_DIR / browser
    if not key:
        return root / "default"
    return root / hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _fill_login_form(page: Any, email: str, password: str) -> None:
    """Заполняет форму auth.mediiia.ru: почта → «Далее» → пароль → «Войти»."""
    email_box = page.locator(
        "input[placeholder='example@example.com'], input[type='email'], input[name*='mail' i]"
    ).first
    email_box.wait_for(timeout=20000)
    email_box.fill(email)
    try:
        page.get_by_role("button", name="Далее").click()
    except Exception:
        page.keyboard.press("Enter")
    page.wait_for_timeout(2000)

    password_box = page.locator("input[type='password']").first
    password_box.wait_for(timeout=20000)
    password_box.fill(password)
    try:
        page.get_by_role("button", name="Войти").click()
    except Exception:
        page.keyboard.press("Enter")


def login_via_browser(
    timeout_sec: int = 300,
    headless: bool = False,
    email: str | None = None,
    password: str | None = None,
    browser: str = "chrome",
) -> dict[str, Any]:
    """
    Открывает выбранный Chrome/Edge с постоянным профилем. Если переданы логин и пароль —
    форма заполняется сама; иначе пользователь входит руками.
    Токен забираем из localStorage mediiia.com.
    """
    from playwright.sync_api import sync_playwright

    browser = normalize_browser(browser)
    profile = profile_dir_for(email, browser)
    profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": headless,
            "viewport": {"width": 1280, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        try:
            context = p.chromium.launch_persistent_context(
                str(profile), channel=browser, **launch_kwargs
            )
        except Exception as exc:
            raise RuntimeError(
                f"Не удалось открыть {browser_label(browser)}. "
                "Установите браузер или выберите другой в параметрах."
            ) from exc
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://mediiia.com/edit", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        if email and password and "auth.mediiia.ru" in page.url:
            try:
                _fill_login_form(page, email, password)
            except Exception:
                pass  # не получилось автоматически — пользователь войдёт сам

        deadline = time.time() + timeout_sec
        session: dict[str, Any] | None = None
        while time.time() < deadline:
            try:
                raw = page.evaluate(
                    f"() => window.localStorage.getItem({json.dumps(OIDC_STORAGE_KEY)})"
                )
                candidate = _extract_oidc(raw)
                if candidate and "auth.mediiia.ru" not in page.url:
                    account_id = _account_id_from_page(page)
                    if account_id:
                        candidate["account_id"] = account_id
                    session = candidate
                    break
            except Exception:
                pass
            page.wait_for_timeout(1000)

        context.close()

    if session is None:
        raise TimeoutError(
            "Не удалось получить сессию Mediiia. "
            "Войдите в аккаунт в открывшемся окне браузера и подождите."
        )

    save_session(session)
    return session


def refresh_session_headless(
    timeout_sec: int = 90,
    email: str | None = None,
    password: str | None = None,
    browser: str = "chrome",
) -> dict[str, Any] | None:
    """Обновляет токен в фоне, если профиль этого аккаунта уже авторизован."""
    if not profile_dir_for(email, browser).exists():
        return None
    try:
        return login_via_browser(
            timeout_sec=timeout_sec,
            headless=True,
            email=email,
            password=password,
            browser=browser,
        )
    except Exception:
        return None


def ensure_session(
    *,
    force_login: bool = False,
    email: str | None = None,
    password: str | None = None,
    browser: str = "chrome",
) -> dict[str, Any]:
    if not force_login:
        existing = load_session()
        if existing and (not email or (existing.get("email") or "").lower() == email.lower()):
            return existing
        refreshed = refresh_session_headless(
            email=email, password=password, browser=browser
        )
        if refreshed:
            return refreshed
    return login_via_browser(email=email, password=password, browser=browser)
