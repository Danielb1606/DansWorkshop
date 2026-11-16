"""Dan's Workshop - the window (graphite and gold)."""

from __future__ import annotations

import base64
import io
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Dict, List, Optional

from . import core
from .core import AppDef

# ----------------------------------------------------------------------------- theme

BG = "#16181c"
RAIL = "#0f1114"
LINE = "#22252a"
CARD = "#1f2227"
CARD_LINE = "#2c3036"
RAISED = "#262a30"
TEXT = "#e8e6e1"
SUB = "#b8b5ad"
MUTED = "#7f838b"
GREEN = "#4cc38a"
RED = "#d9776b"
ACCENT = "#c9a24a"
ACCENT_HI = "#dcb76a"
ACCENT_BG = "#231f15"
ACCENT_LINE = "#4a3d1e"

FONT = ("Segoe UI", 10)
SMALL = ("Segoe UI", 9)
BOLD = ("Segoe UI Semibold", 10)
TITLE = ("Segoe UI Semibold", 18)
H2 = ("Segoe UI Semibold", 12)

GAP = 14
ART_RATIO = 0.56

ICONS = {      # Segoe Fluent / MDL2 glyph, fallback
    "library": ("", "▦"), "updates": ("", "↓"), "activity": ("", "◷"),
    "settings": ("", "⚙"), "refresh": ("", "⟳"), "more": ("", "⋯"),
    "search": ("", "⌕"), "folder": ("", "▭"), "shield": ("", "✓"),
    "plus": ("", "+"), "close": ("", "✕"), "info": ("", "i"),
}
_icon_font: Optional[str] = None


def set_accent(name: str) -> None:
    global ACCENT, ACCENT_HI, ACCENT_BG, ACCENT_LINE
    ACCENT, ACCENT_HI = core.ACCENTS.get(name, core.ACCENTS["gold"])
    ACCENT_BG = _mix(ACCENT, BG, 0.12)
    ACCENT_LINE = _mix(ACCENT, BG, 0.35)


