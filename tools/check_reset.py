"""Проверяем сброс: перечень в подтверждении, отказ и подтверждение."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.gui as gui  # noqa: E402

asked: list[str] = []
answer = {"value": False}


def fake_askyesno(title, message, **kwargs):
    asked.append(message)
    return answer["value"]


gui.messagebox.askyesno = fake_askyesno

app = gui.App(initial_file=Path("9 сентября.docx"), initial_title="Проверка")
app.update()
time.sleep(0.6)
app.update()
app.record_entry.insert(0, "https://vkvideo.ru/video-1_1")
app.video_box.insert("1.0", "<iframe src=\"https://vkvideo.ru/x\"></iframe>")
app.extra_editor.set_markup("Ещё будет лекция 20 октября")
app.refresh_preview()
app.refresh_readiness()
app.update()

print("кнопка сброса:", app.reset_btn.cget("state"))
print("будет стёрто:", app.filled_items())

answer["value"] = False
app.reset_all()
app.update()
print("после отказа — статья на месте:", app.article is not None,
      "| заголовок:", bool(app.title_entry.get().strip()),
      "| статус:", app.status_message)

answer["value"] = True
app.reset_all()
app.update()
time.sleep(0.4)
app.update()
print("после сброса — статья:", app.article,
      "| заголовок:", repr(app.title_entry.get()),
      "| дата:", repr(app.date_entry.get()),
      "| ссылка:", repr(app.record_entry.get()),
      "| код видео:", repr(app.video_box.get("1.0", "end").strip()),
      "| доп:", repr(app.extra_editor.get_markup().strip()))
print("время вернулось:", app.time_from.get(), "-", app.time_to.get())
print("верхняя плашка:", app.top_banner_choice.get())
print("нижняя плашка:", app.bottom_banner_choice.get())
print("кнопка сброса теперь:", app.reset_btn.cget("state"))
print("кнопка публикации:", app.publish_btn.cget("state"))
print("статус:", app.status_message)
print()
print("текст подтверждения:")
print(asked[0])
app.destroy()
