from src.config import DEFAULT_TAIL_TEMPLATES
from src.parser import (
    GREEN,
    TailSettings,
    _docx_paragraph_to_markdown,
    assemble,
    markdown_inline_to_html,
    parse_partners,
    parse_plain_text,
    vk_video_iframe,
)


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
    assert kinds == [
        "green_top",
        "intro",
        "paragraph",
        "outro",
        "partners",
        "video",
        "green_bottom",
    ]
    assert full.blocks[0].color == GREEN
    assert full.blocks[-1].color == GREEN
    assert "9 сентября 2026 года с 18:30 до 21:00" in full.blocks[-1].text
    assert "Дополнительный текст от редактора" in full.blocks[3].text
    assert '<a href="https://t.me/partner"' in full.blocks[4].text


def test_banner_variants_and_custom_text():
    article = parse_plain_text("Заголовок\n\nАбзац.")
    telegram = assemble(
        article,
        TailSettings(
            event_date="16 июля",
            time_from="18:30",
            time_to="21:00",
            top_banner="telegram_bot",
            bottom_banner="telegram_channel",
        ),
        DEFAULT_TAIL_TEMPLATES,
    )
    assert "crehub_hse_bot" in telegram.blocks[0].text
    assert "creativehub_hse" in telegram.blocks[-1].text
    assert "<a href=" in telegram.blocks[0].text

    custom = assemble(
        article,
        TailSettings(
            event_date="16 июля",
            top_banner="custom",
            top_banner_custom='<strong>Свой верх</strong> и <a href="https://example.com">ссылка</a>',
            bottom_banner="custom",
            bottom_banner_custom="Свой низ: {date}",
        ),
        DEFAULT_TAIL_TEMPLATES,
    )
    assert custom.blocks[0].text.startswith("<strong>Свой верх</strong>")
    assert custom.blocks[-1].text == "Свой низ: 16 июля"


def test_banners_can_be_disabled():
    article = parse_plain_text("Заголовок\n\nАбзац.")
    full = assemble(
        article,
        TailSettings(top_banner="none", bottom_banner="none"),
        DEFAULT_TAIL_TEMPLATES,
    )
    assert not any(block.source.startswith("green") for block in full.blocks)


def test_config_can_override_promo_and_date_dependent_banners_wait_for_date():
    article = parse_plain_text("Заголовок\n\nАбзац.")
    configured = assemble(
        article,
        TailSettings(top_banner="promo", bottom_banner="none"),
        {"promo_banner": "Промо из config.json"},
    )
    assert configured.blocks[0].text == "Промо из config.json"

    without_date = assemble(
        article,
        TailSettings(top_banner="webinars", bottom_banner="telegram_channel"),
        DEFAULT_TAIL_TEMPLATES,
    )
    assert not any(block.source.startswith("green") for block in without_date.blocks)


def test_heading_next_to_body_and_stars_in_link_are_preserved():
    article = parse_plain_text("Заголовок\n\n# Раздел\nТекст раздела.")
    assert len(article.blocks) == 1
    assert article.blocks[0].text == "<h3>Раздел</h3><br><br>Текст раздела."

    html = '<a href="https://example.com/*keep*/x">*курсив*</a>'
    converted = markdown_inline_to_html(html)
    assert 'href="https://example.com/*keep*/x"' in converted
    assert "<em>курсив</em>" in converted


def test_docx_conversion_keeps_bold_italic_and_hyperlink():
    class Run:
        def __init__(self, text, *, bold=False, italic=False):
            self.text = text
            self.bold = bold
            self.italic = italic

    class Hyperlink:
        url = "https://example.com"
        runs = [Run("ссыл", bold=True), Run("ка", italic=True)]

    class Paragraph:
        text = "Жирный, курсив и ссылка"

        @staticmethod
        def iter_inner_content():
            return [
                Run("Жирный", bold=True),
                Run(", "),
                Run("курсив", italic=True),
                Run(" и "),
                Hyperlink(),
            ]

    markup = _docx_paragraph_to_markdown(Paragraph())
    assert "<strong>Жирный</strong>" in markup
    assert "<em>курсив</em>" in markup
    assert '<a href="https://example.com"' in markup
    assert "<strong>ссыл</strong><em>ка</em>" in markup
