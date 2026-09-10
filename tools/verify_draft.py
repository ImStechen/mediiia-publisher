"""Проверка созданного черновика: блоки, стили, цвета, порядок."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import load_session

GEO = "https://api.mediiia.ru/geograffee"
LONGREADS = "https://api.mediiia.ru/longreads"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("Использование: python tools\\verify_draft.py <projectId>")
        return 2
    project_id = sys.argv[1]

    session = load_session()
    headers = {"Accept": "application/json, text/plain, */*", "Origin": "https://mediiia.com"}
    if session:
        headers["Authorization"] = f"Bearer {session['access_token']}"
    client = httpx.Client(timeout=60, headers=headers)

    project = client.get(f"{GEO}/api/project/Get", params={"idProject": project_id}).json()
    title = {str(n.get("lang")).lower(): n.get("name") for n in project.get("title") or []}
    print("название:", title.get("ru"))
    print("статус:", project.get("status"), "| protectedStatus:", project.get("protectedStatus"))
    print("теги:", [t.get("title") for t in project.get("tags") or []])

    longread_id = project.get("longreadId") or project_id
    blocks = client.get(
        f"{LONGREADS}/api/post/GetMany", params={"idLongread": longread_id}
    ).json()
    blocks.sort(key=lambda b: b.get("position", 0))
    print(f"\nблоков: {len(blocks)}")
    for block in blocks:
        text = (block.get("text") or "").replace("\n", " ")
        print(
            f"{block.get('position'):3d} {block.get('style'):8s} {str(block.get('color')):8s} "
            f"{text[:90]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
