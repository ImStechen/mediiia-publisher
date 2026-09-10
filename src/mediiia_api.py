"""Клиент внутреннего API Mediiia для создания черновика статьи."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .browsers import open_in_browser
from .parser import Article, Block


GEO = "https://api.mediiia.ru/geograffee"
TAGS = "https://api.mediiia.ru/tags"
LONGREADS = "https://api.mediiia.ru/longreads"


@dataclass
class PublishResult:
    project_id: str
    title: str
    edit_url: str
    blocks_created: int
    tag_ids: list[str]


class MediiiaError(RuntimeError):
    pass


class MediiiaClient:
    def __init__(self, access_token: str, account_id: str | None = None, timeout: float = 60.0):
        self.access_token = access_token
        self.account_id = account_id
        self.http = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://mediiia.com",
                "Referer": "https://mediiia.com/",
            },
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> MediiiaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _json(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            raise MediiiaError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        if not resp.content:
            return None
        try:
            return resp.json()
        except json.JSONDecodeError:
            return resp.text

    def resolve_account_id(self) -> str:
        if self.account_id and len(self.account_id) > 8:
            return self.account_id
        # Попробуем вытащить из токена JWT payload (без проверки подписи — только локально)
        try:
            import base64

            parts = self.access_token.split(".")
            if len(parts) >= 2:
                pad = "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
                for key in ("account_id", "accountId", "userid", "user_id", "sub"):
                    if payload.get(key):
                        self.account_id = str(payload[key])
                        return self.account_id
        except Exception:
            pass
        raise MediiiaError(
            "Не удалось определить account_id. Войдите снова через «Войти в Mediiia»."
        )

    def find_tags(self, names: list[str], lang: str = "ru") -> dict[str, str]:
        """Имя тега (ru) → tagId. Ищем по дереву и списку."""
        wanted = {n.strip().lower(): n for n in names if n.strip()}
        found: dict[str, str] = {}

        def match_name(tag: dict[str, Any]) -> str | None:
            for item in tag.get("name") or []:
                if str(item.get("lang", "")).lower() in {"ru", "en"}:
                    nm = str(item.get("name") or "").strip().lower()
                    if nm in wanted:
                        return wanted[nm]
            title = str(tag.get("title") or "").strip().lower()
            if title in wanted:
                return wanted[title]
            return None

        def walk(nodes: Any) -> None:
            if isinstance(nodes, dict):
                nodes = nodes.get("data") or nodes.get("tags") or nodes.get("items") or []
            for node in nodes or []:
                if not isinstance(node, dict):
                    continue
                name = match_name(node)
                tid = node.get("tagId") or node.get("id")
                if name and tid and name not in found:
                    found[name] = str(tid)
                for key in ("additionalTags", "children", "tags", "subTags", "items"):
                    if isinstance(node.get(key), list):
                        walk(node[key])

        # дерево категорий
        r = self.http.get(
            f"{TAGS}/api/tags/GetTagsTree",
            params={"onlyCategories": "false", "status": "0", "includeSubCategories": "true", "lang": lang},
        )
        walk(self._json(r))

        for params in ({"types": "2"}, {}):
            if all(wanted[k] in found for k in wanted):
                break
            r2 = self.http.get(f"{TAGS}/api/Tags/GetTagsList", params=params)
            walk(self._json(r2))

        return found

    def resolve_tag_ids(
        self, tag_names: list[str], explicit_ids: dict[str, str] | None = None
    ) -> list[str]:
        """Готовые id из конфига надёжнее поиска по названию — берём их в первую очередь."""
        explicit = {k.strip().lower(): str(v) for k, v in (explicit_ids or {}).items() if v}
        need_lookup = [n for n in tag_names if n.strip().lower() not in explicit]

        found: dict[str, str] = {}
        if need_lookup:
            found = self.find_tags(need_lookup)
            missing = [n for n in need_lookup if n not in found]
            if missing:
                raise MediiiaError(
                    "Не найдены теги: "
                    + ", ".join(missing)
                    + ". Впишите их id в config.json → default_tag_ids."
                )

        return [explicit.get(n.strip().lower()) or found[n] for n in tag_names]

    def create_project(self) -> dict[str, Any]:
        account_id = self.resolve_account_id()
        body = {
            "authorId": account_id,
            "appService": "dezign",
            "appContext": "mediiia",
        }
        r = self.http.post(f"{GEO}/api/project/Add", json=body)
        data = self._json(r)
        if not isinstance(data, dict) or not data.get("projectId"):
            # иногда API возвращает просто id строкой
            if isinstance(data, str) and data:
                return {"projectId": data, "longreadId": data}
            raise MediiiaError(f"Неожиданный ответ project/Add: {data!r}")
        return data

    def get_project(self, project_id: str) -> dict[str, Any]:
        r = self.http.get(f"{GEO}/api/project/Get", params={"idProject": project_id})
        data = self._json(r)
        if not isinstance(data, dict):
            raise MediiiaError("project/Get не вернул объект")
        return data

    def update_project_meta(
        self,
        project: dict[str, Any],
        *,
        title: str,
        tag_ids: list[str],
        coauthor_ids: list[str] | None = None,
        visibility_public: bool = True,
    ) -> dict[str, Any]:
        payload = dict(project)
        payload["title"] = [{"lang": "ru", "name": title}, {"lang": "en", "name": title}]
        payload["tagsID"] = tag_ids
        if coauthor_ids is not None:
            payload["coAuthorIds"] = coauthor_ids
        # status 0 = draft-ish; не публикуем
        if "status" in payload and payload["status"] not in (0, None):
            # если уже что-то выставлено сайтом — не форсим publish
            pass
        # protectedStatus: 0 открытый, иное по ссылке — эвристика из UI
        if not visibility_public:
            payload["isProtected"] = True
            payload["protectedStatus"] = 1
        else:
            payload["isProtected"] = False
            payload["protectedStatus"] = 0

        r = self.http.post(f"{GEO}/api/project/Update", json=payload)
        return self._json(r) or payload

    def add_text_block(
        self,
        *,
        longread_id: str,
        user_id: str,
        position: int,
        style: str,
        text: str,
        project_id: str,
        color: str | None = None,
        title: str | None = None,
        quote_author: str = "",
    ) -> dict[str, Any]:
        if style in {"colored", "quote"}:
            color = color or "#ffffff"
        else:
            color = color or "white"

        additional_info = [
            {"name": "projectId", "value": project_id},
            {"name": "tileViewType", "value": "two_row"},
            {"name": "tagsCheckboxVisible", "value": "false"},
        ]
        if style == "quote":
            additional_info.extend(
                [
                    {"name": "tagsIDs", "value": "[]"},
                    {"name": "isOstbay", "value": "false"},
                    {"name": "ostbayTheme", "value": "white"},
                    {
                        "name": "audioDownloadAllowedFor",
                        "value": '{"onlyRegisteredUsers":false}',
                    },
                    {
                        "name": "captionPosition",
                        "value": '{"top":{"visible":false,"text":""},'
                        '"bottom":{"visible":false,"text":""}}',
                    },
                    {
                        "name": "quoteData",
                        "value": json.dumps(
                            {
                                "author": quote_author,
                                "sourceText": "",
                                "sourceLink": "",
                                "marks": "type2",
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                    {"name": "cardsInfo", "value": "[]"},
                ]
            )

        body = {
            "additionalInfo": additional_info,
            "internalId": {},
            "postId": "string",
            "userId": user_id,
            "longreadId": str(longread_id),
            "position": position,
            "style": style,
            "isFirstLetter": False,
            "title": title or text,
            "text": text,
            "titlePosition": "inside",
            "color": color,
            "isHidden": True,
            "isDeleted": True,
            "attachments": [],
            "projectIds": [project_id],
            "dateCreate": "2020-10-28T11:15:50.034Z",
            "dateLastChange": "2020-10-28T11:15:50.034Z",
            "like": 0,
            "anchorText": "",
            "buttons": [],
            "caption": "",
            "cardIds": [],
            "linkText": "",
        }
        r = self.http.post(f"{LONGREADS}/api/post/Add", json=body)
        return self._json(r)

    def touch_longread(self, longread_id: str) -> Any:
        r = self.http.post(f"{LONGREADS}/api/Longread/Update?", json={"longreadId": longread_id})
        # ответ может быть пустым / 200
        if r.status_code >= 400:
            # не критично для черновика
            return None
        try:
            return r.json()
        except Exception:
            return r.text

    def create_draft_from_article(
        self,
        article: Article,
        *,
        tag_names: list[str],
        coauthor_ids: list[str] | None = None,
        open_browser: bool = True,
        browser: str = "chrome",
        tag_ids_map: dict[str, str] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> PublishResult:
        account_id = self.resolve_account_id()
        tag_ids = self.resolve_tag_ids(tag_names, tag_ids_map)

        created = self.create_project()
        project_id = str(created.get("projectId") or created.get("id"))
        project = self.get_project(project_id)
        longread_id = str(project.get("longreadId") or project_id)

        self.update_project_meta(
            project,
            title=article.title,
            tag_ids=tag_ids,
            coauthor_ids=coauthor_ids or [],
        )

        created_n = 0
        total = len(article.blocks)
        for i, block in enumerate(article.blocks):
            self.add_text_block(
                longread_id=longread_id,
                user_id=account_id,
                position=i,
                style=block.style,
                text=block.text,
                project_id=project_id,
                color=block.color or None,
                title=block.title or None,
                quote_author=block.quote_author,
            )
            created_n += 1
            if on_progress:
                on_progress(created_n, total)

        try:
            self.touch_longread(longread_id)
        except Exception:
            pass

        # URL редактора
        edit_url = f"https://mediiia.com/edit/{project_id}"
        if open_browser:
            open_in_browser(edit_url, browser)

        return PublishResult(
            project_id=project_id,
            title=article.title,
            edit_url=edit_url,
            blocks_created=created_n,
            tag_ids=tag_ids,
        )


def slugify_title(title: str) -> str:
    # только для отображения; Mediiia сама строит friendly URL
    s = re.sub(r"\s+", "-", title.strip().lower())
    return quote(s[:60])
