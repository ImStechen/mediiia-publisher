"""Сквозная проверка: файл → блоки + концовка → черновик на Mediiia."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import load_session
from src.config import load_config, tag_names_from_config, tail_templates
from src.mediiia_api import MediiiaClient
from src.parser import TailSettings, assemble, load_article

PARTNERS = (
    "CLOZE | Локальные бренды (https://t.me/clozesstore), "
    "Школа индустрии моды Розмари Турман (https://t.me/howfashionworks)"
)
TITLE = "«Индустриальный искусственный интеллект»: как модной индустрии выжить на падающем рынке"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    session = load_session()
    if not session:
        print("Нет сессии — сначала войдите.")
        return 1

    cfg = load_config()
    root = Path(__file__).resolve().parent.parent
    article = load_article(root / "9 сентября.docx", is_path=True, title_hint=TITLE)
    full = assemble(
        article,
        TailSettings(
            event_date="9 сентября 2026 года",
            time_from="18:30",
            time_to="21:00",
            partners_raw=PARTNERS,
        ),
        tail_templates(cfg),
    )
    print(f"Блоков к заливке: {len(full.blocks)}")

    account_id = (cfg.get("account_id") or "").strip() or session.get("account_id")
    with MediiiaClient(session["access_token"], account_id) as client:
        tag_ids = client.resolve_tag_ids(
            tag_names_from_config(cfg), cfg.get("default_tag_ids") or {}
        )
        print("tagsID:", tag_ids)

        result = client.create_draft_from_article(
            full,
            tag_names=tag_names_from_config(cfg),
            coauthor_ids=list(cfg.get("default_coauthor_ids") or []),
            open_browser=False,
            tag_ids_map=cfg.get("default_tag_ids") or {},
        )

    print(f"Готово: {result.blocks_created} блоков")
    print(result.edit_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
