"""Точка входа: python -m src  или  python main.py"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mediiia публикатор")
    parser.add_argument("--parse", type=Path, help="Только разобрать файл и показать блоки")
    parser.add_argument("--file", type=Path, help="Открыть окно с уже загруженным файлом")
    parser.add_argument("--title", help="Подставить название проекта")
    parser.add_argument("--gui", action="store_true", help="Открыть окно (по умолчанию)")
    args = parser.parse_args(argv)

    if args.parse:
        from src.parser import load_article

        article = load_article(args.parse, is_path=True, title_hint=args.title)
        print("\n".join(article.preview_lines()))
        print(f"\nВсего блоков: {len(article.blocks)}")
        return 0

    from src.gui import run

    run(initial_file=args.file, initial_title=args.title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
