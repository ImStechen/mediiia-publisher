"""Прогон публикации с подменённым API: проверяем прогресс и полосу результата."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.gui as gui  # noqa: E402
from src.mediiia_api import PublishResult  # noqa: E402

SESSION = {"access_token": "x", "email": "editor@example.com", "account_id": "acc"}
seen: list[tuple[int, int]] = []


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def create_draft_from_article(self, article, **kwargs):
        callback = kwargs.get("on_progress")
        total = len(article.blocks)
        for index in range(total):
            if callback:
                callback(index + 1, total)
        assert kwargs["open_browser"] in (True, False)
        assert isinstance(kwargs["tag_names"], list)
        return PublishResult(
            project_id="fake123",
            edit_url="https://mediiia.com/editor/fake123",
            blocks_created=total,
            title=article.title,
            tag_ids=[],
        )


gui.MediiiaClient = FakeClient
gui.can_resume = lambda *a, **k: SESSION
gui.ensure_session = lambda *a, **k: SESSION

app = gui.App(initial_file=Path("9 сентября.docx"), initial_title="Проверка")
app.update()
time.sleep(0.6)
app.update()

app.record_entry.insert(0, "https://vkvideo.ru/video-1_1")
app.video_box.insert("1.0", '<iframe src="https://vkvideo.ru/video_ext.php?oid=-1&id=1"></iframe>')
app.refresh_preview()
app.refresh_readiness()
app.update()

print("готовность:", app.readiness())
print("кнопка до:", app.publish_btn.cget("state"), "|", app.publish_btn.cget("text"))

app.on_publish()
for _ in range(60):
    app.update()
    time.sleep(0.1)
    if not app._busy:
        break

print("статус:", app.status_kind, "|", app.status_message)
print("прогресс скрыт:", not app.progress.winfo_ismapped())
print("кнопка после:", app.publish_btn.cget("state"), "|", app.publish_btn.cget("text"))
texts: list[str] = []
for child in app.status_area.winfo_children():
    if "text" in child.keys():
        texts.append(str(child.cget("text")))
    for sub in child.winfo_children():
        if "text" in sub.keys():
            texts.append(str(sub.cget("text")))
print("в футере:", [text for text in texts if text])

if "--hold" in sys.argv:
    for _ in range(150):
        app.update()
        time.sleep(0.1)
app.destroy()