def _mix(a: str, b: str, t: float) -> str:
    ar, ag, ab = (int(a[i:i + 2], 16) for i in (1, 3, 5))
    br, bg, bb = (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (round(br + (ar - br) * t), round(bg + (ag - bg) * t), round(bb + (ab - bb) * t))


def icon(name: str, size: int = 14):
    glyph, fallback = ICONS[name]
    if _icon_font:
        return glyph, (_icon_font, size)
    return fallback, ("Segoe UI", size)


def photo_from_pil(img) -> tk.PhotoImage:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return tk.PhotoImage(data=base64.b64encode(buf.getvalue()))


# ----------------------------------------------------------------------------- small widgets

class Btn(tk.Label):
    """Flat button. kinds: primary (accent fill), outline (accent line), plain, ghost."""

    def __init__(self, parent, text, command, kind="plain", font=BOLD, padx=14, pady=6, **kw):
        super().__init__(parent, text=text, font=font, padx=padx, pady=pady, cursor="hand2", **kw)
        self.command, self.kind = command, kind
        self.enabled = True
        self._paint(False)
        self.bind("<Enter>", lambda e: self._paint(True))
        self.bind("<Leave>", lambda e: self._paint(False))
        self.bind("<Button-1>", lambda e: self.enabled and self.command and self.command())

    def _paint(self, hover):
        k = self.kind
        if not self.enabled:
            self.configure(bg=RAISED, fg=MUTED, highlightthickness=0)
        elif k == "primary":
            self.configure(bg=ACCENT_HI if hover else ACCENT, fg=BG, highlightthickness=0)
        elif k == "outline":
            self.configure(bg=ACCENT_BG if hover else self.master["bg"], fg=ACCENT,
                           highlightthickness=1, highlightbackground=ACCENT, highlightcolor=ACCENT)
        elif k == "ghost":
            self.configure(bg=self.master["bg"], fg=TEXT if hover else SUB, highlightthickness=0)
        else:
            self.configure(bg="#30343b" if hover else RAISED, fg=TEXT, highlightthickness=0)

    def set(self, text=None, kind=None, enabled=None, command=None):
        if text is not None:
            self.configure(text=text)
        if kind is not None:
            self.kind = kind
        if enabled is not None:
            self.enabled = enabled
        if command is not None:
            self.command = command
        self._paint(False)


class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Dark.Vertical.TScrollbar")
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self._sync())
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(self.win, width=e.width), self._sync()))
        self.bind_all("<MouseWheel>", self._wheel, add="+")
        self.bind_all("<Button-4>", lambda e: self._wheel(e, -120), add="+")
        self.bind_all("<Button-5>", lambda e: self._wheel(e, 120), add="+")

    def _sync(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_scroll(self, a, b):
        self.bar.set(a, b)
        if float(a) <= 0 and float(b) >= 1:
            self.bar.pack_forget()
        elif not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y")

    def _wheel(self, e, delta=None):
        if not self.winfo_ismapped():
            return
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None and w is not self:
            w = w.master
        if w is self:
            d = delta if delta is not None else -e.delta
            self.canvas.yview_scroll(int(d / 120) or (1 if d > 0 else -1), "units")


class Banner(tk.Frame):
    def __init__(self, parent, text, actions=(), tone="accent", closable=True, on_close=None):
        bg = ACCENT_BG if tone == "accent" else ("#16261e" if tone == "good" else "#2a1a18")
        line = ACCENT_LINE if tone == "accent" else ("#24563c" if tone == "good" else "#5a2e28")
        fg = ACCENT if tone == "accent" else (GREEN if tone == "good" else RED)
        super().__init__(parent, bg=bg, highlightthickness=1, highlightbackground=line)
        g, f = icon("info", 12)
        tk.Label(self, text=g, font=f, bg=bg, fg=fg).pack(side="left", padx=(12, 8), pady=9)
        self.msg = tk.Label(self, text=text, bg=bg, fg=TEXT, font=FONT, anchor="w", justify="left")
        self.msg.pack(side="left", fill="x", expand=True, pady=9)
        self.msg.bind("<Configure>", lambda e: self.msg.configure(wraplength=max(200, e.width - 10)))
        if closable:
            g, f = icon("close", 9)
            x = tk.Label(self, text=g, font=f, bg=bg, fg=MUTED, cursor="hand2")
            x.pack(side="right", padx=(6, 12))
            x.bind("<Button-1>", lambda e: (self.destroy(), on_close and on_close()))
        self.buttons = []
        for label, cmd in reversed(list(actions)):
            b = tk.Label(self, text=label, bg=bg, fg=fg, font=BOLD, cursor="hand2", padx=8)
            b.pack(side="right")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            self.buttons.append(b)

    def text(self, t):
        self.msg.configure(text=t)


# ----------------------------------------------------------------------------- card

class Card(tk.Frame):
    def __init__(self, parent, hub: "Hub", app: AppDef, width: int):
        super().__init__(parent, bg=CARD, highlightthickness=1, highlightbackground=CARD_LINE)
        self.hub, self.app, self.w = hub, app, width
        self.h = round(width * ART_RATIO)
        self.art = tk.Canvas(self, width=width, height=self.h, bg=app.colour, highlightthickness=0, bd=0, cursor="hand2")
        self.art.pack(fill="x")
        self.art.bind("<Button-1>", lambda e: hub.primary(app))
        body = tk.Frame(self, bg=CARD)
        body.pack(fill="x", padx=12, pady=(10, 12))
        top = tk.Frame(body, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=app.name, bg=CARD, fg=TEXT, font=BOLD, anchor="w").pack(side="left")
        g, f = icon("more", 12)
        more = tk.Label(top, text=g, font=f, bg=CARD, fg=MUTED, cursor="hand2", padx=4)
        more.pack(side="right")
        more.bind("<Button-1>", lambda e: hub.card_menu(app, e.x_root, e.y_root))
        self.bind("<Button-3>", lambda e: hub.card_menu(app, e.x_root, e.y_root))
        self.art.bind("<Button-3>", lambda e: hub.card_menu(app, e.x_root, e.y_root))
        self.meta = tk.Label(body, text="", bg=CARD, fg=MUTED, font=SMALL, anchor="w", justify="left",
                             wraplength=max(120, width - 28))
        self.meta.pack(fill="x", pady=(2, 10))
        self.btn = Btn(body, "Play", lambda: hub.primary(app), kind="primary", pady=6)
        self.btn.pack(fill="x")
        self._photo = None
        self.refresh()

    def draw_art(self):
        c = self.art
        c.delete("all")
        c.configure(bg=self.app.colour)
        st = core.app_state(self.hub.state, self.app.id)
        p = core.art_path(self.app)
        icon = None if st.get("custom_art") else self.hub.app_icon(self.app)
        if icon:
            img = self.hub.icon_image(self.app, icon, self.w, self.h)
        else:
            img = self.hub.art_image(self.app, p, self.w, self.h) if p else None
        if img is not None:
            self._photo = img
            c.create_image(0, 0, anchor="nw", image=img)
        else:
            initials = self.app.initials or "".join(w[0] for w in self.app.name.split()[:2]).upper()
            c.create_text(self.w // 2, self.h // 2 - 6, text=initials, fill=_mix("#ffffff", self.app.colour, 0.55),
                          font=("Segoe UI Semibold", max(18, self.w // 7)))
            hint = "Picture appears after first use" if self.app.installed and self.app.kind != "script" else ""
            c.create_text(self.w // 2, self.h - 16, text=hint, fill=_mix("#ffffff", self.app.colour, 0.4), font=SMALL)

    def _pill(self, text, dot):
        c = self.art
        f = tkfont.Font(font=SMALL)
        w = f.measure(text) + 26
        c.create_rectangle(10, 10, 10 + w, 32, fill="#16181c", outline="#2c3036")
        c.create_oval(18, 18, 24, 24, fill=dot, outline=dot)
        c.create_text(30, 21, text=text, anchor="w", fill=TEXT, font=SMALL)

    def refresh(self):
        a, hub = self.app, self.hub
        self.draw_art()
        st = core.app_state(hub.state, a.id)
        ver = st.get("version") or ""
        running = hub.is_running(a)
        upd = hub.update_for(a)
        bits = []
        if ver:
            bits.append(f"v{ver}")
        if not a.installed:
            bits.append("not installed on this PC" if a.external else "not in the Workshop yet")
        elif st.get("last_opened"):
            bits.append(f"{'last run' if a.kind == 'script' else 'opened'} {core.ago(st['last_opened'])}")
        else:
            bits.append(a.blurb or "not opened yet")
        self.meta.configure(text="  ·  ".join(bits))
        if running:
            self._pill("Running", GREEN)
        elif upd:
            self._pill(f"Update v{upd.version}", ACCENT)
        if not a.installed:
            self.btn.set("Install Obsidian" if a.id == "obsidian" else ("Bring it in" if a.import_from else "Install"),
                         "outline")
        elif running:
            self.btn.set("Show window", "plain")
        elif upd and a.kind not in ("custom", "external", "script"):
            self.btn.set(f"Update to v{upd.version}", "outline")
        else:
            self.btn.set(a.play_label, "primary")


class AddCard(tk.Frame):
    def __init__(self, parent, hub, width):
        super().__init__(parent, bg=BG)
        h = round(width * ART_RATIO) + 84
        c = tk.Canvas(self, width=width, height=h, bg=BG, highlightthickness=0, cursor="hand2")
        c.pack()
        c.create_rectangle(1, 1, width - 2, h - 2, outline="#3a3d44", dash=(4, 4))
        g, f = icon("plus", 18)
        c.create_text(width // 2, h // 2 - 12, text=g, font=f, fill=MUTED)
        c.create_text(width // 2, h // 2 + 14, text="Add an app", font=SMALL, fill=MUTED)
        c.bind("<Button-1>", lambda e: hub.add_app())


# ----------------------------------------------------------------------------- the hub

class Hub:
    def __init__(self, root: tk.Tk, startup_msg: str = ""):
        global _icon_font
        self.root = root
        self.settings = core.load_settings()
        set_accent(self.settings["accent"])
        fams = set(tkfont.families(root))
        _icon_font = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), None)
        self.state = core.load_state()
        self.checker = core.Checker()
        self.procs: Dict[str, List[int]] = {}
        self.running: Dict[str, bool] = {}
        self.started_at: Dict[str, float] = {}
        self.cards: Dict[str, Card] = {}
        self.art_cache: Dict[tuple, tk.PhotoImage] = {}
        self.banners: List[tk.Widget] = []
        self.messages: List[tuple] = []         # (text, tone) shown on the library
        self.page = "library"
        self.layout_key = None
        self.search = tk.StringVar()
        self.sort = self.state.get("sort", "recent")
        self.busy: Dict[str, str] = {}          # app id -> what's happening
        self.capture_seen: Dict[str, tuple] = {}
        self._icons: Dict[str, tuple] = {}
        if startup_msg:
            self.messages.append((startup_msg, "good"))

        root.title(core.APP_NAME)
        root.configure(bg=BG)
        root.minsize(760, 540)
        self._style()
        self.build()
        root.after(200, self.first_steps)
        root.after(1000, self.tick)
        threading.Thread(target=self.poll_loop, daemon=True).start()

    # ------------------------------------------------------------------ layout

    def _style(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Dark.Vertical.TScrollbar", background=RAISED, troughcolor=BG, bordercolor=BG,
                     arrowcolor=MUTED, lightcolor=RAISED, darkcolor=RAISED, gripcount=0)
        st.map("Dark.Vertical.TScrollbar", background=[("active", "#3a3d44")])

    def build(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.cards.clear()
        self.layout_key = None
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True)
        self.rail = tk.Frame(outer, bg=RAIL, width=64)
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        tk.Frame(outer, bg=LINE, width=1).pack(side="left", fill="y")
        right = tk.Frame(outer, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(right, bg=BG)
        self.body.pack(fill="both", expand=True)
        tk.Frame(right, bg=LINE, height=1).pack(fill="x")
        self.status = tk.Frame(right, bg=RAIL)
        self.status.pack(fill="x")
        self._build_rail()
        self._build_status()
        self.show(self.page)

    def _build_rail(self):
        logo = tk.Frame(self.rail, bg=ACCENT, width=40, height=40)
        logo.pack(pady=(14, 18))
        logo.pack_propagate(False)
        self._logo = None
        try:
            from PIL import Image
            img = Image.open(core.ASSETS / "icon.png").convert("RGBA").resize((40, 40), Image.LANCZOS)
            bgimg = Image.new("RGBA", img.size, RAIL)
            bgimg.alpha_composite(img)
            self._logo = photo_from_pil(bgimg)
            logo.configure(bg=RAIL)
            tk.Label(logo, image=self._logo, bg=RAIL, bd=0).pack(fill="both", expand=True)
        except Exception:
            pass
        self.rail_btns = {}
        for key, tip in (("library", "Library"), ("updates", "Updates"), ("activity", "Activity")):
            self.rail_btns[key] = self._rail_button(key, tip)
        bottom = tk.Frame(self.rail, bg=RAIL)
        bottom.pack(side="bottom", pady=12)
        self.rail_btns["settings"] = self._rail_button("settings", "Settings", parent=bottom)
        av = tk.Label(bottom, text=(self.settings.get("welcome_name") or "D")[:1].upper(), bg=_mix(ACCENT, RAIL, 0.25),
                      fg=ACCENT, font=BOLD, width=3, height=1)
        av.pack(pady=(10, 0))

    def _rail_button(self, key, tip, parent=None):
        g, f = icon(key, 16)
        fr = tk.Frame(parent or self.rail, bg=RAIL, width=44, height=44, cursor="hand2")
        fr.pack(pady=3)
        fr.pack_propagate(False)
        lb = tk.Label(fr, text=g, font=f, bg=RAIL, fg=MUTED, cursor="hand2")
        lb.pack(fill="both", expand=True)
        badge = tk.Label(fr, text="", bg=ACCENT, fg=BG, font=("Segoe UI Semibold", 8), padx=4)
        for w in (fr, lb):
            w.bind("<Button-1>", lambda e, k=key: self.show(k))
        Tooltip(lb, tip)
        return fr, lb, badge

    def _paint_rail(self):
        for key, (fr, lb, badge) in self.rail_btns.items():
            on = key == self.page
            fr.configure(bg=RAISED if on else RAIL)
            lb.configure(bg=RAISED if on else RAIL, fg=TEXT if on else MUTED)
        n = len(self.updates_ready())
        fr, lb, badge = self.rail_btns["updates"]
        if n:
            badge.configure(text=str(n))
            badge.place(relx=1.0, x=-4, y=4, anchor="ne")
        else:
            badge.place_forget()

    def _build_status(self):
        for w in self.status.winfo_children():
            w.destroy()
        g, f = icon("folder", 9)
        left = tk.Label(self.status, text=f"{g}  {core.BASE}", font=SMALL, bg=RAIL, fg=MUTED, cursor="hand2")
        left.configure(font=SMALL)
        left.pack(side="left", padx=12, pady=5)
        left.bind("<Button-1>", lambda e: core.open_folder(core.BASE))
        admin = "Admin" if core.is_admin() else "Not admin"
        n = len([a for a in core.all_apps(self.state) if a.installed])
        tk.Label(self.status, text=f"{admin}  ·  {n} app{'s' if n != 1 else ''}  ·  v{core.__version__}",
                 font=SMALL, bg=RAIL, fg=GREEN if core.is_admin() else MUTED).pack(side="right", padx=12)

    def show(self, page):
        self.page = page
        for w in self.body.winfo_children():
            w.destroy()
        self.cards.clear()
        self.layout_key = None
        {"library": self.page_library, "updates": self.page_updates,
         "activity": self.page_activity, "settings": self.page_settings}[page]()
        self._paint_rail()

    def header(self, parent, title, sub=None, right=None):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=22, pady=(18, 0))
        left = tk.Frame(top, bg=BG)
        left.pack(side="left")
        if sub:
            tk.Label(left, text=sub, bg=BG, fg=MUTED, font=SMALL, anchor="w").pack(anchor="w")
        tk.Label(left, text=title, bg=BG, fg=TEXT, font=TITLE, anchor="w").pack(anchor="w")
        if right:
            right(top)
        return top

    # ------------------------------------------------------------------ library

    def greeting(self):
        h = time.localtime().tm_hour
        part = "morning" if 5 <= h < 12 else "afternoon" if h < 18 else "evening"
        name = self.settings.get("welcome_name") or ""
        return f"Good {part}{', ' + name if name else ''}"

    def page_library(self):
        def right(top):
            box = tk.Frame(top, bg=BG)
            box.pack(side="right", anchor="n")
            g, _ = icon("refresh", 10)
            self.check_btn = Btn(box, f"{g}  Check for updates" if _icon_font else "Check for updates",
                                 self.check_updates, kind="outline", font=BOLD, padx=12, pady=5)
            if _icon_font:
                self.check_btn.configure(font=BOLD)
            self.check_btn.pack(anchor="e")
            self.checked_lbl = tk.Label(box, text="", bg=BG, fg=MUTED, font=SMALL)
            self.checked_lbl.pack(anchor="e", pady=(3, 0))
            self._paint_checked()

        self.header(self.body, "Library", self.greeting(), right)
        bar = tk.Frame(self.body, bg=BG)
        bar.pack(fill="x", padx=22, pady=(14, 0))
        sbox = tk.Frame(bar, bg=CARD, highlightthickness=1, highlightbackground=CARD_LINE)
        sbox.pack(side="left", fill="x", expand=True)
        g, f = icon("search", 10)
        tk.Label(sbox, text=g, font=f, bg=CARD, fg=MUTED).pack(side="left", padx=(10, 6))
        ent = tk.Entry(sbox, textvariable=self.search, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat",
                       font=FONT, highlightthickness=0)
        ent.pack(side="left", fill="x", expand=True, ipady=6)
        self._placeholder(ent, "Search your apps")
        self.search.trace_add("write", lambda *a: self.fill_grid(force=True))
        sort = tk.Label(bar, text="", bg=CARD, fg=SUB, font=FONT, padx=12, pady=6, cursor="hand2",
                        highlightthickness=1, highlightbackground=CARD_LINE)
        sort.pack(side="left", padx=(10, 0))
        self._sort_lbl = sort
        self._paint_sort()
        sort.bind("<Button-1>", lambda e: self._sort_menu(e))

        self.banner_box = tk.Frame(self.body, bg=BG)
        self.banner_box.pack(fill="x", padx=22)
        self.paint_banners()
        self.scroll = ScrollFrame(self.body)
        self.scroll.pack(fill="both", expand=True, padx=(22, 8), pady=(14, 0))
        self.grid = self.scroll.inner
        self.scroll.canvas.bind("<Configure>", lambda e: self.root.after(60, self.fill_grid), add="+")
        self.root.after(30, self.fill_grid)

    def _placeholder(self, ent, text):
        def show(_=None):
            if not ent.get():
                ent.insert(0, text)
                ent.configure(fg=MUTED)
                ent._ph = True

        def hide(_=None):
            if getattr(ent, "_ph", False):
                ent._ph = False
                ent.delete(0, "end")
                ent.configure(fg=TEXT)
        ent._ph = False
        ent.bind("<FocusIn>", hide)
        ent.bind("<FocusOut>", show)
        show()

    def search_text(self):
        t = self.search.get()
        return "" if t == "Search your apps" else t.strip().lower()

    def _paint_sort(self):
        self._sort_lbl.configure(text=("Recently played" if self.sort == "recent" else "Name") + "  ▾")

    def _sort_menu(self, e):
        m = self.menu()
        m.add_command(label="Recently played", command=lambda: self._set_sort("recent"))
        m.add_command(label="Name", command=lambda: self._set_sort("name"))
        m.tk_popup(e.x_root, e.y_root)

    def _set_sort(self, s):
        self.sort = self.state["sort"] = s
        core.save_state(self.state)
        self._paint_sort()
        self.fill_grid(force=True)

    def sorted_apps(self):
        apps = core.all_apps(self.state)
        q = self.search_text()
        if q:
            apps = [a for a in apps if q in a.name.lower()]
        if self.sort == "name":
            return sorted(apps, key=lambda a: a.name.lower())
        return sorted(apps, key=lambda a: (not a.installed, -(core.app_state(self.state, a.id).get("last_opened") or 0), a.name.lower()))

    def fill_grid(self, force=False):
        if self.page != "library" or not self.grid.winfo_exists():
            return
        # leave room for the scrollbar whether or not it's showing, so cards never get cut off
        width = max(300, self.scroll.winfo_width() - 22)
        cols = 3 if width >= 600 else 2 if width >= 400 else 1
        cw = (width - GAP * (cols - 1)) // cols
        apps = self.sorted_apps()
        key = (cols, cw // 6, tuple(a.id for a in apps))
        if key == self.layout_key and not force:
            return
        self.layout_key = key
        for w in self.grid.winfo_children():
            w.destroy()
        self.cards.clear()
        for c in range(3):
            self.grid.grid_columnconfigure(c, weight=0, minsize=0)
        for i, app in enumerate(apps):
            card = Card(self.grid, self, app, cw)
            card.grid(row=i // cols, column=i % cols, padx=(0 if i % cols == 0 else GAP, 0), pady=(0, GAP), sticky="n")
            self.cards[app.id] = card
        if not self.search_text():
            i = len(apps)
            AddCard(self.grid, self, cw).grid(row=i // cols, column=i % cols,
                                             padx=(0 if i % cols == 0 else GAP, 0), pady=(0, GAP), sticky="n")
        elif not apps:
            tk.Label(self.grid, text="No apps match your search.", bg=BG, fg=MUTED, font=FONT).grid(row=0, column=0, sticky="w")

    def app_icon(self, app):
        """Its own icon (cached for a minute so the tiles stay quick)."""
        now = time.time()
        hit = self._icons.get(app.id)
        if hit and now - hit[1] < 60:
            return hit[0]
        p = core.app_icon(app)
        self._icons[app.id] = (p, now)
        return p

    def icon_image(self, app, path, w, h):
        """The app's own icon, centred on its colour; scaled up and sharpened when it's small."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        key = (app.id, "icon", w, h, mtime)
        if key in self.art_cache:
            return self.art_cache[key]
        try:
            from PIL import Image, ImageFilter
            ic = Image.open(path).convert("RGBA")
            size = int(h * 0.78)
            grow = size > ic.width
            ic = ic.resize((size, size), Image.LANCZOS)
            if grow:
                ic = ic.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=2))
            bg = Image.new("RGBA", (w, h), app.colour)
            bg.alpha_composite(ic, ((w - size) // 2, (h - size) // 2))
            ph = photo_from_pil(bg.convert("RGB"))
        except Exception:
            return None
        self.art_cache[key] = ph
        return ph

    def art_image(self, app, path, w, h):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        key = (app.id, w, h, mtime)
        if key in self.art_cache:
            return self.art_cache[key]
        try:
            from PIL import Image
            img = Image.open(path).convert("RGB")
            scale = max(w / img.width, h / img.height)
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
            left = (img.width - w) // 2
            img = img.crop((left, 0, left + w, h))           # keep the top of the window (title, menus)
            ph = photo_from_pil(img)
        except Exception:
            return None
        self.art_cache = {k: v for k, v in self.art_cache.items() if k[0] != app.id}
        self.art_cache[key] = ph
        return ph

    def paint_banners(self):
        if self.page != "library" or not getattr(self, "banner_box", None) or not self.banner_box.winfo_exists():
            return
        for w in self.banner_box.winfo_children():
            w.destroy()
        items = []
        cands = core.import_candidates(self.state)
        if cands and "import" not in self.busy:
            ns = [a.name for a, _ in cands]
            names = ns[0] if len(ns) == 1 else ", ".join(ns[:-1]) + " and " + ns[-1]
            items.append((f"Found {names} on your Desktop. Bring {'them' if len(cands) > 1 else 'it'} into the "
                          f"Workshop with all saved data. The originals stay where they are as a backup.",
                          [("Bring them in" if len(cands) > 1 else "Bring it in", self.import_all)], "accent", False))
        if "import" in self.busy:
            items.append((self.busy["import"], [], "accent", False))
        hub = self.checker.results.get("hub")
        if hub and core.newer(hub.version, core.__version__):
            items.append((f"Dan's Workshop v{hub.version} is ready to install.",
                          [("What's new", lambda: self.show("updates")), ("Update", self.update_hub)], "accent", True))
        for app in self.updates_ready():
            info = self.update_for(app)
            items.append((f"{app.name} v{info.version} is ready to install.",
                          [("What's new", lambda: self.show("updates")), ("Update", lambda a=app: self.update_app(a))],
                          "accent", True))
        for text, tone in self.messages:
            items.append((text, [], tone, True))
        for text, actions, tone, closable in items:
            b = Banner(self.banner_box, text, actions, tone, closable,
                       on_close=(lambda t=text: self._drop_msg(t)))
            b.pack(fill="x", pady=(12, 0))

    def _drop_msg(self, text):
        self.messages = [m for m in self.messages if m[0] != text]

    def say(self, text, tone="good"):
        self.messages = [m for m in self.messages if m[0] != text] + [(text, tone)]
        self.messages = self.messages[-3:]
        self.paint_banners()

    def _paint_checked(self):
        if not getattr(self, "checked_lbl", None) or not self.checked_lbl.winfo_exists():
            return
        if self.checker.busy:
            self.checked_lbl.configure(text="Checking…")
        elif self.checker.last_checked:
            self.checked_lbl.configure(text=f"Last checked {core.ago(self.checker.last_checked)}")
        else:
            self.checked_lbl.configure(text="Not checked yet")

    # ------------------------------------------------------------------ updates page

    def page_updates(self):
        def right(top):
            Btn(top, "Check for updates", self.check_updates, kind="outline", padx=12, pady=5).pack(side="right", anchor="n")
        self.header(self.body, "Updates", "Everything in the Workshop", right)
        sc = ScrollFrame(self.body)
        sc.pack(fill="both", expand=True, padx=(22, 8), pady=(14, 0))
        rows = [("hub", core.APP_NAME, core.__version__, self.checker.results.get("hub"), None)]
        for a in core.all_apps(self.state):
            if a.kind in ("custom", "external", "script"):
                continue
            rows.append((a.id, a.name, core.app_state(self.state, a.id).get("version", ""), self.checker.results.get(a.id), a))
        for key, name, have, info, app in rows:
            r = tk.Frame(sc.inner, bg=CARD, highlightthickness=1, highlightbackground=CARD_LINE)
            r.pack(fill="x", pady=(0, 10), padx=(0, 6))
            top = tk.Frame(r, bg=CARD)
            top.pack(fill="x", padx=14, pady=(12, 0))
            tk.Label(top, text=name, bg=CARD, fg=TEXT, font=H2).pack(side="left")
            ready = bool(info and have and core.newer(info.version, have)) or bool(info and not have and app and app.installed)
            if key == "hub":
                ready = bool(info and core.newer(info.version, core.__version__))
            if self.checker.errors.get(key):
                state, col = "Couldn't check (offline?)", RED
            elif not self.checker.last_checked:
                state, col = "Not checked yet", MUTED
            elif ready:
                state, col = f"v{have or '?'}  →  v{info.version}", ACCENT
            elif app and not app.installed:
                state, col = "Not in the Workshop yet", MUTED
            else:
                state, col = f"Up to date  ·  v{have or (info.version if info else '?')}", GREEN
            tk.Label(top, text=state, bg=CARD, fg=col, font=BOLD).pack(side="left", padx=12)
            if ready:
                cmd = self.update_hub if key == "hub" else (lambda a=app: self.update_app(a))
                label = self.busy.get(key) or "Update"
                Btn(top, label, cmd, kind="primary", padx=12, pady=4).pack(side="right")
            notes = (info.notes if info else "") or ""
            if notes:
                tk.Label(r, text="What's new", bg=CARD, fg=MUTED, font=SMALL, anchor="w").pack(fill="x", padx=14, pady=(8, 0))
                lb = tk.Label(r, text=notes.strip()[:1500], bg=CARD, fg=SUB, font=FONT, justify="left", anchor="w")
                lb.pack(fill="x", padx=14, pady=(2, 12))
                lb.bind("<Configure>", lambda e, l=lb: l.configure(wraplength=max(200, e.width - 8)))
            else:
                tk.Frame(r, bg=CARD, height=12).pack()

    # ------------------------------------------------------------------ activity page

    def page_activity(self):
        def right(top):
            Btn(top, "Clear", self._clear_activity, kind="ghost", padx=8, pady=4).pack(side="right", anchor="n")
        self.header(self.body, "Activity", "When apps were opened and updated", right)
        sc = ScrollFrame(self.body)
        sc.pack(fill="both", expand=True, padx=(22, 8), pady=(10, 0))
        items = core.activity()
        if not items:
            tk.Label(sc.inner, text="Nothing yet. Opening or updating an app adds a line here.",
                     bg=BG, fg=MUTED, font=FONT).pack(anchor="w", pady=10)
            return
        day = None
        for it in items[:400]:
            d = core.nice_date(it["t"])
            if d != day:
                day = d
                tk.Label(sc.inner, text=d, bg=BG, fg=ACCENT, font=BOLD, anchor="w").pack(fill="x", pady=(12, 4))
            row = tk.Frame(sc.inner, bg=BG)
            row.pack(fill="x")
            tk.Label(row, text=core.nice_time(it["t"]), bg=BG, fg=MUTED, font=FONT, width=9, anchor="w").pack(side="left")
            dot = GREEN if it["event"] == "opened" else ACCENT
            tk.Label(row, text="●", bg=BG, fg=dot, font=SMALL).pack(side="left", padx=(0, 8))
            tk.Label(row, text=f"{it['app']}  {it['event']}", bg=BG, fg=TEXT, font=FONT, anchor="w").pack(side="left")
            tk.Frame(sc.inner, bg=LINE, height=1).pack(fill="x", pady=(6, 6))

    def _clear_activity(self):
        if messagebox.askyesno(core.APP_NAME, "Clear the activity list?", parent=self.root):
            core.clear_activity()
            self.show("activity")

    # ------------------------------------------------------------------ settings page

    def page_settings(self):
        self.header(self.body, "Settings", "Dan's Workshop")
        sc = ScrollFrame(self.body)
        sc.pack(fill="both", expand=True, padx=(22, 8), pady=(10, 0))
        p = sc.inner

        def section(title, sub=""):
            box = tk.Frame(p, bg=CARD, highlightthickness=1, highlightbackground=CARD_LINE)
            box.pack(fill="x", pady=(0, 12), padx=(0, 6))
            tk.Label(box, text=title, bg=CARD, fg=TEXT, font=H2, anchor="w").pack(fill="x", padx=14, pady=(12, 0))
            if sub:
                sl = tk.Label(box, text=sub, bg=CARD, fg=MUTED, font=SMALL, anchor="w", justify="left")
                sl.pack(fill="x", padx=14)
                sl.bind("<Configure>", lambda e, l=sl: l.configure(wraplength=max(200, e.width - 8)))
            inner = tk.Frame(box, bg=CARD)
            inner.pack(fill="x", padx=14, pady=(10, 14))
            return inner

        def chips(parent, options, current, on_pick):
            row = tk.Frame(parent, bg=CARD)
            row.pack(anchor="w")
            for val, label in options:
                on = val == current
                b = Btn(row, label, lambda v=val: on_pick(v), kind="primary" if on else "plain", font=FONT, padx=12, pady=5)
                b.pack(side="left", padx=(0, 8))

        s = section("After opening an app", "What the Workshop does once an app has started.")
        chips(s, [("keep", "Stay open"), ("minimise", "Minimise"), ("close", "Close")], self.settings["after_launch"],
              lambda v: self._set("after_launch", v))

        s = section("Accent colour")
        row = tk.Frame(s, bg=CARD)
        row.pack(anchor="w")
        for name, (col, _) in core.ACCENTS.items():
            on = name == self.settings["accent"]
            sw = tk.Frame(row, bg=col, width=34, height=34, cursor="hand2",
                          highlightthickness=2, highlightbackground=TEXT if on else CARD)
            sw.pack(side="left", padx=(0, 10))
            sw.bind("<Button-1>", lambda e, n=name: self._set_accent(n))

        s = section("Your name", "Used for the greeting on the Library.")
        e = tk.Entry(s, bg=RAISED, fg=TEXT, insertbackground=TEXT, relief="flat", font=FONT, width=24)
        e.insert(0, self.settings.get("welcome_name", ""))
        e.pack(anchor="w", ipady=5)
        e.bind("<FocusOut>", lambda ev: self._set("welcome_name", e.get().strip(), rebuild=False))
        e.bind("<Return>", lambda ev: self._set("welcome_name", e.get().strip(), rebuild=False))

        s = section("Opening without the admin prompt",
                    "The desktop shortcut starts the Workshop through a Windows task, so it runs as administrator "
                    "without asking every time. Apps opened from here run as administrator too.")
        exe = Path(sys.executable)
        ok = core.task_ok(self.settings, exe) if getattr(sys, "frozen", False) else False
        tk.Label(s, text="Set up and working" if ok else "Not set up yet", bg=CARD, fg=GREEN if ok else ACCENT,
                 font=BOLD).pack(anchor="w", pady=(0, 8))
        Btn(s, "Set up again" if ok else "Set it up", self.setup_admin, kind="plain", font=FONT, padx=12, pady=5).pack(anchor="w")

        s = section("Updates")
        v = tk.BooleanVar(value=self.settings.get("check_on_open", True))
        cb = tk.Checkbutton(s, text="Check for updates when the Workshop opens", variable=v, bg=CARD, fg=TEXT,
                            selectcolor=RAISED, activebackground=CARD, activeforeground=TEXT, font=FONT,
                            command=lambda: self._set("check_on_open", v.get(), rebuild=False))
        cb.pack(anchor="w")

        s = section("Workshop folder", "Everything lives here, so the whole folder can be moved or backed up in one go.")
        tk.Label(s, text=str(core.BASE), bg=CARD, fg=SUB, font=FONT).pack(anchor="w", pady=(0, 8))
        Btn(s, "Open folder", lambda: core.open_folder(core.BASE), kind="plain", font=FONT, padx=12, pady=5).pack(anchor="w")

        s = section("About")
        tk.Label(s, text=f"Dan's Workshop v{core.__version__}", bg=CARD, fg=SUB, font=FONT).pack(anchor="w")

    def _set(self, key, value, rebuild=True):
        self.settings[key] = value
        core.save_settings(self.settings)
        if rebuild:
            self.show(self.page)

    def _set_accent(self, name):
        self.settings["accent"] = name
        core.save_settings(self.settings)
        set_accent(name)
        self.art_cache.clear()
        self.build()

    # ------------------------------------------------------------------ state helpers

    def is_running(self, app):
        return self.running.get(app.id, False)

    def update_for(self, app) -> Optional[core.UpdateInfo]:
        info = self.checker.results.get(app.id)
        if not info or not app.installed or app.kind in ("custom", "external", "script"):
            return None
        have = core.app_state(self.state, app.id).get("version", "")
        if not have or core.newer(info.version, have):
            return info if have else None
        return None

    def updates_ready(self):
        return [a for a in core.all_apps(self.state) if self.update_for(a)]

    def menu(self):
        return tk.Menu(self.root, tearoff=0, bg=CARD, fg=TEXT, activebackground=RAISED, activeforeground=TEXT,
                       bd=0, font=FONT)

    def card_menu(self, app, x, y):
        m = self.menu()
        if app.id == "obsidian" and app.installed:
            self._obsidian_menu(m, app)
            m.tk_popup(x, y)
            return
        if app.installed and app.kind == "script":
            for label, file in app.actions:
                m.add_command(label=label, command=lambda l=label, f=file: self.run_action(app, l, f))
            if (app.dir / "mods").is_dir():
                m.add_command(label="Open mods folder", command=lambda: core.open_folder(app.dir / "mods"))
            m.add_separator()
        if app.installed:
            m.add_command(label="Open folder", command=lambda: core.open_folder(app.dir))
            m.add_command(label="Request a change…", command=lambda: self.request_change(app))
            m.add_separator()
            m.add_command(label="Change picture…", command=lambda: self.change_picture(app))
            m.add_command(label="Use its icon again" if (app.icon or self._icons.get(app.id, (None,))[0]) else "Retake picture next time it's open", command=lambda: self.retake(app))
        else:
            m.add_command(label="Add from a folder…", command=lambda: self.add_from_folder(app))
        if app.kind == "custom":
            m.add_separator()
            m.add_command(label="Remove from the Workshop", command=lambda: self.remove_app(app))
        m.tk_popup(x, y)

    # ------------------------------------------------------------------ actions

    def primary(self, app):
        if self.busy.get(app.id):
            return
        if not app.installed and app.id == "obsidian":
            self.install_obsidian()
            return
        if not app.installed:
            if core.expand(app.import_from).joinpath(app.exe).is_file():
                self.import_all()
            else:
                self.add_from_folder(app)
            return
        if app.kind == "script":
            self.run_action(app, app.play_label, app.exe)
            return
        if self.is_running(app):
            core.bring_to_front(core.main_window(core.pids_for(app, self.procs)))
            return
        if self.update_for(app):
            self.update_app(app)
            return
        self.play(app)

    def play(self, app, vault: str = ""):
        try:
            core.launch(app, vault or core.app_state(self.state, app.id).get("vault", ""))
        except Exception as e:
            messagebox.showerror(core.APP_NAME, f"Couldn't open {app.name}:\n{e}", parent=self.root)
            return
        st = core.app_state(self.state, app.id)
        st["last_opened"] = time.time()
        core.save_state(self.state)
        core.log_activity(app.name, "opened")
        self.running[app.id] = True
        self.started_at[app.id] = time.time()
        self.refresh_cards()
        after = self.settings.get("after_launch")
        if after == "minimise":
            self.root.iconify()
        elif after == "close":
            self.root.after(1500, self.root.destroy)

    def run_action(self, app, label, file):
        try:
            core.run_script(app, file)
        except Exception as e:
            messagebox.showerror(core.APP_NAME, f"Couldn't run {label}:\n{e}", parent=self.root)
            return
        core.app_state(self.state, app.id)["last_opened"] = time.time()
        core.save_state(self.state)
        core.log_activity(app.name, label.lower())
        self.refresh_cards()

    def check_updates(self, quiet=False):
        apps = [a for a in core.all_apps(self.state)]
        started = self.checker.run(apps, lambda: self.root.after(0, lambda: self._checked(quiet)))
        if started:
            self._paint_checked()

    def _checked(self, quiet):
        for a in core.all_apps(self.state):
            if a.kind == "github-exe" and a.installed:
                core.installed_version(a, self.state, self.checker.releases.get(a.id))
        core.save_state(self.state)
        if not quiet:
            n = len(self.updates_ready()) + (1 if (self.checker.results.get("hub") and
                                                   core.newer(self.checker.results["hub"].version, core.__version__)) else 0)
            if self.checker.errors and not n:
                self.say("Couldn't reach GitHub to check for updates. Check your internet and try again.", "bad")
            elif not n:
                self.say("Everything is up to date.", "good")
        self._paint_checked()
        if self.page == "updates":
            self.show("updates")
        else:
            self.paint_banners()
            self.refresh_cards()
            self._paint_rail()

    def update_app(self, app):
        info = self.update_for(app) or self.checker.results.get(app.id)
        if not info:
            return
        if self.is_running(app):
            messagebox.showinfo(core.APP_NAME, f"Close {app.name} first, then press Update again.", parent=self.root)
            return
        self.busy[app.id] = "Updating…"
        self.say(f"Updating {app.name}…", "accent")

        def work():
            err = None
            try:
                core.install_update(app, info, lambda f: self.root.after(0, lambda: self._progress(app, f)))
            except Exception as e:
                err = str(e)
            self.root.after(0, lambda: self._updated(app, info, err))

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, app, f):
        self.busy[app.id] = f"Downloading {round(f * 100)}%"
        c = self.cards.get(app.id)
        if c and c.winfo_exists():
            c.btn.set(self.busy[app.id], "plain")

    def _updated(self, app, info, err):
        self.busy.pop(app.id, None)
        self._drop_msg(f"Updating {app.name}…")
        if err:
            self.say(f"{app.name} didn't update: {err}", "bad")
        else:
            st = core.app_state(self.state, app.id)
            st["version"] = info.version
            st.pop("ver_key", None)
            core.installed_version(app, self.state, self.checker.releases.get(app.id))
            st["version"] = info.version
            st["recapture"] = True
            st["seen_version"] = info.version
            core.save_state(self.state)
            core.log_activity(app.name, f"updated to v{info.version}")
            self.say(f"{app.name} is now on v{info.version}.", "good")
        if self.page == "updates":
            self.show("updates")
        else:
            self.paint_banners()
            self.refresh_cards()
            self._paint_rail()

    def update_hub(self):
        info = self.checker.results.get("hub")
        if not info:
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(core.APP_NAME, "Updates only install in the packaged app.", parent=self.root)
            return
        self.busy["hub"] = "Downloading…"
        self.say("Downloading the new Dan's Workshop… it restarts by itself when ready.", "accent")

        def work():
            try:
                core.start_hub_update(info)
            except Exception as e:
                self.root.after(0, lambda: (self.busy.pop("hub", None), self.say(f"The update didn't download: {e}", "bad")))
                return
            self.root.after(0, self.root.destroy)

        threading.Thread(target=work, daemon=True).start()

    def import_all(self):
        cands = core.import_candidates(self.state)
        if not cands or "import" in self.busy:
            return
        # the originals must be closed so their saved data is complete
        open_now = []
        procs = core.running_pids()
        for app, src in cands:
            key = str((src / app.exe).resolve()).lower()
            if procs.get(key) or self.is_running(app):
                open_now.append(app.name)
        if open_now:
            messagebox.showinfo(core.APP_NAME, "Close " + " and ".join(open_now) + " first, so all of its saved data is "
                                "brought across. Then press the button again.", parent=self.root)
            return
        self.busy["import"] = "Bringing your apps in…"
        self.paint_banners()

        def work():
            notes, errors = [], []
            for app, src in cands:
                try:
                    def prog(f, name, a=app):
                        self.busy["import"] = f"Bringing in {a.name}…  {round(f * 100)}%"
                    note = core.import_app(app, src, prog)
                    st = core.app_state(self.state, app.id)
                    st.pop("ver_key", None)
                    st["imported_from"] = str(src)
                    core.log_activity(app.name, "added to the Workshop")
                    notes.append(app.name + (f" ({note})" if note else ""))
                except Exception as e:
                    errors.append(f"{app.name}: {e}")
            self.root.after(0, lambda: self._imported(notes, errors))

        threading.Thread(target=work, daemon=True).start()
        self._import_progress()

    def _import_progress(self):
        if "import" not in self.busy:
            return
        for b in self.banner_box.winfo_children() if self.banner_box.winfo_exists() else []:
            if isinstance(b, Banner):
                b.text(self.busy["import"])
        self.root.after(250, self._import_progress)

    def _imported(self, notes, errors):
        self.busy.pop("import", None)
        for a in core.all_apps(self.state):
            if a.installed:
                core.installed_version(a, self.state, self.checker.releases.get(a.id))
        core.save_state(self.state)
        if notes:
            self.say("Brought in " + ", ".join(notes) + ". Your old copies on the Desktop are untouched: "
                     "delete them once you're happy everything works from here.", "good")
        if errors:
            self.say("Some things didn't copy: " + "; ".join(errors), "bad")
        self._build_status()
        self.fill_grid(force=True)
        self.check_updates(quiet=True)

    def add_from_folder(self, app):
        path = filedialog.askopenfilename(parent=self.root, title=f"Find {app.exe}",
                                          filetypes=[(app.exe, app.exe), ("Programs", "*.exe")])
        if not path:
            return
        src = Path(path).parent
        self.busy["import"] = f"Bringing in {app.name}…"
        self.paint_banners()

        def work():
            try:
                note = core.import_app(app, src)
                core.log_activity(app.name, "added to the Workshop")
                self.root.after(0, lambda: self._imported([app.name + (f" ({note})" if note else "")], []))
            except Exception as e:
                self.root.after(0, lambda: self._imported([], [f"{app.name}: {e}"]))

        threading.Thread(target=work, daemon=True).start()
        self._import_progress()

    # ------------------------------------------------------------------ Obsidian

    def _submenu(self, m):
        return tk.Menu(m, tearoff=0, bg=CARD, fg=TEXT, activebackground=RAISED, activeforeground=TEXT, font=FONT)

    def _obsidian_menu(self, m, app):
        vaults = core.obsidian_vaults()
        default = core.app_state(self.state, app.id).get("vault", "")
        inside = {os.path.normcase(str(v)) for v in core.workshop_vaults()}
        if vaults:
            sub = self._submenu(m)
            for v in vaults:
                tag = "  (in the Workshop)" if os.path.normcase(v["path"]) in inside else ""
                sub.add_command(label=v["name"] + tag, command=lambda p=v["path"]: self.play(app, core.stored_vault(p)))
            m.add_cascade(label="Open vault", menu=sub)
            pick = self._submenu(m)
            pick.add_command(label=("✓ " if not default else "   ") + "Whatever was open last",
                             command=lambda: self._set_vault(app, ""))
            for v in vaults:
                st = core.stored_vault(v["path"])
                pick.add_command(label=("✓ " if default == st else "   ") + v["name"],
                                 command=lambda st=st: self._set_vault(app, st))
            m.add_cascade(label="Play opens…", menu=pick)
            if default:
                m.add_command(label="Open the notes folder",
                              command=lambda: core.open_folder(Path(core.vault_path(default))))
        m.add_separator()
        outside = [v for v in vaults if os.path.normcase(v["path"]) not in inside]
        if outside:
            mv = self._submenu(m)
            for v in outside:
                mv.add_command(label=v["name"], command=lambda v=v: self.move_vault(app, v))
            m.add_cascade(label="Move a vault into the Workshop", menu=mv)
        m.add_command(label="Back up notes now", command=lambda: self.backup_notes(force=True))
        names = sorted({p.name for p in core.BACKUP_DIR.iterdir() if p.is_dir()}) if core.BACKUP_DIR.is_dir() else []
        if names:
            rs = self._submenu(m)
            for n in names:
                zs = self._submenu(rs)
                for z in core.list_backups(n)[:15]:
                    when = time.strftime("%d %b %Y, ", time.localtime(z.stat().st_mtime)) + core.nice_time(z.stat().st_mtime)
                    zs.add_command(label=when, command=lambda z=z, n=n: self.restore_notes(app, z, n))
                rs.add_cascade(label=n, menu=zs)
            m.add_cascade(label="Restore a backup", menu=rs)
            m.add_command(label="Open backups folder", command=lambda: core.open_folder(core.BACKUP_DIR))
        m.add_separator()
        m.add_command(label="Change picture…", command=lambda: self.change_picture(app))
        m.add_command(label="Use its icon again", command=lambda: self.retake(app))

    def _set_vault(self, app, stored):
        core.app_state(self.state, app.id)["vault"] = stored
        core.save_state(self.state)
        name = Path(core.vault_path(stored)).name if stored else "whatever vault was open last"
        self.say(f"Play on Obsidian now opens {name}.", "good")

    def _obsidian_open(self) -> bool:
        ob = next((a for a in core.all_apps(self.state) if a.id == "obsidian"), None)
        return bool(ob and core.pids_for(ob, core.running_pids()))

    def move_vault(self, app, v):
        if self._obsidian_open():
            messagebox.showinfo(core.APP_NAME, "Close Obsidian first, then try again.", parent=self.root)
            return
        warn = core.vault_warnings(v["path"])
        text = (f"Move \u201c{v['name']}\u201d into the Workshop?\n\nIt's copied to {core.NOTES_DIR / v['name']} and Obsidian "
                f"opens it from there. The original folder stays where it is as a backup.")
        if warn:
            text += ("\n\nCareful: " + "; ".join(warn) + ". Moving it means that stops for this copy. "
                     "Only carry on if that's what you want.")
        if not messagebox.askyesno(core.APP_NAME, text, icon="warning" if warn else "question", parent=self.root):
            return
        self.busy["import"] = f"Moving {v['name']} into the Workshop…"
        self.paint_banners()

        def work():
            try:
                def prog(f, name):
                    self.busy["import"] = f"Moving {v['name']} into the Workshop…  {round(f * 100)}%"
                new = core.move_vault_in(v["path"], prog)
                self.root.after(0, lambda: self._vault_moved(app, v, new, None))
            except Exception as e:
                self.root.after(0, lambda: self._vault_moved(app, v, None, str(e)))

        threading.Thread(target=work, daemon=True).start()
        self._import_progress()

    def _vault_moved(self, app, v, new, err):
        self.busy.pop("import", None)
        if err:
            self.say(f"{v['name']} wasn't moved: {err}", "bad")
            return
        st = core.app_state(self.state, app.id)
        if not st.get("vault") or core.vault_path(st["vault"]) == v["path"]:
            st["vault"] = core.stored_vault(str(new))
        core.save_state(self.state)
        core.log_activity("Obsidian", f"vault {v['name']} moved into the Workshop")
        self.say(f"{v['name']} now lives in the Workshop ({new}) and Obsidian opens it from there. "
                 f"The old folder ({v['path']}) is untouched - delete it once you're happy.", "good")
        self.backup_notes()

    def _vaults_to_back_up(self) -> List[str]:
        out = [str(v) for v in core.workshop_vaults()]
        default = core.app_state(self.state, "obsidian").get("vault", "")
        if default and core.vault_path(default) not in out and Path(core.vault_path(default)).is_dir():
            out.append(core.vault_path(default))
        return out

    def backup_notes(self, force=False):
        vaults = self._vaults_to_back_up()
        if not vaults:
            if force:
                self.say("Nothing to back up yet: move a vault into the Workshop, or pick which vault Play opens.", "bad")
            return

        def work():
            made, errs = [], []
            for v in vaults:
                try:
                    z = core.backup_vault(v, force=force)
                    if z:
                        made.append(Path(v).name)
                except Exception as e:
                    errs.append(f"{Path(v).name}: {e}")
            def done():
                if made:
                    core.log_activity("Obsidian", "notes backed up (" + ", ".join(made) + ")")
                    if force:
                        self.say("Notes backed up: " + ", ".join(made) + ".", "good")
                elif force and not errs:
                    self.say("Notes backed up.", "good")
                if errs:
                    self.say("A notes backup didn't finish: " + "; ".join(errs), "bad")
            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def restore_notes(self, app, zip_path, name):
        if self._obsidian_open():
            messagebox.showinfo(core.APP_NAME, "Close Obsidian first, then try again.", parent=self.root)
            return
        target = core.NOTES_DIR / name
        if not target.exists():
            match = [v["path"] for v in core.obsidian_vaults() if v["name"] == name]
            target = Path(match[0]) if match else target
        when = time.strftime("%d %b %Y %H:%M", time.localtime(zip_path.stat().st_mtime))
        if not messagebox.askyesno(core.APP_NAME, f"Put {name} back to how it was on {when}?\n\nThe current version "
                                   "is kept next to it (renamed \u201cbefore restore\u201d), so nothing is lost.",
                                   parent=self.root):
            return
        try:
            core.restore_backup(zip_path, str(target))
            core.register_workshop_vaults()
        except Exception as e:
            self.say(f"Couldn't restore {name}: {e}", "bad")
            return
        core.log_activity("Obsidian", f"vault {name} restored from {when}")
        self.say(f"{name} is back to how it was on {when}.", "good")

    def install_obsidian(self):
        if "obsidian" in self.busy:
            return
        self.busy["obsidian"] = "Downloading…"
        self.say("Downloading Obsidian's installer…", "accent")

        def work():
            try:
                info = core.obsidian_installer()
                if not info:
                    raise RuntimeError("couldn't find the installer")
                dest = core.DATA_DIR / "downloads" / info.url.rsplit("/", 1)[-1]
                core.download(info.url, dest, info.size)
                core.launch_as_user(str(dest))
                msg, tone = ("Obsidian's installer is open: click through it, then press Play. Your notes in the "
                             "Workshop are added to Obsidian automatically."), "good"
            except Exception as e:
                msg, tone = f"Couldn't get Obsidian's installer: {e}", "bad"
            self.root.after(0, lambda: (self.busy.pop("obsidian", None), self._drop_msg("Downloading Obsidian's installer…"),
                                        self.say(msg, tone), self.refresh_cards()))

        threading.Thread(target=work, daemon=True).start()

    def add_app(self):
        AddAppDialog(self)

    def remove_app(self, app):
        if messagebox.askyesno(core.APP_NAME, f"Remove {app.name} from the Workshop list?\n\n"
                               "Its files stay in the folder, so nothing is deleted.", parent=self.root):
            core.remove_custom_app(app.id, self.state)
            self.fill_grid(force=True)

    def request_change(self, app):
        text = core.change_brief(app, core.app_state(self.state, app.id).get("version", ""))
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        import webbrowser
        webbrowser.open("https://claude.ai/new")
        self.say(f"A brief about {app.name} is copied. Paste it into Claude (Ctrl+V) and add the change you want.", "good")

    def change_picture(self, app):
        path = filedialog.askopenfilename(parent=self.root, title="Pick a picture",
                                          filetypes=[("Pictures", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")])
        if not path:
            return
        try:
            core.set_custom_art(app, Path(path))
            core.app_state(self.state, app.id)["custom_art"] = True
            core.app_state(self.state, app.id).pop("recapture", None)
            core.save_state(self.state)
        except Exception as e:
            messagebox.showerror(core.APP_NAME, f"Couldn't use that picture:\n{e}", parent=self.root)
        self.refresh_cards()

    def retake(self, app):
        st = core.app_state(self.state, app.id)
        if self._icons.get(app.id, (None,))[0] or app.icon:
            st.pop("custom_art", None)
            core.save_state(self.state)
            self.refresh_cards()
            return
        st["recapture"] = True
        st.pop("custom_art", None)
        core.save_state(self.state)
        self.say(f"A new picture of {app.name} will be taken the next time it's open on your screen.", "good")

    def setup_admin(self):
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(core.APP_NAME, "This only works in the packaged app.", parent=self.root)
            return
        ok, msg = core.setup_no_prompt(Path(sys.executable))
        if ok:
            self.settings["task_path"] = str(Path(sys.executable))
            self.settings["shortcut_done"] = True
            core.save_settings(self.settings)
            self.say("Desktop shortcut ready. Right-click it and choose Pin to taskbar (on Windows 11: Show more "
                     "options → Pin to taskbar). It opens the Workshop as administrator without asking.", "good")
        else:
            self.say(f"Couldn't set up the shortcut: {msg}", "bad")
        if self.page == "settings":
            self.show("settings")

    # ------------------------------------------------------------------ background

    def _register_vaults(self):
        try:
            if core.workshop_vaults() and not self._obsidian_open():
                n = core.register_workshop_vaults()
                if n:
                    self.say(f"Added {n} vault{'s' if n > 1 else ''} from the Workshop to Obsidian.", "good")
        except Exception:
            pass

    def first_steps(self):
        self._register_vaults()
        if self.settings.get("check_on_open", True):
            self.check_updates(quiet=True)
        if getattr(sys, "frozen", False) and core.IS_WIN and core.is_admin():
            exe = Path(sys.executable)
            if self.settings.get("task_path") != str(exe):
                # first run, or the folder moved: make (or fix) the no-prompt shortcut
                self.setup_admin()
            if self.settings.get("icon_rev") != core.ICON_REV:
                threading.Thread(target=core.refresh_icons, args=(exe,), daemon=True).start()
                self.settings["icon_rev"] = core.ICON_REV
                core.save_settings(self.settings)

    def poll_loop(self):
        while True:
            try:
                procs = core.running_pids()
                fg = core.foreground_pid()
                captures = []
                for app in core.all_apps(self.state):
                    pids = core.pids_for(app, procs)
                    st = core.app_state(self.state, app.id)
                    if not pids or st.get("custom_art") or self._icons.get(app.id, (None,))[0]:
                        self.capture_seen.pop(app.id, None)
                        continue
                    need = st.get("recapture") or not core.art_path(app)
                    if not need or fg not in pids:
                        self.capture_seen.pop(app.id, None)
                        continue
                    box = core.client_box(core.main_window(pids))
                    if not box:
                        continue
                    prev = self.capture_seen.get(app.id)
                    if prev and prev[0] == box and time.time() - prev[1] >= 4:
                        if core.capture_art(app, box):
                            captures.append(app.id)
                        self.capture_seen.pop(app.id, None)
                    elif not prev or prev[0] != box:
                        self.capture_seen[app.id] = (box, time.time())
                self.root.after(0, lambda p=procs, c=captures: self._polled(p, c))
            except Exception:
                pass
            time.sleep(3)

    def _polled(self, procs, captures):
        self.procs = procs
        changed = bool(captures)
        for app_id in captures:
            core.app_state(self.state, app_id).pop("recapture", None)
        for app in core.all_apps(self.state):
            now = bool(core.pids_for(app, procs))
            if now and app.id in self.started_at and time.time() - self.started_at[app.id] < 8:
                pass
            was = self.running.get(app.id, False)
            if not now and app.id in self.started_at and time.time() - self.started_at[app.id] < 8:
                now = True                     # still starting up
            if now != was:
                changed = True
                self.running[app.id] = now
                if now and not (app.id in self.started_at and time.time() - self.started_at[app.id] < 10):
                    core.app_state(self.state, app.id)["last_opened"] = time.time()
                    core.log_activity(app.name, "opened")
                if app.id == "obsidian" and was and not now:
                    self.backup_notes()                       # Obsidian just closed: back up the notes
                    self._register_vaults()
            # an app that updated itself (both apps can) shows up as a new version
            if app.installed:
                st = core.app_state(self.state, app.id)
                v = core.installed_version(app, self.state, self.checker.releases.get(app.id))
                seen = st.get("seen_version")
                if v and seen and v != seen and core.newer(v, seen):
                    core.log_activity(app.name, f"updated to v{v}")
                    st["recapture"] = not st.get("custom_art")
                    changed = True
                if v:
                    st["seen_version"] = v
        if changed:
            core.save_state(self.state)
            self.refresh_cards()
            self.paint_banners()
            self._paint_rail()

    def refresh_cards(self):
        for c in list(self.cards.values()):
            if c.winfo_exists():
                c.refresh()

    def tick(self):
        self._paint_checked()
        self.root.after(30_000, self.tick)


class Tooltip:
    def __init__(self, widget, text):
        self.w, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _):
        if self.tip:
            return
        x, y = self.w.winfo_rootx() + self.w.winfo_width() + 6, self.w.winfo_rooty() + 10
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=RAISED, fg=TEXT, font=SMALL, padx=8, pady=3).pack()

    def hide(self, _):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class AddAppDialog(tk.Toplevel):
    def __init__(self, hub: Hub):
        super().__init__(hub.root, bg=BG)
        self.hub = hub
        self.title("Add an app")
        self.resizable(False, False)
        self.transient(hub.root)
        self.exe: Optional[Path] = None
        pad = dict(padx=20)
        tk.Label(self, text="Add an app", bg=BG, fg=TEXT, font=TITLE).pack(anchor="w", pady=(18, 4), **pad)
        tk.Label(self, text="Pick the program's .exe. Its folder is copied into the Workshop so its saved data\n"
                            "comes along and everything stays in one portable place.",
                 bg=BG, fg=SUB, font=FONT, justify="left").pack(anchor="w", **pad)
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", pady=(14, 6), **pad)
        self.path_lbl = tk.Label(row, text="No program picked", bg=CARD, fg=MUTED, font=FONT, anchor="w", padx=10, pady=6, width=46)
        self.path_lbl.pack(side="left")
        Btn(row, "Browse…", self.pick, kind="plain", font=FONT).pack(side="left", padx=(8, 0))
        tk.Label(self, text="Name", bg=BG, fg=MUTED, font=SMALL).pack(anchor="w", pady=(8, 2), **pad)
        self.name = tk.Entry(self, bg=RAISED, fg=TEXT, insertbackground=TEXT, relief="flat", font=FONT, width=40)
        self.name.pack(anchor="w", ipady=5, **pad)
        self.copy = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Copy it into the Workshop folder (recommended)", variable=self.copy, bg=BG, fg=TEXT,
                       selectcolor=RAISED, activebackground=BG, activeforeground=TEXT, font=FONT).pack(anchor="w", pady=(12, 0), **pad)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", pady=18, **pad)
        Btn(bar, "Add", self.add, kind="primary").pack(side="right")
        Btn(bar, "Cancel", self.destroy, kind="ghost").pack(side="right", padx=8)
        self.err = tk.Label(bar, text="", bg=BG, fg=RED, font=SMALL)
        self.err.pack(side="left")
        self.grab_set()

    def pick(self):
        p = filedialog.askopenfilename(parent=self, title="Pick the program", filetypes=[("Programs", "*.exe")])
        if p:
            self.exe = Path(p)
            self.path_lbl.configure(text=str(self.exe)[-60:], fg=TEXT)
            if not self.name.get():
                self.name.insert(0, self.exe.stem)
            self.err.configure(text="")

    def add(self):
        if not self.exe:
            self.err.configure(text="Pick the program first")
            return
        if not self.name.get().strip():
            self.err.configure(text="Give it a name")
            return
        try:
            app = core.add_custom_app(self.name.get().strip(), self.exe, self.copy.get(), self.hub.state)
            core.log_activity(app.name, "added to the Workshop")
        except Exception as e:
            self.err.configure(text=f"Couldn't add it: {e}")
            return
        self.destroy()
        self.hub.fill_grid(force=True)
        self.hub._build_status()


def launch(args: List[str]) -> None:
    if "--install-update" in args:          # this is the new version installing itself; no window
        i = args.index("--install-update")
        core.install_update_helper(int(args[i + 1]), Path(args[i + 2]))
        return
    if core.IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Danielb1606.DansWorkshop")
        except Exception:
            pass
        if not core.single_instance():
            return
    core.DATA_DIR.mkdir(parents=True, exist_ok=True)
    core.APPS_DIR.mkdir(parents=True, exist_ok=True)
    msg = core.hub_startup(args)
    root = tk.Tk()
    try:
        root.iconbitmap(default=str(core.ASSETS / "icon.ico"))
    except tk.TclError:
        pass
    try:
        # sharp taskbar/title icons: give Windows every size instead of letting it stretch 16 px
        root._icons = [tk.PhotoImage(file=str(core.ASSETS / n)) for n in ("icon.png", "icon48.png", "icon32.png", "icon16.png")]
        root.iconphoto(True, *root._icons)
    except tk.TclError:
        pass
    scale = root.winfo_fpixels("1i") / 96
    w, h = round(1040 * scale), round(700 * scale)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(w, sw - 40), min(h, sh - 80)
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
    Hub(root, msg)
    root.mainloop()
