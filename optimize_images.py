#!/usr/bin/env python3
"""
optimize_images.py — prepare photographs for ngatia.photo

Reads every JPEG in ./originals/ and writes two versions:

    images/<name>.jpg        2000px long edge, quality 82   (lightbox, hero)
    images/thumb/<name>.jpg   700px long edge, quality 80   (contact sheet)

It optionally watermarks them, and strips EXIF — including GPS, worth
removing before putting street frames online, since camera and phone
metadata can pin down exactly where you were standing.

Needs only Pillow, which Anaconda already includes.

    mkdir originals
    mv *.jpg originals/
    python optimize_images.py
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    sys.exit(
        "Pillow isn't available.\n"
        "Install it with:  conda install -y pillow\n"
        "             or:  pip install pillow"
    )

SRC = Path("originals")
OUT = Path("images")
THUMB = Path("images/thumb")

FULL_PX, FULL_Q = 2000, 82
THUMB_PX, THUMB_Q = 700, 80

# ======================= WATERMARK SETTINGS =========================
# Set WATERMARK = False to turn it off and just resize.

WATERMARK = True

# The text itself. "ngatia.photo" doubles as a watermark and as a way for
# anyone who reposts the picture to find you.
WM_TEXT = "ngatia.photo"

# Corner: "southeast", "southwest", "northeast", "northwest", "south".
WM_POSITION = "southeast"

# 0 = invisible, 1 = solid. 0.45–0.6 reads without fighting the picture.
WM_OPACITY = 0.55

# Text size as a fraction of the long edge. 0.018 is about 36px on a
# 2000px file — small, but legible on a phone.
WM_SCALE = 0.018

# Distance from the edge, also as a fraction of the long edge.
WM_INSET = 0.016

# Watermark the small grid thumbnails too? They're only 700px wide, so
# they're not much use to anyone lifting them, and a mark at that size is
# mostly clutter. Off by default.
WM_ON_THUMBS = False
# ====================================================================

FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def stamp(img):
    """Draw the watermark twice — translucent black offset by a pixel,
    then white on top. Keeps it readable over a bright sky and over a
    dark doorway without needing a box behind it."""
    long_edge = max(img.size)
    size = max(9, int(long_edge * WM_SCALE))
    inset = max(6, int(long_edge * WM_INSET))
    font = load_font(size)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    left, top, right, bottom = draw.textbbox((0, 0), WM_TEXT, font=font)
    tw, th = right - left, bottom - top

    if "east" in WM_POSITION:
        x = img.width - tw - inset - left
    elif "west" in WM_POSITION:
        x = inset - left
    else:
        x = (img.width - tw) // 2 - left

    if WM_POSITION.startswith("north"):
        y = inset - top
    else:
        y = img.height - th - inset - top

    fg = int(255 * WM_OPACITY)
    bg = int(255 * WM_OPACITY * 0.6)
    draw.text((x - 1, y - 1), WM_TEXT, font=font, fill=(0, 0, 0, bg))
    draw.text((x, y), WM_TEXT, font=font, fill=(255, 255, 255, fg))

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def render(src_img, box, quality, dest, watermark):
    img = src_img.copy()
    img.thumbnail((box, box), Image.LANCZOS)
    if watermark:
        img = stamp(img)
    img.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
    return dest.stat().st_size


def main():
    if not SRC.is_dir():
        sys.exit(
            f"No ./{SRC} directory found.\n"
            "Create it and move your camera files in first:\n"
            f"    mkdir {SRC} && mv *.jpg {SRC}/"
        )

    files = sorted(
        p for p in SRC.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg"} and not p.name.startswith(".")
    )
    if not files:
        sys.exit(f"No JPEGs in ./{SRC} — nothing to do.")

    OUT.mkdir(parents=True, exist_ok=True)
    THUMB.mkdir(parents=True, exist_ok=True)

    print(f"Processing {len(files)} photographs…")
    if WATERMARK:
        print(f'Watermark: "{WM_TEXT}" ({WM_POSITION})')
    print()

    before = after = 0

    for path in files:
        try:
            with Image.open(path) as raw:
                # honour the camera's rotation flag, then drop all EXIF
                src_img = ImageOps.exif_transpose(raw).convert("RGB")
        except Exception as exc:
            print(f"  {path.name:<24} skipped — {exc}")
            continue

        stem = path.stem
        a = render(src_img, FULL_PX, FULL_Q, OUT / f"{stem}.jpg", WATERMARK)
        t = render(src_img, THUMB_PX, THUMB_Q, THUMB / f"{stem}.jpg",
                   WATERMARK and WM_ON_THUMBS)

        b = path.stat().st_size
        before += b
        after += a + t
        print(f"  {stem:<24} {b//1024:>5} KB  →  {a//1024:>4} KB + {t//1024:>3} KB")

    print()
    print(f"Total: {before/1024/1024:.1f} MB  →  {after/1024/1024:.1f} MB")
    print()
    print(f"Originals are untouched in ./{SRC} — keep that folder out of git.")
    print("Next:  git add images && git commit -m 'Optimised photographs' && git push")


if __name__ == "__main__":
    main()
