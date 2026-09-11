from __future__ import annotations

import base64
import json
import time

import src.auth as auth


def _token(exp: int | None) -> str:
    payload: dict[str, object] = {"account_id": "a" * 32}
    if exp is not None:
        payload["exp"] = exp
    chunk = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{chunk}.signature"


def test_is_fresh_rejects_token_from_previous_run() -> None:
    assert not auth.is_fresh({"expires_at": time.time() - 3600})
    assert not auth.is_fresh({"expires_at": time.time() + 30})  # вот-вот истечёт
    assert auth.is_fresh({"expires_at": time.time() + 3600})
    assert auth.is_fresh({})  # срок неизвестен — не блокируем вход


def test_extract_oidc_takes_expiry_from_token_when_storage_has_none() -> None:
    exp = int(time.time()) + 3600
    raw = json.dumps({"access_token": _token(exp), "profile": {"email": "a@b.ru"}})

    session = auth._extract_oidc(raw)

    assert session is not None
    assert session["expires_at"] == exp
    assert session["account_id"] == "a" * 32
    assert auth.is_fresh(session)


def test_extract_oidc_prefers_storage_expiry() -> None:
    exp = int(time.time()) + 3600
    raw = json.dumps({"access_token": _token(exp), "expires_at": exp + 999})

    session = auth._extract_oidc(raw)

    assert session is not None
    assert session["expires_at"] == exp + 999


def test_can_resume_survives_expired_token(tmp_path, monkeypatch) -> None:
    """Токен Mediiia живёт час, но вход должен ощущаться постоянным."""
    monkeypatch.setattr(auth, "LAST_ACCOUNT_PATH", tmp_path / "account.json")
    monkeypatch.setattr(auth, "DEFAULT_TOKEN_PATH", tmp_path / "session.json")
    monkeypatch.setattr(auth, "BROWSER_PROFILE_DIR", tmp_path / "browser")

    expired = {
        "access_token": _token(int(time.time()) - 10),
        "expires_at": time.time() - 10,
        "email": "editor@example.com",
    }
    auth.save_session(expired)

    assert auth.load_session() is None  # просроченный токен не используем
    assert auth.can_resume("chrome") is None  # профиля браузера ещё нет

    auth.profile_dir_for("editor@example.com", "chrome").mkdir(parents=True)
    resumed = auth.can_resume("chrome")
    assert resumed is not None
    assert resumed["email"] == "editor@example.com"

    auth.forget_account()
    assert auth.can_resume("chrome") is None


def test_last_account_falls_back_to_session_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "LAST_ACCOUNT_PATH", tmp_path / "account.json")
    monkeypatch.setattr(auth, "DEFAULT_TOKEN_PATH", tmp_path / "session.json")
    (tmp_path / "session.json").write_text(
        json.dumps({"email": "editor@example.com", "access_token": "x"}), encoding="utf-8"
    )

    account = auth.last_account()

    assert account == {"email": "editor@example.com", "name": ""}
    assert "access_token" not in account


class _FakeLocator:
    def __init__(self, hrefs: list[str]) -> None:
        self._hrefs = hrefs

    def evaluate_all(self, _script: str) -> list[str]:
        return self._hrefs


class _FakePage:
    def __init__(self, hrefs: list[str]) -> None:
        self._hrefs = hrefs

    def locator(self, _selector: str) -> _FakeLocator:
        return _FakeLocator(self._hrefs)


def test_account_id_from_page_needs_single_account() -> None:
    mine = "b" * 32
    other = "c" * 32

    single = _FakePage([f"https://mediiia.com/account/name-{mine}"])
    assert auth._account_id_from_page(single) == mine

    feed = _FakePage(
        [
            f"https://mediiia.com/account/one-{mine}",
            f"https://mediiia.com/account/two-{other}",
        ]
    )
    assert auth._account_id_from_page(feed) == ""

    assert auth._account_id_from_page(_FakePage([])) == ""
