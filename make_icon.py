"""Draws the toolbox icon (assets/icon.png and assets/icon.ico)."""
from PIL import Image, ImageDraw

S = 1024
def draw(size=S):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=220, fill="#1b1d21")
    gold, light, dark = "#c9a24a", "#f0d58f", "#1b1d21"
    # handle
    d.rounded_rectangle((372, 228, 652, 400), radius=60, outline=gold, width=58)
    # body
    d.rounded_rectangle((170, 360, 854, 800), radius=70, fill=gold)
    # lid line
    d.rectangle((170, 500, 854, 540), fill=dark)
    # latch
    d.rounded_rectangle((454, 470, 570, 590), radius=24, fill=light)
    d.rounded_rectangle((484, 500, 540, 560), radius=10, fill=gold)
    return im

im = draw()
im.resize((256, 256), Image.LANCZOS).save("assets/icon.png")
im.save("assets/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
