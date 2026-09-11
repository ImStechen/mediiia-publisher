"""Проверка: инфопартнёры, зелёные плашки и концовка на реальном файле."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, tail_templates
from src.parser import TailSettings, assemble, load_article, parse_partners

PARTNERS = (
    "CLOZE | Локальные бренды (https://t.me/clozesstore), "
    "Школа индустрии моды Розмари Турман (https://t.me/howfashionworks)"
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    print("— разбор инфопартнёров —")
    for name, url in parse_partners(PARTNERS):
        print(f"  {name!r} → {url}")

    article = load_article(
        Path(__file__).resolve().parent.parent / "9 сентября.docx",
        is_path=True,
        title_hint="«Индустриальный искусственный интеллект»: как модной индустрии выжить на падающем рынке",
    )
    tail = TailSettings(
        event_date="9 сентября",
        time_from="19:00",
        time_to="21:30",
        record_url="https://vkvideo.ru/video-215704772_456239157",
        partners_raw=PARTNERS,
        video_embed="https://vkvideo.ru/video-215704772_456239157",
        promo_banner=True,
    )
    full = assemble(article, tail, tail_templates(load_config()))

    print(f"\n— собрано блоков: {len(full.blocks)} (тело: {len(article.blocks)}) —")
    for line in full.preview_lines():
        print(line)

    print("\n— HTML служебных блоков —")
    for block in full.blocks:
        if block.source.startswith("green") or block.source in {"partners", "outro", "video"}:
            print(f"[{block.source}] style={block.style} color={block.color or '(по умолчанию)'}")
            print(block.text)
            print()


if __name__ == "__main__":
    main()
