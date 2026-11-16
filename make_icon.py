"""Draws the Workshop icon: a gold toolbox on a dark tile with a gold edge.
Every size is drawn on its own with all straight edges snapped to whole pixels,
so it stays razor sharp at taskbar sizes (16-48 px)."""
from PIL import Image, ImageDraw

GOLD, LIGHT, DARK = "#d4a84b", "#f3dc9a", "#1b1d21"
Q = 8          # draw at 8x, then shrink: snapped edges stay crisp, only curves get smoothing


def draw(n: int) -> Image.Image:
    S = n * Q
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P = lambda *v: tuple(int(round(x)) * Q for x in v)          # whole pixels -> 8x canvas
    bw = max(1, round(n / 12))                                   # gold edge: 2 px at 24
    r = max(2, round(n * 0.2))
    d.rounded_rectangle(P(0, 0, n, n), radius=r * Q, fill=GOLD)
    d.rounded_rectangle(P(bw, bw, n - bw, n - bw), radius=max(1, r - bw) * Q, fill=DARK)
    pad = max(1, round(n / 14))
    m = bw + pad
    W = n - 2 * m                                                # toolbox width
    H = round(W * 0.86)
    x0, y0 = m, m + (n - 2 * m - H) // 2 + (1 if n <= 20 else 0)
    t = max(1, round(n / 14))                                    # handle thickness
    hw, hh = round(W * 0.44), round(H * 0.34)
    hx = x0 + (W - hw) // 2
    body_top = y0 + hh - t
    rb = max(1, round(n * 0.06))
    # handle
    d.rounded_rectangle(P(hx, y0, hx + hw, y0 + hh + t), radius=max(1, round(hw * 0.3)) * Q, fill=GOLD)
    d.rectangle(P(hx + t, y0 + t, hx + hw - t, y0 + hh + t), fill=DARK)
    # body
    d.rounded_rectangle(P(x0, body_top, x0 + W, y0 + H), radius=rb * Q, fill=GOLD)
    bh = y0 + H - body_top
    lid = body_top + round(bh * 0.34)
    lt = max(1, round(n / 24))
    d.rectangle(P(x0, lid, x0 + W, lid + lt), fill=DARK)
    # latch
    lw_, lh = max(2, round(W * 0.2)), max(2, round(bh * 0.36))
    lx, ly = x0 + (W - lw_) // 2, lid + lt // 2 - lh // 2
    d.rectangle(P(lx, ly, lx + lw_, ly + lh), fill=LIGHT)
    if n >= 32:
        k = max(1, round(lw_ * 0.3))
        d.rectangle(P(lx + k, ly + k, lx + lw_ - k, ly + lh - k), fill=GOLD)
    return im.resize((n, n), Image.LANCZOS)


sizes = [16, 20, 24, 30, 32, 36, 40, 48, 64, 128, 256]
imgs = {s: draw(s) for s in sizes}
imgs[256].save("assets/icon.png")
for s in (16, 32, 48):
    imgs[s].save(f"assets/icon{s}.png")
imgs[256].save("assets/icon.ico", sizes=[(s, s) for s in sizes],
               append_images=[imgs[s] for s in sizes if s != 256])
