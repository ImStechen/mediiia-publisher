"""Какие теги стоят у опубликованных статей и что отдают эндпоинты тегов."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import load_session

GEO = "https://api.mediiia.ru/geograffee"
TAGS = "https://api.mediiia.ru/tags"

PROJECTS = {
    "Слабое звено": "861e8cdf01454e46b0323460678d16d5",
    "Визуальный хук": "883c97655e2344d681b096a9f25619c7",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    session = load_session()
    headers = {"Accept": "application/json, text/plain, */*", "Origin": "https://mediiia.com"}
    if session:
        headers["Authorization"] = f"Bearer {session['access_token']}"
        print("сессия есть:", session.get("email"))
    else:
        print("сессии нет — запросы без токена")

    client = httpx.Client(timeout=60, headers=headers)

    wanted_ids: set[str] = set()
    for name, project_id in PROJECTS.items():
        resp = client.get(f"{GEO}/api/project/Get", params={"idProject": project_id})
        print(f"\n=== {name}: project/Get {resp.status_code}")
        if resp.status_code >= 400:
            print(resp.text[:300])
            continue
        data = resp.json()
        tags = data.get("tagsID") or data.get("tagsId") or []
        print("tagsID:", tags)
        wanted_ids.update(str(t) for t in tags)
        for key in ("tags", "tagsList", "tagObjects"):
            if data.get(key):
                print(key, json.dumps(data[key], ensure_ascii=False)[:600])

    for url, params in (
        (f"{TAGS}/api/tags/GetTagsTree", {"onlyCategories": "false", "status": "0", "includeSubCategories": "true", "lang": "ru"}),
        (f"{TAGS}/api/Tags/GetTagsList", {"types": "2"}),
        (f"{TAGS}/api/Tags/GetTagsList", {}),
    ):
        resp = client.get(url, params=params)
        print(f"\n=== {url} {params} → {resp.status_code}")
        if resp.status_code >= 400:
            print(resp.text[:300])
            continue
        data = resp.json()
        print("тип:", type(data).__name__, "длина:", len(data) if hasattr(data, "__len__") else "-")
        sample = data[:2] if isinstance(data, list) else data
        print(json.dumps(sample, ensure_ascii=False)[:1200])

        if isinstance(data, list) and wanted_ids:
            print("-- совпадения по id из статей --")
            for item in data:
                if not isinstance(item, dict):
                    continue
                tid = str(item.get("tagId") or item.get("id") or "")
                if tid in wanted_ids:
                    print(" ", tid, json.dumps(item.get("name") or item.get("title"), ensure_ascii=False))


if __name__ == "__main__":
    main()
