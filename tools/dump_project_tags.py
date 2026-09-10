"""Названия тегов у опубликованных статей — для config.json."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import load_session

GEO = "https://api.mediiia.ru/geograffee"

PROJECTS = {
    "Слабое звено": "861e8cdf01454e46b0323460678d16d5",
    "Визуальный хук": "883c97655e2344d681b096a9f25619c7",
    "Креативный трек": "26e4363ce9cc429b8e2082d5e6c4e90a",
    "Звук. Пространство": "f7934e22ae1b45bfaaff95e0e790bd9b",
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    session = load_session()
    headers = {"Accept": "application/json, text/plain, */*", "Origin": "https://mediiia.com"}
    if session:
        headers["Authorization"] = f"Bearer {session['access_token']}"
    client = httpx.Client(timeout=60, headers=headers)

    for label, project_id in PROJECTS.items():
        data = client.get(f"{GEO}/api/project/Get", params={"idProject": project_id}).json()
        print(f"\n=== {label}")
        print("статус:", data.get("status"), "| protectedStatus:", data.get("protectedStatus"))
        print("coAuthorIds:", data.get("coAuthorIds"))
        for tag in data.get("tags") or []:
            names = {str(n.get("lang")).lower(): n.get("name") for n in tag.get("name") or []}
            print(
                f"  {tag.get('tagId')}  ru={names.get('ru')!r}  en={names.get('en')!r}  "
                f"title={tag.get('title')!r}  isEducationTag={tag.get('isEducationTag')}"
            )


if __name__ == "__main__":
    main()
