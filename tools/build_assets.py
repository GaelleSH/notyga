# -*- coding: utf-8 -*-
"""Derive the site's image assets from the original source files.

Optional: the results are already committed under assets/img/. Re-run this only
if you want to change a crop, a size or the logo colour.

    pip install Pillow
    python tools/build_assets.py

The supplied logo was a flat JPEG of dark-green ink on white. Alpha is taken
from the inverted luminance so antialiased edges survive, and the RGB is then
flattened to one colour, which lets a green and a reversed white variant come
out of the same mask.
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "source")
OUT = os.path.join(ROOT, "assets", "img")

GREEN = (0, 100, 1)   # sampled from the logo file
WHITE = (255, 255, 255)

os.makedirs(OUT, exist_ok=True)

logo = Image.open(os.path.join(SRC, "logo-notyga-v2-3.jpg")).convert("L")
w, h = logo.size

alpha = logo.point(lambda v: 255 - v)
# Clear the faint JPEG haze in the paper, then lift the ink back to full.
alpha = alpha.point(lambda v: 0 if v < 26 else min(255, int((v - 26) * 255 / 190)))


def tinted(mask, rgb, box=None):
    if box:
        mask = mask.crop(box)
    img = Image.new("RGBA", mask.size, rgb + (0,))
    img.putalpha(mask)
    return img.crop(img.getbbox())


def save(img, name, width):
    img = img.resize((width, max(1, round(img.height * width / img.width))),
                     Image.LANCZOS)
    img.save(os.path.join(OUT, name), optimize=True)
    print("  %-26s %dx%d" % (name, img.width, img.height))


# Vertical bands, measured from the ink-density profile of the source file.
BANDS = {
    "mark":     ((0, 0, w, 430), 1200),    # the arrow + data-dots symbol
    "wordmark": ((0, 440, w, 900), 1200),  # "NOTYGA"
    "full":     ((0, 0, w, h), 1400),      # complete stacked lockup
}

print("logo variants:")
for name, (box, width) in BANDS.items():
    for suffix, rgb in (("", GREEN), ("-white", WHITE)):
        save(tinted(alpha, rgb, box), "logo-%s%s.png" % (name, suffix), width)

# Founder portrait: centre-crop to 4:5, then downscale for the web.
print("portrait:")
p = Image.open(os.path.join(SRC, "g-saint-hilary.jpg")).convert("RGB")
pw, ph = p.size
target = 4 / 5
if pw / ph > target:
    nw = round(ph * target)
    p = p.crop(((pw - nw) // 2, 0, (pw - nw) // 2 + nw, ph))
else:
    nh = round(pw / target)
    p = p.crop((0, 0, pw, nh))
p = p.resize((900, round(900 / target)), Image.LANCZOS)
p.save(os.path.join(OUT, "founder.jpg"), quality=86, optimize=True, progressive=True)
print("  %-26s %dx%d" % ("founder.jpg", p.width, p.height))

print("favicons:")
fav = Image.open(os.path.join(SRC, "cropped-favicon-96x96-1.png")).convert("RGBA")
for size, name in ((512, "favicon-512.png"), (180, "apple-touch-icon.png"),
                   (32, "favicon-32.png")):
    fav.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, name), optimize=True)
    print("  %-26s %dx%d" % (name, size, size))
