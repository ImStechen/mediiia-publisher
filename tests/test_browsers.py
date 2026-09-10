from __future__ import annotations

import json

import src.browsers as browsers


def test_browser_names_and_normalization() -> None:
    assert browsers.normalize_browser("chrome") == "chrome"
    assert browsers.normalize_browser("msedge") == "msedge"
    assert browsers.normalize_browser("unknown") == "chrome"
    assert browsers.browser_label("msedge") == "Microsoft Edge"


def test_browser_preference_roundtrip(tmp_path, monkeypatch) -> None:
    path = tmp_path / "preferences.json"
    monkeypatch.setattr(browsers, "PREFERENCES_PATH", path)

    browsers.save_browser_preference("msedge")

    assert browsers.load_browser_preference() == "msedge"
    assert json.loads(path.read_text(encoding="utf-8")) == {"browser": "msedge"}
