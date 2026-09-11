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
LAST_ACCOUNT_PATH = APP_DATA_DIR / "account.json"
BROWSER_PROFILE_DIR = APP_DATA_DIR / "browser"
LANDING_URL = "https://mediiia.com/"
FRESHNESS_SKEW_SEC = 120.0


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
    remember_account(data)
    return path


def clear_session(path: Path | None = None) -> None:
    path = path or token_path()
    if path.exists():
        path.unlink()


def remember_account(session: dict[str, Any]) -> None:
    """Помним, кто входил: токен живёт час, а вход должен ощущаться постоянным."""
    email = (session.get("email") or "").strip()
    if not email:
        return
    hint = {"email": email, "name": session.get("name") or ""}
    try:
        LAST_ACCOUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
        LAST_ACCOUNT_PATH.write_text(
            json.dumps(hint, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def last_account() -> dict[str, Any] | None:
    for path in (LAST_ACCOUNT_PATH, token_path()):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        email = (data.get("email") or "").strip()
        if email:
            # Из просроченной сессии берём только почту, токен оттуда не нужен.
            return {"email": email, "name": data.get("name") or ""}
    return None


def forget_account() -> None:
    clear_session()
    if LAST_ACCOUNT_PATH.exists():
        LAST_ACCOUNT_PATH.unlink()


def can_resume(browser: str = "chrome") -> dict[str, Any] | None:
    """
    Вход считается действующим и когда токен истёк: профиль браузера
    помнит аккаунт, и токен продлевается молча, без окна входа.
    """
    session = load_session()
    if session:
        return session
    account = last_account()
    if account and profile_dir_for(account.get("email"), browser).exists():
        return account
    return None


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
        "expires_at": user.get("expires_at") or access_profile.get("exp"),
        "token_type": user.get("token_type") or "Bearer",
        "account_id": access_profile.get("account_id") or profile.get("accountId"),
        "identity_sub": profile.get("sub"),
        "email": profile.get("email"),
        "name": profile.get("name") or profile.get("preferred_username"),
        "raw_profile_keys": list(profile.keys()),
    }


def is_fresh(session: dict[str, Any], skew: float = FRESHNESS_SKEW_SEC) -> bool:
    """
    В localStorage браузера токен остаётся с прошлого запуска, даже просроченный.
    Берём его только пока он живой, иначе сохранили бы мёртвую сессию.
    """
    expires_at = session.get("expires_at")
    if expires_at is None:
        return True
    try:
        return time.time() < float(expires_at) - skew
    except (TypeError, ValueError):
        return True


def _account_id_from_page(page: Any) -> str:
    """
    Запасной способ узнать account_id — по ссылке на профиль.
    В ленте ссылок на чужие аккаунты много, и угадывать нельзя:
    отвечаем только когда на странице ровно один аккаунт.
    """
    try:
        hrefs = page.locator("a[href*='/account/']").evaluate_all(
            "nodes => nodes.map(node => node.href)"
        )
    except Exception:
        return ""
    found = {
        match.group(1).lower()
        for href in hrefs
        if (match := re.search(r"([0-9a-f]{32})(?:[/?#]|$)", str(href), re.I))
    }
    return found.pop() if len(found) == 1 else ""


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
        page.goto(LANDING_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        deadline = time.time() + timeout_sec
        session: dict[str, Any] | None = None
        form_attempts = 0
        renew_not_before = 0.0
        while time.time() < deadline:
            if "auth.mediiia.ru" in page.url:
                if email and password and form_attempts < 2:
                    form_attempts += 1
                    try:
                        _fill_login_form(page, email, password)
                    except Exception:
                        pass  # не вышло автоматически — пользователь войдёт сам
                page.wait_for_timeout(1000)
                continue

            candidate: dict[str, Any] | None = None
            try:
                raw = page.evaluate(
                    f"() => window.localStorage.getItem({json.dumps(OIDC_STORAGE_KEY)})"
                )
                candidate = _extract_oidc(raw)
            except Exception:
                pass

            if candidate and is_fresh(candidate):
                if not candidate.get("account_id"):
                    candidate["account_id"] = _account_id_from_page(page)
                session = candidate
                break

            if candidate and time.time() >= renew_not_before:
                # Токен остался с прошлого запуска. Перезагрузка страницы
                # заставляет сайт обменять refresh_token на свежий.
                renew_not_before = time.time() + 10
                try:
                    page.reload(wait_until="domcontentloaded")
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
    if not email:
        # Без почты профиль браузера не найти, а в нём и лежит продлеваемый вход.
        email = (last_account() or {}).get("email") or None
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
