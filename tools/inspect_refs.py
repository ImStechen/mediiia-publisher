"""Разбор опубликованных статей: концовки, цвета плашек, кнопки."""

from __future__ import annotations

import json
import sys

import httpx

ARTICLES = {
    "Слабое звено": "861e8cdf01454e46b0323460678d16d5",
    "Визуальный хук": "883c97655e2344d681b096a9f25619c7",
    "Креативный трек": "26e4363ce9cc429b8e2082d5e6c4e90a",
    "Звук. Пространство": "f7934e22ae1b45bfaaff95e0e790bd9b",
}

TAIL = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = httpx.Client(timeout=60)

    for name, longread_id in ARTICLES.items():
        resp = client.get(
            "https://api.mediiia.ru/longreads/api/post/GetMany",
            params={"idLongread": longread_id},
        )
        blocks = resp.json()
        blocks.sort(key=lambda b: b.get("position", 0))

        print("=" * 100)
        print(f"{name} | блоков: {len(blocks)}")

        combos: dict[tuple, int] = {}
        for block in blocks:
            key = (block.get("style"), block.get("color"))
            combos[key] = combos.get(key, 0) + 1
        print("style/color:", combos)

        print(f"-- последние {TAIL} блоков --")
        for block in blocks[-TAIL:]:
            print(
                f"pos={block.get('position')} style={block.get('style')} "
                f"color={block.get('color')} titlePosition={block.get('titlePosition')}"
            )
            text = (block.get("text") or "").replace("\n", " ")
            print("   text:", text[:500])
            if block.get("buttons"):
                print("   buttons:", json.dumps(block["buttons"], ensure_ascii=False)[:400])
            if block.get("linkText"):
                print("   linkText:", block["linkText"])
            if block.get("caption"):
                print("   caption:", str(block["caption"])[:200])
            extra = block.get("additionalInfo") or []
            if extra:
                print("   additionalInfo:", json.dumps(extra, ensure_ascii=False)[:250])


if __name__ == "__main__":
    main()
