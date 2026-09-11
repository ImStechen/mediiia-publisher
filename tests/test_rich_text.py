from __future__ import annotations

import pytest

from src.parser import article_to_markup, markdown_inline_to_html, parse_plain_text
from src.rich_text import markup_to_html, parse_markup, safe_url


def test_parse_markup_understands_visual_formats() -> None:
    markup = (
        "# Подзаголовок\n\n"
        'Обычный <strong>жирный</strong>, <em>курсив</em> и '
        '<a href="https://example.com">ссылка</a>.\n\n'
        "> Цитата"
    )
    text, spans = parse_markup(markup)

    assert text == "Подзаголовок\n\nОбычный жирный, курсив и ссылка.\n\nЦитата"
    kinds = [kind for kind, _start, _end, _meta in spans]
    assert {"h3", "bold", "italic", "a", "blockquote"} <= set(kinds)
    link = next(span for span in spans if span[0] == "a")
    assert link[3] == "https://example.com"


def test_markdown_and_html_formatting_reaches_parser() -> None:
    article = parse_plain_text(
        "Название\n\n"
        "Текст с **жирным**, *курсивом* и [ссылкой](https://example.com)."
    )
    body = article.blocks[0].text
    assert "<strong>жирным</strong>" in body
    assert "<em>курсивом</em>" in body
    assert '<a href="https://example.com"' in body

    mixed = markdown_inline_to_html(
        "<strong>Имя</strong>, *курсив* и [сайт](https://example.com)"
    )
    assert "<strong>Имя</strong>" in mixed
    assert "<em>курсив</em>" in mixed
    assert '<a href="https://example.com"' in mixed


def test_article_markup_round_trip_keeps_structure() -> None:
    original = parse_plain_text(
        "Название\n\n# Раздел\n\n"
        "Текст с **жирным**.\n\n> «Мысль» — Анна Иванова"
    )
    restored = parse_plain_text(article_to_markup(original))

    assert restored.title == original.title
    assert [block.source for block in restored.blocks] == [
        block.source for block in original.blocks
    ]
    assert "<strong>жирным</strong>" in restored.blocks[0].text
    assert restored.blocks[1].quote_author == "Анна Иванова"


def test_markup_to_html_and_url_validation() -> None:
    assert markup_to_html("# Заголовок\n\nТекст") == "<h3>Заголовок</h3><br><br>Текст"
    assert safe_url("t.me/creativehub_hse") == "https://t.me/creativehub_hse"
    assert safe_url("") == ""
    with pytest.raises(ValueError):
        safe_url("https://")
