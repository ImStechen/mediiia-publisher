"""
Логин/пароль аккаунта, от которого публикуем.

Пароль шифруется средствами Windows (DPAPI) и расшифровывается только
под той же учётной записью Windows. Файл лежит в %USERPROFILE%\\.mediiia-publisher.
"""

from __future__ import annotations

import base64
import ctypes
import json
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from .auth import APP_DATA_DIR

CREDENTIALS_PATH = APP_DATA_DIR / "credentials.json"


@dataclass
class Credentials:
    email: str = ""
    password: str = ""

    @property
    def filled(self) -> bool:
        return bool(self.email.strip() and self.password)


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob_bytes(blob: _Blob) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def _dpapi(func_name: str, data: bytes) -> bytes | None:
    """CryptProtectData / CryptUnprotectData. None — если DPAPI недоступна."""
    try:
        crypt32 = ctypes.windll.crypt32
        func = getattr(crypt32, func_name)
    except (AttributeError, OSError):
        return None

    source = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_char)))
    result = _Blob()
    args = [ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)]
    if not func(*args):
        return None
    try:
        return _blob_bytes(result)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)


def _encrypt(password: str) -> dict[str, str]:
    raw = password.encode("utf-8")
    protected = _dpapi("CryptProtectData", raw)
    if protected is not None:
        return {"scheme": "dpapi", "value": base64.b64encode(protected).decode("ascii")}
    return {"scheme": "base64", "value": base64.b64encode(raw).decode("ascii")}


def _decrypt(stored: dict[str, str]) -> str:
    value = stored.get("value") or ""
    if not value:
        return ""
    raw = base64.b64decode(value)
    if stored.get("scheme") == "dpapi":
        unprotected = _dpapi("CryptUnprotectData", raw)
        return unprotected.decode("utf-8") if unprotected else ""
    return raw.decode("utf-8", errors="ignore")


def load_credentials(path: Path | None = None) -> Credentials:
    path = path or CREDENTIALS_PATH
    if not path.exists():
        return Credentials()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Credentials()
    return Credentials(
        email=str(data.get("email") or ""),
        password=_decrypt(data.get("password") or {}),
    )


def save_credentials(creds: Credentials, path: Path | None = None) -> Path:
    path = path or CREDENTIALS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"email": creds.email.strip(), "password": _encrypt(creds.password)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_credentials(path: Path | None = None) -> None:
    path = path or CREDENTIALS_PATH
    if path.exists():
        path.unlink()
