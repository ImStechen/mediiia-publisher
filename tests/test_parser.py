from src.config import DEFAULT_TAIL_TEMPLATES
from src.parser import GREEN, TailSettings, assemble, parse_partners, parse_plain_text, vk_video_iframe


def test_gemini_like_article():
    raw = """Заголовок события

Первый абзац с **жирным** именем.

> Цитата спикера номер один.

Второй абзац.

> Вторая цитата.
"""
    article = parse_plain_text(raw)
    assert article.title == "Заголовок события"
    assert len(article.blocks) == 4
    assert article.blocks[0].style == "normal"
    assert "<strong>жирным</strong>" in article.blocks[0].text
    assert article.blocks[1].style == "quote"
    assert "Цитата спикера" in article.blocks[1].text
    assert article.blocks[3].style == "quote"


def test_multiline_quote():
    raw = """Title

> line one
> line two
"""
    article = parse_plain_text(raw)
    assert len(article.blocks) == 1
    assert article.blocks[0].style == "quote"
    assert article.blocks[0].title == "line one line two"


def test_quote_author_is_parsed_or_inferred():
    explicit = parse_plain_text('Title\n\n> «Главная мысль» — Анна Иванова.')
    assert explicit.blocks[0].quote_author == "Анна Иванова"
    assert explicit.blocks[0].title == "Главная мысль"

    inferred = parse_plain_text(
        "Title\n\nВыступила **Мария Петрова**, руководитель проекта.\n\n> Важная цитата."
    )
    assert inferred.blocks[1].quote_author == "Мария Петрова"


def test_heading_is_joined_to_following_paragraph_and_lead_removed():
    article = parse_plain_text(
        "Title\n\nОбщий лид статьи.\n\n**Раздел статьи**\n\n"
        "Первое предложение раздела."
    )
    assert len(article.blocks) == 1
    assert article.blocks[0].source == "paragraph"
    assert article.blocks[0].text.startswith("<h3>Раздел статьи</h3><br><br>")


def test_partners_keep_commas_and_pipes_in_names():
    raw = (
        "CLOZE | Локальные бренды (https://t.me/clozesstore), "
        "Школа индустрии моды Розмари Турман (https://t.me/howfashionworks)"
    )
    assert parse_partners(raw) == [
        ("CLOZE | Локальные бренды", "https://t.me/clozesstore"),
        ("Школа индустрии моды Розмари Турман", "https://t.me/howfashionworks"),
    ]


def test_video_requires_embed_code():
    assert vk_video_iframe("https://vkvideo.ru/video-215704772_456239157") == ""
    assert vk_video_iframe("<iframe src='x'></iframe>") == "<iframe src='x'></iframe>"


def test_tail_wraps_article_with_green_blocks():
    article = parse_plain_text("Заголовок\n\nАбзац текста.")
    tail = TailSettings(
        event_date="9 сентября 2026 года",
        time_from="18:30",
        time_to="21:00",
        record_url="https://vkvideo.ru/video-215704772_456239157",
        partners_raw="Партнёр (https://t.me/partner)",
        extra_info="Дополнительный текст от редактора.",
        video_embed="<iframe src='https://vkvideo.ru/video_ext.php'></iframe>",
    )
    full = assemble(article, tail, DEFAULT_TAIL_TEMPLATES)

    kinds = [block.source for block in full.blocks]
    assert kinds == ["green", "intro", "paragraph", "outro", "partners", "video", "green"]
    assert full.blocks[0].color == GREEN
    assert full.blocks[-1].color == GREEN
    assert "9 сентября 2026 года с 18:30 до 21:00" in full.blocks[-1].text
    assert "Дополнительный текст от редактора" in full.blocks[3].text
    assert '<a href="https://t.me/partner"' in full.blocks[4].text
