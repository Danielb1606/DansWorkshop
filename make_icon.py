"""Draws the toolbox icon (assets/icon.png, assets/icon.ico).
Each size is drawn separately (at 8x, then shrunk) so small sizes stay crisp."""
from PIL import Image, ImageDraw

GOLD, LIGHT, DARK, BG = "#d4a84b", "#f3dc9a", "#1b1d21", "#1b1d21"


def draw(size: int) -> Image.Image:
    S = size * 8
    k = S / 256
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    small = size <= 24
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(52 * k), fill=BG)
    # handle (thicker when tiny)
    d.rounded_rectangle((int(84 * k), int(30 * k), int(172 * k), int(96 * k)), radius=int(22 * k),
                        outline=GOLD, width=int((26 if small else 20) * k))
    # body fills most of the square
    d.rounded_rectangle((int(22 * k), int(78 * k), int(234 * k), int(226 * k)), radius=int(22 * k), fill=GOLD)
    # lid line
    d.rectangle((int(22 * k), int(124 * k), int(234 * k), int((140 if small else 136) * k)), fill=DARK)
    # latch
    d.rounded_rectangle((int(104 * k), int(108 * k), int(152 * k), int(158 * k)), radius=int(8 * k), fill=LIGHT)
    if not small:
        d.rounded_rectangle((int(116 * k), int(120 * k), int(140 * k), int(146 * k)), radius=int(4 * k), fill=GOLD)
    return im.resize((size, size), Image.LANCZOS)


sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
imgs = {s: draw(s) for s in sizes}
imgs[256].save("assets/icon.png")
for s in (16, 32, 48):
    imgs[s].save(f"assets/icon{s}.png")
imgs[256].save("assets/icon.ico", sizes=[(s, s) for s in sizes],
               append_images=[imgs[s] for s in sizes if s != 256])
