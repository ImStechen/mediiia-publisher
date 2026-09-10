"""Ищем рамки полей на скриншоте: где линия есть, а где обрывается."""

from __future__ import annotations

import sys

from PIL import Image

BORDER = (216, 219, 224)
CARD_BORDER = (227, 229, 233)
TOLERANCE = 6


def close(pixel, target) -> bool:
    return all(abs(a - b) <= TOLERANCE for a, b in zip(pixel, target))


def horizontal_runs(im, target, min_length: int) -> list[tuple[int, int, int]]:
    width, height = im.size
    found = []
    for y in range(height):
        start = None
        for x in range(width):
            if close(im.getpixel((x, y)), target):
                if start is None:
                    start = x
            else:
                if start is not None and x - start >= min_length:
                    found.append((y, start, x - 1))
                start = None
        if start is not None and width - start >= min_length:
            found.append((y, start, width - 1))
    return found


def vertical_run_length(im, x: int, y_from: int, target) -> int:
    length = 0
    _, height = im.size
    y = y_from
    while y < height and close(im.getpixel((x, y)), target):
        length += 1
        y += 1
    return length


def main(path: str) -> None:
    im = Image.open(path).convert("RGB")
    runs = horizontal_runs(im, BORDER, 200)
    print(f"горизонтальных линий рамки контролов: {len(runs)}")
    for y, x_from, x_to in runs:
        left = vertical_run_length(im, x_from, y, BORDER)
        right = vertical_run_length(im, x_to, y, BORDER)
        print(f"  y={y} x={x_from}..{x_to} ширина={x_to - x_from + 1} лево={left} право={right}")

    print()
    card_runs = horizontal_runs(im, CARD_BORDER, 200)
    print(f"горизонтальных линий рамки карточек: {len(card_runs)}")
    for y, x_from, x_to in card_runs:
        print(f"  y={y} x={x_from}..{x_to} ширина={x_to - x_from + 1}")


if __name__ == "__main__":
    main(sys.argv[1])
