"""Draws the toolbox icon (assets/icon.png, assets/icon.ico).
Each size is drawn separately (at 8x, then shrunk) so small sizes stay crisp.
Taskbar sizes (48 px and under) leave out the dark tile behind the toolbox so the
toolbox fills the space like other taskbar icons."""
from PIL import Image, ImageDraw

GOLD, LIGHT, DARK, BG = "#d4a84b", "#f3dc9a", "#1b1d21", "#1b1d21"


def toolbox(d, k, ox, oy, small, outline):
    def R(x0, y0, x1, y1):
        return (ox + x0 * k, oy + y0 * k, ox + x1 * k, oy + y1 * k)
    if outline:      # thin dark edge so it reads on light and dark taskbars
        d.rounded_rectangle(R(-6, 66, 262, 238), radius=int(28 * k), fill=DARK)
        d.rounded_rectangle(R(66, -6, 190, 100), radius=int(34 * k), fill=DARK)
    d.rounded_rectangle(R(78, 6, 178, 96), radius=int(26 * k), outline=GOLD, width=int((30 if small else 22) * k))
    d.rounded_rectangle(R(4, 78, 252, 228), radius=int(24 * k), fill=GOLD)
    d.rectangle(R(4, 128, 252, 146 if small else 140), fill=DARK)
    d.rounded_rectangle(R(100, 106, 156, 166), radius=int(9 * k), fill=LIGHT)
    if not small:
        d.rounded_rectangle(R(114, 120, 142, 152), radius=int(5 * k), fill=GOLD)


def draw(size: int, plate: bool) -> Image.Image:
    S = size * 8
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if plate:
        d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(52 * S / 256), fill=BG)
        k = S / 256 * 0.84
        toolbox(d, k, S * 0.08, S * 0.11, size <= 24, False)
    else:
        k = S * 0.98 / 268                       # artwork spans -6..262 wide, -6..238 tall
        toolbox(d, k, (S - 268 * k) / 2 + 6 * k, (S - 244 * k) / 2 + 6 * k, size <= 24, True)
    return im.resize((size, size), Image.LANCZOS)


sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
imgs = {s: draw(s, plate=s > 48) for s in sizes}
imgs[256].save("assets/icon.png")
for s in (16, 32, 48):
    imgs[s].save(f"assets/icon{s}.png")
imgs[256].save("assets/icon.ico", sizes=[(s, s) for s in sizes],
               append_images=[imgs[s] for s in sizes if s != 256])
