"""Детерминированный разбор текста Gemini / Word в блоки Mediiia."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


GREEN = "#3ccd29"

BLOCK_LABELS = {
    "quote": "ЦИТАТА",
    "green": "ЗЕЛЁНАЯ ПЛАШКА",
    "green_top": "ВЕРХНЯЯ ЗЕЛЁНАЯ ПЛАШКА",
    "green_bottom": "НИЖНЯЯ ЗЕЛЁНАЯ ПЛАШКА",
    "intro": "ВСТУПЛЕНИЕ",
    "partners": "ИНФОПАРТНЁРЫ",
    "outro": "ЗАПИСЬ + ДОП. ИНФО",
    "video": "ВИДЕО",
}


@dataclass
class Block:
    style: str  # normal | colored | video
    text: str
    source: str = "paragraph"
    color: str = ""
    title: str = ""
    quote_author: str = ""


@dataclass
class Article:
    title: str
    blocks: list[Block]

    def preview_lines(self) -> list[str]:
        lines = [f"НАЗВАНИЕ: {self.title or '(не найдено — заполните вручную)'}", ""]
        for i, block in enumerate(self.blocks, 1):
            kind = BLOCK_LABELS.get(block.source, "АБЗАЦ")
            if block.source == "quote" and block.quote_author:
                kind += f" — {block.quote_author}"
            snippet = block.text.replace("<br>", " ").replace("\n", " ")
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            if len(snippet) > 130:
                snippet = snippet[:127] + "…"
            lines.append(f"{i:2d}. [{kind}] {snippet}")
        return lines


def article_to_markup(article: Article) -> str:
    """Обратимое представление статьи для визуального редактора исходника."""
    chunks = [article.title.strip()] if article.title.strip() else []
    for block in article.blocks:
        if block.source == "quote":
            quote = f"«{block.title or strip_markup(block.text)}»"
            if block.quote_author:
                quote += f" — {block.quote_author}"
            chunks.append("> " + quote)
            continue
        text = re.sub(
            r"^\s*<h3>(.*?)</h3>", r"# \1", block.text, count=1, flags=re.I | re.S
        )
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I).strip()
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)


_BOLD_MD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_MD = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_LINK_MD = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_QUOTE_PREFIX = re.compile(r"^>\s?")
_HEADING = re.compile(r"^#{1,6}\s+")
_MULTI_NL = re.compile(r"\n{3,}")
_TAGS = re.compile(r"<[^>]+>")
_STRONG = re.compile(r"<strong>(.+?)</strong>", re.I | re.S)
_QUOTE_WITH_AUTHOR_AFTER = re.compile(
    r'^[«"](?P<body>.+?)[»"]\s*[—–-]\s*(?P<author>[^<>\n]{2,90}?)[.]?$',
    re.S,
)
_QUOTE_WITH_AUTHOR_BEFORE = re.compile(
    r'^(?P<author>[^:«"<>\n]{2,90}):\s*[«"](?P<body>.+?)[»"][.]?$',
    re.S,
)
_QUOTE_ONLY = re.compile(r'^[«"](?P<body>.+?)[»"][.]?$', re.S)

TITLE_MAX_LEN = 150
ATTRIBUTION_MAX_LEN = 90


def strip_markup(text: str) -> str:
    return _TAGS.sub("", text).replace("**", "").strip()


def markdown_inline_to_html(text: str) -> str:
    """Жирный, курсив и ссылки → HTML, уже готовые разрешённые теги сохраняем."""
    text = text.strip()
    if not text:
        return ""
    text = re.sub(
        r"</?b>",
        lambda m: "<strong>" if m.group(0).lower() == "<b>" else "</strong>",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"</?i>",
        lambda m: "<em>" if m.group(0).lower() == "<i>" else "</em>",
        text,
        flags=re.I,
    )
    text = _LINK_MD.sub(
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text
    )
    text = _BOLD_MD.sub(r"<strong>\1</strong>", text)
    return _ITALIC_MD.sub(r"<em>\1</em>", text)


def is_typographic_quote(text: str) -> bool:
    """Абзац-цитата вида «текст» — так цитаты выглядят в статьях Mediiia."""
    s = strip_markup(text)
    if not s or s[0] not in "«\"":
        return False
    closing = "»" if s[0] == "«" else '"'
    idx = s.find(closing, 1)
    if idx == -1:
        return False
    tail = s[idx + 1 :].strip()
    if not tail:
        return True
    # Допускаем короткую атрибуцию: — Имя Фамилия.
    return len(tail) <= ATTRIBUTION_MAX_LEN


def _normalize(raw: str) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    return _MULTI_NL.sub("\n\n", raw).strip()


def _split_chunks(raw: str) -> list[str]:
    """Пустая строка разделяет блоки; внутри блока строки сохраняются."""
    chunks: list[str] = []
    buf: list[str] = []
    for line in _normalize(raw).split("\n"):
        if not line.strip():
            if buf:
                chunks.append("\n".join(buf).strip())
                buf = []
            continue
        buf.append(line.rstrip())
    if buf:
        chunks.append("\n".join(buf).strip())
    return [c for c in chunks if c]


def _is_md_quote_line(line: str) -> bool:
    return bool(_QUOTE_PREFIX.match(line.strip()))


def _to_html_body(lines: list[str]) -> str:
    plain = "\n".join(line.strip() for line in lines)
    return markdown_inline_to_html(plain).replace("\n", "<br>")


def _quote_parts(text: str) -> tuple[str, str]:
    """Возвращает чистый текст цитаты и автора из двух форматов Gemini."""
    plain = strip_markup(text).strip()
    for pattern in (_QUOTE_WITH_AUTHOR_AFTER, _QUOTE_WITH_AUTHOR_BEFORE):
        match = pattern.match(plain)
        if match:
            return (
                match.group("body").strip().rstrip("."),
                match.group("author").strip().rstrip("."),
            )
    match = _QUOTE_ONLY.match(plain)
    if match:
        plain = match.group("body").strip()
    return plain.rstrip("."), ""


def _quote_block(text: str) -> Block | None:
    body, author = _quote_parts(text)
    if not body:
        return None
    return Block(
        style="quote",
        title=body,
        text=f"«{body}».",
        source="quote",
        color="#ffffff",
        quote_author=author,
    )


def _chunk_to_block(chunk: str) -> Block | None:
    lines = [ln for ln in chunk.split("\n") if ln.strip()]
    if not lines:
        return None

    # 1. Цитата в markdown: все строки с >
    if all(_is_md_quote_line(ln) for ln in lines):
        body = " ".join(_QUOTE_PREFIX.sub("", ln.strip()) for ln in lines)
        return _quote_block(body)

    # 2. Цитата в кавычках «...»
    joined = " ".join(ln.strip() for ln in lines)
    if is_typographic_quote(joined):
        return _quote_block(joined)

    # 3. Подзаголовок: markdown-решётка или одиночный полностью жирный абзац
    if len(lines) == 1:
        single = lines[0].strip()
        if _HEADING.match(single):
            body = markdown_inline_to_html(_HEADING.sub("", single).strip())
            return Block(style="normal", text=body, source="heading") if body else None
        stripped = single.strip()
        is_all_bold = (
            stripped.startswith("**")
            and stripped.endswith("**")
            and stripped.count("**") == 2
        ) or (
            stripped.lower().startswith("<strong>")
            and stripped.lower().endswith("</strong>")
            and stripped.lower().count("<strong>") == 1
        )
        if is_all_bold and len(strip_markup(stripped)) <= TITLE_MAX_LEN:
            body = markdown_inline_to_html(stripped)
            return Block(style="normal", text=body, source="heading") if body else None

    # 4. Обычный абзац
    cleaned = [_QUOTE_PREFIX.sub("", ln.strip()) for ln in lines]
    body = _to_html_body(cleaned)
    return Block(style="normal", text=body, source="paragraph") if body else None


def _looks_like_person_name(text: str) -> bool:
    words = re.findall(r"[А-ЯЁA-Z][а-яёa-z-]+", strip_markup(text))
    return 2 <= len(words) <= 5 and len(strip_markup(text)) <= 70


def _as_h3(text: str) -> str:
    """Подзаголовок оформляем тегом h3 — так же, как в статьях хаба."""
    inner = text.strip()
    match = re.fullmatch(r"<strong>(.+)</strong>", inner, re.I | re.S)
    if match:
        inner = match.group(1).strip()
    return f"<h3>{inner}</h3>"


def _infer_quote_authors(blocks: list[Block]) -> None:
    """Если Gemini не подписал цитату, берём имя из предыдущего блока спикера."""
    for index, block in enumerate(blocks):
        if block.source != "quote" or block.quote_author or index == 0:
            continue
        candidates = _STRONG.findall(blocks[index - 1].text)
        for candidate in candidates:
            if _looks_like_person_name(candidate):
                block.quote_author = strip_markup(candidate)
                break


def _split_long_paragraph(text: str, threshold: int = 520, target: int = 320) -> str:
    """Длинный текст внутри блока делим на читаемые абзацы через пустую строку."""
    if len(strip_markup(text)) <= threshold or "<br><br>" in text:
        return text
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    if len(sentences) < 2:
        return text
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(strip_markup(current + " " + sentence)) > target:
            parts.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        parts.append(current.strip())
    return "<br><br>".join(parts)


def _tidy_body_blocks(blocks: list[Block]) -> list[Block]:
    """
    Убирает оторванные подзаголовки: приклеивает их к следующему абзацу.
    Типичный ввод Gemini начинается лидом, затем подзаголовком; служебное
    вступление заменит этот лид, поэтому его удаляем.
    """
    if len(blocks) > 1 and blocks[0].source == "paragraph" and blocks[1].source == "heading":
        blocks = blocks[1:]

    merged: list[Block] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if (
            block.source == "heading"
            and index + 1 < len(blocks)
            and blocks[index + 1].source == "paragraph"
        ):
            following = blocks[index + 1]
            merged.append(
                Block(
                    style="normal",
                    text=f"{_as_h3(block.text)}<br><br>{following.text}",
                    source="paragraph",
                )
            )
            index += 2
            continue
        if block.source == "heading":
            merged.append(Block(style="normal", text=_as_h3(block.text), source="heading"))
            index += 1
            continue
        if block.source == "paragraph":
            block.text = _split_long_paragraph(block.text)
        merged.append(block)
        index += 1

    _infer_quote_authors(merged)
    return merged


def _looks_like_title(chunk: str) -> bool:
    if "\n" in chunk.strip():
        return False
    if is_typographic_quote(chunk):
        return False
    if _is_md_quote_line(chunk):
        return False
    plain = strip_markup(chunk)
    if not plain or len(plain) > TITLE_MAX_LEN:
        return False
    # Заголовок обычно без точки в конце
    return not plain.endswith(".")


def parse_plain_text(raw: str, title_hint: str | None = None) -> Article:
    """
    Правила:
    - первая короткая строка без точки → название (длинный лид названием не считаем);
    - пустая строка разделяет блоки;
    - строки с > и абзацы «в кавычках» → блок colored;
    - **текст** → <strong>текст</strong>.
    """
    chunks = _split_chunks(raw)
    if not chunks:
        return Article(title=title_hint or "", blocks=[])

    title = (title_hint or "").strip()
    body_chunks = chunks

    if not title:
        first = chunks[0]
        if _looks_like_title(first):
            title = strip_markup(_HEADING.sub("", first))
            body_chunks = chunks[1:]

    blocks: list[Block] = []
    for chunk in body_chunks:
        lines = [ln for ln in chunk.split("\n") if ln.strip()]
        has_quote = any(_is_md_quote_line(ln) for ln in lines)
        has_plain = any(not _is_md_quote_line(ln) for ln in lines)
        if has_quote and has_plain:
            # Внутри одного куска перемешаны цитаты и текст — режем по типу строки
            group: list[str] = []
            mode: bool | None = None
            for line in lines:
                cur = _is_md_quote_line(line)
                if mode is None:
                    mode = cur
                if cur != mode:
                    block = _chunk_to_block("\n".join(group))
                    if block:
                        blocks.append(block)
                    group = []
                    mode = cur
                group.append(line)
            if group:
                block = _chunk_to_block("\n".join(group))
                if block:
                    blocks.append(block)
        else:
            block = _chunk_to_block(chunk)
            if block:
                blocks.append(block)

    return Article(title=title, blocks=_tidy_body_blocks(blocks))


def _docx_paragraph_to_markdown(paragraph) -> str:
    """Абзац Word → строка с **жирным**, склеивая соседние runs одного стиля."""
    merged: list[tuple[bool, str]] = []
    for run in paragraph.runs:
        text = run.text or ""
        if not text:
            continue
        bold = bool(run.bold)
        if merged and merged[-1][0] == bold:
            merged[-1] = (bold, merged[-1][1] + text)
        else:
            merged.append((bold, text))

    parts: list[str] = []
    for bold, text in merged:
        if not text.strip():
            parts.append(text)
            continue
        if bold:
            lead = text[: len(text) - len(text.lstrip())]
            tail = text[len(text.rstrip()) :]
            parts.append(f"{lead}**{text.strip()}**{tail}")
        else:
            parts.append(text)

    result = "".join(parts).strip()
    return result or (paragraph.text or "").strip()


def parse_docx(path: str | Path, title_hint: str | None = None) -> Article:
    """Читает .docx: абзацы, жирный текст, стиль «Цитата», цитаты «в кавычках»."""
    from docx import Document

    doc = Document(str(Path(path)))
    lines: list[str] = []
    for paragraph in doc.paragraphs:
        text = _docx_paragraph_to_markdown(paragraph)
        if not text:
            lines.append("")
            continue
        style_name = (paragraph.style.name or "").lower() if paragraph.style else ""
        if ("quote" in style_name or "цитат" in style_name) and not text.startswith(">"):
            text = "> " + text
        lines.append(text)
        lines.append("")  # каждый абзац Word — отдельный блок

    return parse_plain_text("\n".join(lines), title_hint=title_hint)


@dataclass
class TailSettings:
    """Данные, которые пользователь вводит в окне для служебной концовки."""

    event_date: str = ""  # «9 сентября»
    time_from: str = ""  # «18:30»
    time_to: str = ""  # «21:00»
    record_url: str = ""  # ссылка на запись в VK Видео
    partners_raw: str = ""  # «Название (ссылка), Название (ссылка)»
    extra_info: str = ""  # произвольная информация после ссылки на запись
    video_embed: str = ""  # именно iframe-код VK
    top_banner: str = "promo"
    top_banner_custom: str = ""
    bottom_banner: str = "site"
    bottom_banner_custom: str = ""
    promo_banner: bool | None = None  # совместимость со старыми вызовами


_LINK_IN_PARENS = re.compile(r"\((https?://[^)\s]+)\)")


def html_link(url: str, text: str) -> str:
    return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{text}</a>'


def parse_partners(raw: str) -> list[tuple[str, str]]:
    """
    «CLOZE | Локальные бренды (https://t.me/clozesstore), Школа моды (https://t.me/x)»
    → [("CLOZE | Локальные бренды", "https://t.me/clozesstore"), ...]

    Разделителем считается сама ссылка в скобках, поэтому запятые и «|»
    внутри названия канала не ломают разбор.
    """
    raw = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    partners: list[tuple[str, str]] = []
    cursor = 0
    for match in _LINK_IN_PARENS.finditer(raw):
        name = raw[cursor : match.start()].replace("\n", " ")
        name = name.strip().strip(",;•*").strip()
        name = re.sub(r"\s{2,}", " ", name)
        cursor = match.end()
        if name:
            partners.append((name, match.group(1)))
    return partners


def vk_video_iframe(source: str) -> str:
    """Принимает именно готовый iframe-код VK."""
    text = (source or "").strip()
    if not text:
        return ""
    if "<iframe" in text.lower():
        return text
    return ""


def _fill(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def _banner_text(
    selected: str,
    custom: str,
    options: dict[str, tuple[str, str]],
    values: dict[str, str],
) -> str:
    if selected == "custom":
        template = custom.strip()
    else:
        template = options.get(selected, ("", ""))[1]
    return _fill(template, values).strip()


def build_intro_blocks(
    article: Article, tail: TailSettings, templates: dict[str, str]
) -> list[Block]:
    from .config import TOP_BANNER_OPTIONS

    blocks: list[Block] = []
    selected = tail.top_banner
    if tail.promo_banner is False:
        selected = "none"
    elif tail.promo_banner is True and selected == "promo":
        # Старый config.json может переопределять текст промокода.
        TOP_BANNER_OPTIONS = dict(TOP_BANNER_OPTIONS)
        TOP_BANNER_OPTIONS["promo"] = (
            TOP_BANNER_OPTIONS["promo"][0],
            templates.get("promo_banner") or TOP_BANNER_OPTIONS["promo"][1],
        )
    banner = _banner_text(
        selected,
        tail.top_banner_custom,
        TOP_BANNER_OPTIONS,
        {"date": tail.event_date.strip(), "title": article.title.strip()},
    )
    if banner:
        blocks.append(
            Block(style="colored", text=banner, source="green_top", color=GREEN)
        )

    intro = (templates.get("intro_template") or "").strip()
    if intro and tail.event_date.strip():
        blocks.append(
            Block(
                style="normal",
                text=_fill(
                    intro,
                    {
                        "date": tail.event_date.strip(),
                        "title": article.title.strip(),
                    },
                ),
                source="intro",
            )
        )
    return blocks


def build_tail_blocks(tail: TailSettings, templates: dict[str, str]) -> list[Block]:
    from .config import BOTTOM_BANNER_OPTIONS

    blocks: list[Block] = []

    channel = templates.get("record_channel") or "HSE CREATIVE HUB"
    record_url = tail.record_url.strip() or templates.get("record_channel_url") or ""
    outro = (templates.get("record_template") or "").strip()
    if outro:
        link = html_link(record_url, channel) if record_url else channel
        extra = _normalize(tail.extra_info)
        extra_html = "<br><br>".join(
            markdown_inline_to_html(chunk).replace("\n", "<br>")
            for chunk in _split_chunks(extra)
        )
        text = _fill(outro, {"record_link": link})
        if extra_html:
            text += "<br><br>" + extra_html
        blocks.append(
            Block(
                style="normal",
                text=text,
                source="outro",
            )
        )

    partners = parse_partners(tail.partners_raw)
    if partners:
        intro = templates.get("partners_intro") or ""
        lines = [f"*<strong>{html_link(url, name)}</strong>" for name, url in partners]
        blocks.append(
            Block(
                style="normal",
                text=intro + "\n\n" + "\n".join(lines),
                source="partners",
            )
        )

    iframe = vk_video_iframe(tail.video_embed)
    if iframe:
        blocks.append(Block(style="video", text=iframe, source="video"))

    bottom_options = dict(BOTTOM_BANNER_OPTIONS)
    bottom_options["site"] = (
        bottom_options["site"][0],
        templates.get("event_template") or bottom_options["site"][1],
    )
    banner = _banner_text(
        tail.bottom_banner,
        tail.bottom_banner_custom,
        bottom_options,
        {
            "date": tail.event_date.strip(),
            "time_from": tail.time_from.strip(),
            "time_to": tail.time_to.strip(),
        },
    )
    if banner:
        blocks.append(
            Block(
                style="colored",
                text=banner,
                source="green_bottom",
                color=GREEN,
            )
        )

    return blocks


def assemble(article: Article, tail: TailSettings, templates: dict[str, str]) -> Article:
    """Тело статьи + промо-плашка сверху + служебная концовка снизу."""
    blocks = (
        build_intro_blocks(article, tail, templates)
        + list(article.blocks)
        + build_tail_blocks(tail, templates)
    )
    return Article(title=article.title, blocks=blocks)


def load_article(
    source: str | Path,
    *,
    is_path: bool = False,
    title_hint: str | None = None,
) -> Article:
    if is_path:
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix == ".docx":
            return parse_docx(path, title_hint=title_hint)
        if suffix in {".txt", ".md", ".markdown"}:
            return parse_plain_text(path.read_text(encoding="utf-8"), title_hint=title_hint)
        raise ValueError(f"Неподдерживаемый файл: {suffix}")
    return parse_plain_text(str(source), title_hint=title_hint)
