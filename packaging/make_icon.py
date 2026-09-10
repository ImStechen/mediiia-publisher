"""Рисует ICO без бинарного исходника в репозитории."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "app.ico"
OUTPUT.parent.mkdir(exist_ok=True)

size = 256
image = Image.new("RGBA", (size, size), "#182D66")
draw = ImageDraw.Draw(image)
draw.rectangle((0, 0, 24, size), fill="#00AA01")
draw.rectangle((45, 45, 216, 216), fill="#00AA01")

try:
    font = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 112)
except OSError:
    font = ImageFont.load_default()

text = "M"
box = draw.textbbox((0, 0), text, font=font)
x = 45 + (171 - (box[2] - box[0])) // 2
y = 45 + (171 - (box[3] - box[1])) // 2 - box[1]
draw.text((x, y), text, fill="#000000", font=font)

image.save(OUTPUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(OUTPUT)
