"""Ссылка и код видео необязательны: кнопка должна работать и без них."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.gui as gui  # noqa: E402

SESSION = {"access_token": "x", "email": "editor@example.com", "account_id": "acc"}
gui.can_resume = lambda *a, **k: SESSION


def footer_texts(app: gui.App) -> list[str]:
    texts: list[str] = []

    def walk(widget) -> None:
        for child in widget.winfo_children():
            if "text" in child.keys() and str(child.cget("text")).strip():
                texts.append(str(child.cget("text")))
            walk(child)

    walk(app.status_area)
    return texts


app = gui.App(initial_file=Path("9 сентября.docx"), initial_title="Проверка")
app.update()
time.sleep(0.6)
app.update()

print("обязательное:", app.readiness())
print("необязательное:", app.extras())
print("кнопка:", app.publish_btn.cget("state"), "|", app.publish_btn.cget("text"))
print("в футере:", footer_texts(app))

app.record_entry.insert(0, "https://vkvideo.ru/video-1_1")
app.refresh_readiness()
app.update()
print("\nсо ссылкой, без видео:", footer_texts(app))

app.video_box.insert("1.0", '<iframe src="https://vkvideo.ru/video_ext.php"></iframe>')
app.refresh_readiness()
app.update()
print("со ссылкой и видео:   ", footer_texts(app))

app.title_entry.delete(0, "end")
app.refresh_readiness()
app.update()
print("\nбез заголовка:", footer_texts(app))
print("кнопка:", app.publish_btn.cget("state"), "|", app.publish_btn.cget("text"))

if "--hold" in sys.argv:
    app.title_entry.insert(0, "Проверка")
    app.refresh_readiness()
    app.mainloop()
else:
    app.destroy()
