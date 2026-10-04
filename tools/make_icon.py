from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BG, INK = (0xE6, 0xEC, 0xF2), (0x2E, 0x3A, 0x4B)
FONT = "/System/Library/Fonts/SFNS.ttf"
WORD, TRACKING = "COACH", 0.4


def icon(size: int = 1024) -> Image.Image:
    box = (100, 100, 924, 924)
    shadow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(shadow).rounded_rectangle((box[0], box[1] + 18, box[2], box[3] + 18), 185, fill=90)
    image = Image.new("RGBA", (size, size), (*INK, 0))
    image.putalpha(shadow.filter(ImageFilter.GaussianBlur(28)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, 185, fill=(*BG, 255))
    font = ImageFont.truetype(FONT, 118)
    font.set_variation_by_axes([100, 96, 400, 600])
    gap = font.size * TRACKING
    widths = [font.getlength(c) for c in WORD]
    x = (size - sum(widths) - gap * (len(WORD) - 1)) / 2
    top, bottom = font.getbbox(WORD)[1], font.getbbox(WORD)[3]
    for char, width in zip(WORD, widths):
        draw.text((x, size / 2 - (top + bottom) / 2), char, font=font, fill=(*INK, 255))
        x += width + gap
    return image


if __name__ == "__main__":
    image = icon()
    image.save(ROOT / "tools/icon.png")
    image.resize((256, 256), Image.LANCZOS).save(ROOT / "web/icon.png")
