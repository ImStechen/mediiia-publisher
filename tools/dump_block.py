"""Полный текст конкретных блоков — чтобы точно повторить шаблоны концовки."""

from __future__ import annotations

import sys

import httpx

TARGETS = [
    ("Визуальный хук", "883c97655e2344d681b096a9f25619c7"),
    ("Слабое звено", "861e8cdf01454e46b0323460678d16d5"),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = httpx.Client(timeout=60)

    for name, longread_id in TARGETS:
        blocks = client.get(
            "https://api.mediiia.ru/longreads/api/post/GetMany",
            params={"idLongread": longread_id},
        ).json()
        blocks.sort(key=lambda b: b.get("position", 0))

        print("#" * 100)
        print(name)
        for block in blocks:
            text = block.get("text") or ""
            is_green = block.get("color") == "#3ccd29"
            is_partners = "партн" in text.lower()
            is_record = "записи" in text.lower() or "послушать" in text.lower()
            if is_green or is_partners or is_record:
                print("-" * 100)
                print(f"pos={block.get('position')} style={block.get('style')} color={block.get('color')}")
                print(repr(text))


if __name__ == "__main__":
    main()
