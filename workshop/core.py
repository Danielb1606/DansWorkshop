r"""Dan's Workshop - everything that isn't drawing the window.

Layout on disk (everything lives in one portable folder):

    Dan's Workshop\
        Dan's Workshop.exe
        _internal\              program files (PyInstaller one-folder build)
        apps\<App folder>\       each app, with its own saved data
        workshop_data\           hub settings, activity log, card pictures
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

__version__ = "1.3.4"
APP_NAME = "Dan's Workshop"
EXE_NAME = "Dan's Workshop.exe"
HUB_REPO = "Danielb1606/DansWorkshop"
HUB_ASSET = "DansWorkshop.zip"
TASK_NAME = "Dan's Workshop"
UA = {"User-Agent": "DansWorkshop"}
IS_WIN = sys.platform == "win32"


# ----------------------------------------------------------------------------- paths

def _base_dir() -> Path:
    if os.environ.get("DW_BASE"):
        return Path(os.environ["DW_BASE"])
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent / "_dev_workshop"


BASE = _base_dir()
APPS_DIR = BASE / "apps"
DATA_DIR = BASE / "workshop_data"
ART_DIR = DATA_DIR / "art"
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"
NOTES_DIR = BASE / "notes"
BACKUP_DIR = BASE / "backups" / "Obsidian"


def set_base(path: Path) -> None:
    """Point everything at another Workshop folder (used by the tests)."""
    global BASE, APPS_DIR, DATA_DIR, ART_DIR, NOTES_DIR, BACKUP_DIR
    BASE = Path(path)
    APPS_DIR, DATA_DIR = BASE / "apps", BASE / "workshop_data"
    ART_DIR = DATA_DIR / "art"
    NOTES_DIR, BACKUP_DIR = BASE / "notes", BASE / "backups" / "Obsidian"


def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def appdata() -> Path:
    return Path(os.environ.get("APPDATA") or (home() / "AppData" / "Roaming"))


# ----------------------------------------------------------------------------- json helpers

def read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def ver_tuple(v: str) -> Tuple[int, ...]:
    out = []
    for p in str(v or "0").strip().lstrip("vV").split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        out.append(int(num) if num else 0)
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return tuple(out)


def newer(a: str, b: str) -> bool:
    """True if version a is newer than b."""
    return ver_tuple(a) > ver_tuple(b)


# ----------------------------------------------------------------------------- settings

DEFAULT_SETTINGS = {
    "after_launch": "keep",          # keep | minimise | close
    "accent": "gold",
    "check_on_open": True,
    "task_path": "",                 # exe path the no-prompt task was made for
    "shortcut_done": False,
    "welcome_name": "Dan",
}

ACCENTS = {
    "gold": ("#c9a24a", "#dcb76a"),
    "blue": ("#5fa8e8", "#86bff0"),
    "green": ("#4cc38a", "#72d3a4"),
    "rose": ("#d9776b", "#e5978d"),
    "violet": ("#9a86e0", "#b3a3ea"),
}


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update(read_json(DATA_DIR / "settings.json", {}))
    if s.get("accent") not in ACCENTS:
        s["accent"] = "gold"
    if s.get("after_launch") not in ("keep", "minimise", "close"):
        s["after_launch"] = "keep"
    return s


def save_settings(s: dict) -> None:
    write_json(DATA_DIR / "settings.json", s)


# ----------------------------------------------------------------------------- the apps

@dataclass
class AppDef:
    id: str
    name: str
    folder: str                         # folder name inside apps\
    exe: str                            # exe file name (must never be renamed)
    kind: str = "custom"                # neutralino | github-exe | custom
    repo: str = ""                      # owner/repo for notes and "request a change"
    asset: str = ""                     # github-exe: release asset name
    update_urls: List[str] = field(default_factory=list)   # neutralino: update.json
    import_from: str = ""               # where the old copy usually lives
    import_skip: List[str] = field(default_factory=list)
    appdata_profile: str = ""           # neutralino: browser data to bring in
    portable_profile: bool = False      # point the browser data at apps\<folder>\profile
    colour: str = "#2a2f38"
    blurb: str = ""
    external: List[str] = field(default_factory=list)   # installed elsewhere: possible exe paths (linked, not copied)
    play_label: str = "Play"
    initials: str = ""
    icon: str = ""                      # assets/<icon>: shown on the tile instead of a screenshot
    actions: List[Tuple[str, str]] = field(default_factory=list)   # extra (label, file) on the card menu

    @property
    def dir(self) -> Path:
        if self.external:
            return self.exe_path.parent
        return APPS_DIR / self.folder

    @property
    def exe_path(self) -> Path:
        if self.external:
            for c in self.external:
                p = expand(c)
                if p.is_file():
                    return p
            return expand(self.external[0])
        return self.dir / self.exe

    @property
    def installed(self) -> bool:
        return self.exe_path.is_file()

    @property
    def profile_dir(self) -> Path:
        return self.dir / "profile"


BUILTIN = [
    AppDef(
        id="poker-trainer", name="Poker Trainer", folder="Poker Trainer",
        exe="Poker Trainer Dev.exe", kind="neutralino", repo="Danielb1606/PokerTrainer",
        update_urls=["https://danielb1606.github.io/PokerTrainer/win/update.json",
                     "https://raw.githubusercontent.com/Danielb1606/PokerTrainer/main/win/update.json"],
        import_from=r"%USERPROFILE%\Desktop\Poker Trainer",
        import_skip=["overlay misses", "*.new", "resources.neu.new"],
        appdata_profile=r"%APPDATA%\Poker Trainer Dev.exe",
        portable_profile=True, colour="#24463a",
        blurb="Ranges, drills and the table reader."),
    AppDef(
        id="daniels-assignment", name="Daniels Assignment", folder="Daniels Assignment",
        exe="DanielsAssignment.exe", kind="github-exe", repo="Danielb1606/DanielsAssignment",
        asset="DanielsAssignment.exe", icon="app_daniels-assignment.png",
        import_from=r"%USERPROFILE%\Desktop\GamingProgram",
        import_skip=["*.old.exe", "*.new.exe", "*.failed.exe", "*-report-*.zip"],
        colour="#26364a", blurb="Flask automation for the PoE-style UI."),
    AppDef(
        id="deadlock-config", name="Deadlock Auto Config", folder="Deadlock Auto Config",
        exe="Apply Deadlock Settings.bat", kind="script", play_label="Apply settings", initials="DL",
        icon="app_deadlock-config.png",
        actions=[("Save my current in-game settings", "Save My Current In-Game Settings.bat"),
                 ("Change aspect ratio", "Change Aspect Ratio.bat")],
        import_from=r"%USERPROFILE%\Desktop\Deadlock config files\Deadlock Auto Config",
        colour="#3a2a22", blurb="Puts your Deadlock settings and mods back after a patch."),
    AppDef(
        id="obsidian", name="Obsidian", folder="", exe="Obsidian.exe", kind="external",
        external=[r"%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe", r"%PROGRAMFILES%\Obsidian\Obsidian.exe",
                  r"%LOCALAPPDATA%\Obsidian\Obsidian.exe"],
        colour="#2e2640", blurb="Your notes."),
]


def expand(p: str) -> Path:
    if not p:
        return Path()
    local = Path(os.environ.get("LOCALAPPDATA") or (home() / "AppData" / "Local"))
    progs = Path(os.environ.get("PROGRAMFILES") or r"C:\Program Files")
    for var, val in (("%USERPROFILE%", home()), ("%APPDATA%", appdata()), ("%LOCALAPPDATA%", local),
                     ("%PROGRAMFILES%", progs)):
        if p.startswith(var):
            return Path(val).joinpath(*[x for x in p[len(var):].split("\\") if x])
    return Path(os.path.expandvars(p))


def load_state() -> dict:
    st = read_json(DATA_DIR / "state.json", {})
    st.setdefault("apps", {})
    st.setdefault("custom", [])
    return st


def save_state(st: dict) -> None:
    write_json(DATA_DIR / "state.json", st)


def all_apps(state: Optional[dict] = None) -> List[AppDef]:
    state = state if state is not None else load_state()
    apps = [a for a in BUILTIN if not a.external or a.installed or (a.id == "obsidian" and workshop_vaults())]
    for c in state.get("custom", []):
        try:
            apps.append(AppDef(id=c["id"], name=c["name"], folder=c["folder"], exe=c["exe"],
                               kind="custom", colour=c.get("colour", "#2f2a3a")))
        except KeyError:
            pass
    return apps


def app_state(state: dict, app_id: str) -> dict:
    return state["apps"].setdefault(app_id, {})


# ----------------------------------------------------------------------------- activity

def log_activity(app_name: str, event: str, when: Optional[float] = None) -> None:
    path = DATA_DIR / "activity.json"
    items = read_json(path, [])
    items.append({"t": when or time.time(), "app": app_name, "event": event})
    write_json(path, items[-2000:])


def activity() -> List[dict]:
    return sorted(read_json(DATA_DIR / "activity.json", []), key=lambda x: -x.get("t", 0))


def clear_activity() -> None:
    write_json(DATA_DIR / "activity.json", [])


def nice_time(t: float) -> str:
    lt = time.localtime(t)
    h = lt.tm_hour % 12 or 12
    return f"{h}:{lt.tm_min:02d} {'am' if lt.tm_hour < 12 else 'pm'}"


def nice_date(t: float, now: Optional[float] = None) -> str:
    now = now or time.time()
    d, n = time.localtime(t), time.localtime(now)
    if (d.tm_year, d.tm_yday) == (n.tm_year, n.tm_yday):
        return "Today"
    y = time.localtime(now - 86400)
    if (d.tm_year, d.tm_yday) == (y.tm_year, y.tm_yday):
        return "Yesterday"
    return time.strftime("%A %d %B %Y", d).replace(" 0", " ")


def ago(t: Optional[float], now: Optional[float] = None) -> str:
    if not t:
        return "never"
    s = max(0, int((now or time.time()) - t))
    if s < 60:
        return "just now"
    if s < 3600:
        m = s // 60
        return f"{m} min ago"
    if s < 86400:
        h = s // 3600
        return f"{h} hour{'s' if h > 1 else ''} ago"
    d = s // 86400
    return "yesterday" if d == 1 else f"{d} days ago"


# ----------------------------------------------------------------------------- versions

def neu_version(path: Path) -> str:
    """Version inside a Neutralino resources.neu (an asar archive)."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
            hsize = struct.unpack("<I", head[12:16])[0]
            header = json.loads(f.read(hsize))
            base = 8 + struct.unpack("<I", head[4:8])[0]
            entry = header["files"]["neutralino.config.json"]
            f.seek(base + int(entry["offset"]))
            cfg = json.loads(f.read(int(entry["size"])))
        return str(cfg.get("version", ""))
    except (OSError, ValueError, KeyError, struct.error):
        return ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def http_json(url: str, timeout: float = 10):
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def github_releases(repo: str) -> List[dict]:
    return http_json(f"https://api.github.com/repos/{repo}/releases?per_page=40")


def match_release_by_size(releases: List[dict], asset: str, size: int) -> str:
    """Work out which release an exe came from by its exact size."""
    for rel in releases:
        for a in rel.get("assets", []):
            if a.get("name") == asset and int(a.get("size") or -1) == size:
                return str(rel.get("tag_name", "")).lstrip("vV")
    return ""


def installed_version(app: AppDef, state: dict, releases: Optional[List[dict]] = None) -> str:
    """Version of the installed copy. Cheap: cached against the exe's size and time."""
    if not app.installed:
        return ""
    st = app_state(state, app.id)
    if app.kind == "neutralino":
        res = app.dir / "resources.neu"
        try:
            key = f"{res.stat().st_size}:{int(res.stat().st_mtime)}"
        except OSError:
            return ""
        if st.get("ver_key") != key:
            st["version"], st["ver_key"] = neu_version(res), key
        return st.get("version", "")
    if app.kind == "github-exe":
        exe = app.exe_path
        key = f"{exe.stat().st_size}:{int(exe.stat().st_mtime)}"
        if st.get("ver_key") != key:
            if releases is None:
                return st.get("version", "")           # don't know yet; caller fetches
            v = match_release_by_size(releases, app.asset, exe.stat().st_size)
            st["version"], st["ver_key"] = v, key
        return st.get("version", "")
    return st.get("version", "")


@dataclass
class UpdateInfo:
    version: str
    notes: str = ""
    url: str = ""
    size: int = 0
    sha256: str = ""


def latest_for(app: AppDef, releases: Optional[List[dict]] = None) -> Optional[UpdateInfo]:
    """Newest available version of an app (None if it can't be checked)."""
    if app.kind == "neutralino":
        for u in app.update_urls:
            try:
                d = http_json(u)
            except Exception:
                continue
            res = d.get("resourcesURL", "resources.neu")
            if not res.startswith("http"):
                res = u.rsplit("/", 1)[0] + "/" + res
            return UpdateInfo(str(d.get("version", "")), d.get("notes", ""), res, 0, d.get("sha256", ""))
        return None
    if app.kind == "github-exe":
        rels = releases if releases is not None else github_releases(app.repo)
        for rel in rels:
            if rel.get("draft") or rel.get("prerelease"):
                continue
            a = next((x for x in rel.get("assets", []) if x.get("name") == app.asset), None)
            if a:
                return UpdateInfo(str(rel.get("tag_name", "")).lstrip("vV"), (rel.get("body") or "").strip(),
                                  a["browser_download_url"], int(a.get("size") or 0))
        return None
    return None


def download(url: str, dest: Path, size: int = 0, sha256: str = "",
             progress: Callable[[float], None] = lambda f: None) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or size or 0)
        done = 0
        while chunk := r.read(1 << 16):
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if total:
                progress(min(1.0, done / total))
    got = dest.stat().st_size
    if (size and got != size) or (sha256 and h.hexdigest() != sha256.lower()) or got < 1000:
        dest.unlink(missing_ok=True)
        raise RuntimeError("the download was damaged or incomplete - try again")


def install_update(app: AppDef, info: UpdateInfo, progress=lambda f: None) -> None:
    """Put a new version in place. The app must be closed."""
    if app.kind == "github-exe":
        new = app.exe_path.with_suffix(".new.exe")
        download(info.url, new, info.size, "", progress)
        old = app.exe_path.with_suffix(".old.exe")
        old.unlink(missing_ok=True)
        if app.exe_path.exists():
            os.replace(app.exe_path, old)
        os.replace(new, app.exe_path)
        try:
            old.unlink()
        except OSError:
            pass
    elif app.kind == "neutralino":
        res = app.dir / "resources.neu"
        new = app.dir / "resources.neu.download"
        download(info.url, new, 0, info.sha256, progress)
        if res.exists():
            shutil.copy2(res, app.dir / "resources.neu.bak")      # same rollback copy the app keeps
        os.replace(new, res)
    else:
        raise RuntimeError("this app doesn't have automatic updates")


# ----------------------------------------------------------------------------- bringing apps in

def _skipped(rel: str, patterns: List[str]) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return any(fnmatch.fnmatch(parts[0], p) or fnmatch.fnmatch(parts[-1], p) for p in patterns)


def copy_tree(src: Path, dst: Path, skip: List[str] = (), progress=lambda f, name: None) -> int:
    """Copy a folder, skipping patterns. Files already there are overwritten. Returns files copied."""
    src, dst = Path(src), Path(dst)
    files = []
    for root, dirs, names in os.walk(src):
        rel_root = os.path.relpath(root, src)
        dirs[:] = [d for d in dirs if not _skipped(os.path.normpath(os.path.join(rel_root, d)).lstrip(".\\/"), skip)]
        for n in names:
            rel = os.path.normpath(os.path.join(rel_root, n))
            rel = rel[2:] if rel.startswith("." + os.sep) else rel
            if not _skipped(rel, skip):
                files.append(rel)
    for i, rel in enumerate(files):
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src / rel, target)
        except OSError:
            # browser caches often hold locked or odd files; they aren't needed
            if not any(x in rel.lower() for x in ("cache", "lock", "crashpad", "log")):
                raise
        progress((i + 1) / max(1, len(files)), rel)
    return len(files)


def import_candidates(state: Optional[dict] = None) -> List[Tuple[AppDef, Path]]:
    out = []
    for app in all_apps(state):
        src = expand(app.import_from)
        if app.import_from and not app.installed and (src / app.exe).is_file():
            out.append((app, src))
    return out


def import_app(app: AppDef, src: Path, progress=lambda f, name: None) -> str:
    """Copy an existing app (and its saved data) into the Workshop. The original
    is left untouched as a backup. Returns a short note for the user."""
    note = ""
    copy_tree(src, app.dir, app.import_skip, progress)
    if app.portable_profile and app.appdata_profile:
        prof = expand(app.appdata_profile)
        if prof.is_dir() and not app.profile_dir.exists():
            copy_tree(prof, app.profile_dir, ["Crashpad", "*.lock", "lockfile"], progress)
            note = "saved profiles brought in"
        else:
            app.profile_dir.mkdir(parents=True, exist_ok=True)
    return note


def add_custom_app(name: str, exe: Path, copy_in: bool, state: dict) -> AppDef:
    exe = Path(exe)
    base_id = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-") or "app"
    ids = {a.id for a in all_apps(state)}
    app_id, n = base_id, 2
    while app_id in ids:
        app_id, n = f"{base_id}-{n}", n + 1
    if copy_in:
        folder = name.strip() or exe.stem
        for ch in '<>:"/\\|?*':
            folder = folder.replace(ch, "")
        if (APPS_DIR / folder).exists():
            folder = f"{folder} ({app_id})"
        copy_tree(exe.parent, APPS_DIR / folder)
        rec = {"id": app_id, "name": name, "folder": folder, "exe": exe.name}
    else:
        # outside the Workshop: keep a relative-looking folder entry pointing outside
        rec = {"id": app_id, "name": name, "folder": os.path.relpath(exe.parent, APPS_DIR), "exe": exe.name}
    palette = ["#3a2f4a", "#4a3a2a", "#2a4a46", "#4a2a33", "#33402a"]
    rec["colour"] = palette[len(state["custom"]) % len(palette)]
    state["custom"].append(rec)
    save_state(state)
    return next(a for a in all_apps(state) if a.id == app_id)


def remove_custom_app(app_id: str, state: dict) -> None:
    state["custom"] = [c for c in state["custom"] if c.get("id") != app_id]
    state["apps"].pop(app_id, None)
    save_state(state)


# ----------------------------------------------------------------------------- launching

def clean_env() -> dict:
    """Environment for starting other programs without PyInstaller leftovers."""
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith("_MEI") or k.startswith("_PYI") or k in ("PYINSTALLER_RESET_ENVIRONMENT", "TCL_LIBRARY", "TK_LIBRARY"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def launch_env(app: AppDef) -> dict:
    env = clean_env()
    if app.portable_profile:
        app.profile_dir.mkdir(parents=True, exist_ok=True)
        # WebView2 (the browser engine Poker Trainer runs on) keeps its saved
        # data here instead of AppData. Also reaches its own update restarter.
        env["WEBVIEW2_USER_DATA_FOLDER"] = str(app.profile_dir)
    return env


def launch(app: AppDef, vault: str = ""):
    if not app.installed:
        raise RuntimeError(f"{app.name} isn't installed")
    if app.external:
        launch_as_user(obsidian_link(vault_path(vault)) if vault else str(app.exe_path))
        return None
    if app.kind == "script":
        return run_script(app, app.exe)
    flags = 0
    if IS_WIN:
        flags = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([str(app.exe_path)], cwd=str(app.dir), env=launch_env(app),
                            creationflags=flags, close_fds=True)


def run_script(app: AppDef, file: str) -> subprocess.Popen:
    """Run one of a script app's .bat files in its own console window (it shows
    what it did and waits for a key, like double-clicking it)."""
    path = app.dir / file
    if not path.is_file():
        raise RuntimeError(f"{file} is missing from {app.dir}")
    flags = 0x00000010 if IS_WIN else 0                  # CREATE_NEW_CONSOLE
    return subprocess.Popen(["cmd", "/c", str(path)] if IS_WIN else ["sh", str(path)], cwd=str(app.dir),
                            env=clean_env(), creationflags=flags)


def launch_as_user(target: str) -> None:
    """Start a program or link as the normal (not administrator) user. Explorer
    runs un-elevated, so whatever it starts does too."""
    if IS_WIN:
        subprocess.Popen(["explorer.exe", target], creationflags=0x08000000, close_fds=True)
    else:
        subprocess.Popen(["xdg-open", target])


def obsidian_vaults() -> List[dict]:
    """Vaults Obsidian knows about: [{'name', 'path', 'open'}], most recently used first."""
    d = read_json(appdata() / "obsidian" / "obsidian.json", {})
    out = []
    for v in (d.get("vaults") or {}).values():
        p = v.get("path")
        if p:
            out.append({"name": Path(p).name, "path": p, "open": bool(v.get("open")), "ts": v.get("ts", 0)})
    return sorted(out, key=lambda v: -v["ts"])


# ----------------------------------------------------------------------------- Obsidian notes in the Workshop

OBSIDIAN_JSON = lambda: appdata() / "obsidian" / "obsidian.json"
KEEP_BACKUPS = 20
WS_PREFIX = "workshop:"          # vault paths stored relative to the Workshop, so they survive moving PC


def workshop_vaults() -> List[Path]:
    if not NOTES_DIR.is_dir():
        return []
    return sorted(p for p in NOTES_DIR.iterdir() if p.is_dir())


def vault_path(stored: str) -> str:
    """Turn a stored vault ('workshop:Name' or an absolute path) into a real path."""
    if stored.startswith(WS_PREFIX):
        return str(NOTES_DIR / stored[len(WS_PREFIX):])
    return stored


def stored_vault(path: str) -> str:
    p = Path(path)
    try:
        if p.resolve().parent == NOTES_DIR.resolve():
            return WS_PREFIX + p.name
    except OSError:
        pass
    return str(p)


def vault_warnings(path: str) -> List[str]:
    """Reasons moving this vault could break something it relies on."""
    out = []
    low = str(path).lower()
    if "onedrive" in low or "dropbox" in low or "google drive" in low or "icloud" in low:
        out.append("it's in a cloud-synced folder (it syncs to your other devices from there)")
    core_plugins = read_json(Path(path) / ".obsidian" / "core-plugins.json", None)
    if (isinstance(core_plugins, list) and "sync" in core_plugins) or \
            (isinstance(core_plugins, dict) and core_plugins.get("sync")):
        out.append("Obsidian Sync is turned on for it")
    if (Path(path) / ".git").is_dir():
        out.append("it's a git repository")
    return out


def move_vault_in(path: str, progress=lambda f, name: None) -> Path:
    """Copy a vault into the Workshop notes folder and point Obsidian at the copy.
    The original folder is left as it is (a backup until you delete it)."""
    src = Path(path)
    if not src.is_dir():
        raise RuntimeError("that vault's folder doesn't exist any more")
    dst = NOTES_DIR / src.name
    n = 2
    while dst.exists():
        dst, n = NOTES_DIR / f"{src.name} ({n})", n + 1
    copy_tree(src, dst, [".trash"], progress)
    # check the copy is complete before switching Obsidian over
    def count(folder):
        n = 0
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d != ".trash"]
            n += len(files)
        return n
    if count(dst) < count(src):
        raise RuntimeError("not every file copied (is something open or locked?) - nothing was switched over")
    replace_vault_in_obsidian(str(src), str(dst))
    return dst


def _vault_id() -> str:
    import secrets
    return secrets.token_hex(8)


def replace_vault_in_obsidian(old: str, new: str) -> None:
    """Swap a vault's location in Obsidian's own vault list. Obsidian must be closed."""
    path = OBSIDIAN_JSON()
    d = read_json(path, {})
    vaults = d.setdefault("vaults", {})
    vid = next((k for k, v in vaults.items() if os.path.normcase(v.get("path", "")) == os.path.normcase(old)), None)
    entry = vaults.pop(vid, {}) if vid else {}
    entry.update(path=new, ts=int(time.time() * 1000), open=True)
    for v in vaults.values():
        v.pop("open", None)
    vaults[vid or _vault_id()] = entry
    write_json(path, d)


def register_workshop_vaults() -> int:
    """Make sure Obsidian on this PC knows about the vaults in the Workshop
    (e.g. after copying the Workshop to another PC). Obsidian must be closed."""
    vs = workshop_vaults()
    if not vs:
        return 0
    path = OBSIDIAN_JSON()
    d = read_json(path, {})
    vaults = d.setdefault("vaults", {})
    known = {os.path.normcase(v.get("path", "")) for v in vaults.values()}
    added = 0
    for v in vs:
        if os.path.normcase(str(v)) not in known:
            vaults[_vault_id()] = {"path": str(v), "ts": int(time.time() * 1000)}
            added += 1
    # a Workshop that moved leaves entries pointing at folders that no longer exist; drop those that were ours
    for k in [k for k, v in vaults.items() if v.get("path") and not Path(v["path"]).exists()
              and Path(v["path"]).parent.name == "notes"]:
        vaults.pop(k)
    if added or not path.exists():
        write_json(path, d)
    return added


def _latest_change(folder: Path) -> float:
    latest = 0.0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != ".trash"]
        for f in files:
            try:
                latest = max(latest, os.path.getmtime(os.path.join(root, f)))
            except OSError:
                pass
    return latest


def backup_vault(path: str, force: bool = False) -> Optional[Path]:
    """Zip a vault into the Workshop backups folder (backups/Obsidian/<vault>). Skips it when
    nothing changed since the last backup. Keeps the newest KEEP_BACKUPS."""
    import zipfile
    src = Path(path)
    if not src.is_dir():
        return None
    folder = BACKUP_DIR / src.name
    existing = list_backups(src.name)
    if existing and not force and _latest_change(src) <= existing[0].stat().st_mtime:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H%M%S")
    out = folder / f"{src.name} {stamp}.zip"
    tmp = out.with_suffix(".zip.part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d != ".trash"]
            for f in files:
                full = Path(root) / f
                try:
                    z.write(full, full.relative_to(src))
                except OSError:
                    pass                      # a file being written right now; next backup gets it
    os.replace(tmp, out)
    for old in list_backups(src.name)[KEEP_BACKUPS:]:
        try:
            old.unlink()
        except OSError:
            pass
    return out


def list_backups(vault_name: str) -> List[Path]:
    folder = BACKUP_DIR / vault_name
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.zip"), key=lambda p: -p.stat().st_mtime)


def restore_backup(zip_path: Path, vault: str) -> Path:
    """Put a backup back. The current vault folder is kept next to it, renamed."""
    import zipfile
    target = Path(vault)
    if target.exists():
        keep = target.with_name(f"{target.name} (before restore {time.strftime('%Y-%m-%d %H%M')})")
        os.replace(target, keep)
    target.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(target)
    return target


def obsidian_installer() -> Optional[UpdateInfo]:
    """Latest Obsidian installer for Windows, from Obsidian's own GitHub releases."""
    d = http_json("https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest")
    a = next((x for x in d.get("assets", []) if x.get("name", "").lower().endswith(".exe")
              and "arm64" not in x["name"].lower() and "32" not in x["name"]), None)
    if not a:
        return None
    return UpdateInfo(str(d.get("tag_name", "")).lstrip("vV"), "", a["browser_download_url"], int(a.get("size") or 0))


def obsidian_link(vault_path: str) -> str:
    from urllib.parse import quote
    return "obsidian://open?path=" + quote(vault_path, safe="")


def open_folder(path: Path) -> None:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        os.startfile(str(path))                    # noqa: S606 - opens Explorer
    else:
        subprocess.Popen(["xdg-open", str(path)])


def change_brief(app: AppDef, version: str) -> str:
    lines = [f"I'd like a change to my app \"{app.name}\" (it's one of the apps in Dan's Workshop)."]
    if app.repo:
        lines.append(f"Code: https://github.com/{app.repo} - read CLAUDE.md there first, it has everything about the app.")
    elif app.kind == "script":
        lines.append("It's a set of scripts (no repo): they're in the folder below - README.txt explains them.")
    lines.append(f"Installed version: {version or 'unknown'}")
    lines.append(f"Folder on my PC: {app.dir}")
    lines.append("")
    lines.append("The change I want: ")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- Windows bits

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _psapi = ctypes.WinDLL("psapi", use_last_error=True)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def running_pids() -> Dict[str, List[int]]:
    """{lower-case exe path: [pids]} for every process we can see."""
    out: Dict[str, List[int]] = {}
    if not IS_WIN:
        return out
    arr = (wintypes.DWORD * 4096)()
    needed = wintypes.DWORD()
    if not _psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)):
        return out
    buf = ctypes.create_unicode_buffer(1024)
    for pid in arr[: needed.value // ctypes.sizeof(wintypes.DWORD)]:
        if not pid:
            continue
        h = _k32.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            size = wintypes.DWORD(len(buf))
            if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                out.setdefault(buf.value.lower(), []).append(int(pid))
        finally:
            _k32.CloseHandle(h)
    return out


def pids_for(app: AppDef, procs: Dict[str, List[int]]) -> List[int]:
    try:
        key = str(app.exe_path.resolve()).lower()
    except OSError:
        key = str(app.exe_path).lower()
    return procs.get(key, [])


def main_window(pids: List[int]) -> Optional[int]:
    """Biggest visible titled window belonging to these processes."""
    if not IS_WIN or not pids:
        return None
    best = [None, 0]
    want = set(pids)

    def cb(hwnd, _):
        if not _u32.IsWindowVisible(hwnd) or _u32.GetWindowTextLengthW(hwnd) == 0:
            return True
        pid = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in want:
            r = wintypes.RECT()
            _u32.GetWindowRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best[1]:
                best[0], best[1] = hwnd, area
        return True

    _u32.EnumWindows(WNDENUMPROC(cb), 0)
    return best[0]


def bring_to_front(hwnd: int) -> None:
    if not IS_WIN or not hwnd:
        return
    if _u32.IsIconic(hwnd):
        _u32.ShowWindow(hwnd, 9)                            # SW_RESTORE
    _u32.keybd_event(0x12, 0, 0, 0)                         # tap Alt so Windows allows the switch
    _u32.keybd_event(0x12, 0, 2, 0)
    _u32.SetForegroundWindow(hwnd)


def foreground_pid() -> int:
    if not IS_WIN:
        return 0
    pid = wintypes.DWORD()
    _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value


def client_box(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    if not IS_WIN or not hwnd or _u32.IsIconic(hwnd):
        return None
    r = wintypes.RECT()
    if not _u32.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    pt = wintypes.POINT(0, 0)
    _u32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = r.right - r.left, r.bottom - r.top
    if w < 400 or h < 300:
        return None
    return pt.x, pt.y, pt.x + w, pt.y + h


def capture_art(app: AppDef, box: Tuple[int, int, int, int]) -> bool:
    """Save a picture of the app's window to use as its card art."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")
    except Exception:
        return False
    if img.width < 50:
        return False
    if img.width > 1280:
        img = img.resize((1280, round(img.height * 1280 / img.width)))
    ART_DIR.mkdir(parents=True, exist_ok=True)
    img.save(ART_DIR / f"{app.id}.png")
    return True


def set_custom_art(app: AppDef, picture: Path) -> None:
    from PIL import Image
    img = Image.open(picture).convert("RGB")
    if img.width > 1280:
        img = img.resize((1280, round(img.height * 1280 / img.width)))
    ART_DIR.mkdir(parents=True, exist_ok=True)
    img.save(ART_DIR / f"{app.id}.png")


def neu_file(path: Path, name: str) -> Optional[bytes]:
    """Read one file out of a Neutralino resources.neu, e.g. 'resources/icons/appIcon.png'."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
            header = json.loads(f.read(struct.unpack("<I", head[12:16])[0]))
            base = 8 + struct.unpack("<I", head[4:8])[0]
            node = header
            for part in name.strip("/").split("/"):
                node = node["files"][part]
            f.seek(base + int(node["offset"]))
            return f.read(int(node["size"]))
    except (OSError, ValueError, KeyError, struct.error):
        return None


def exe_icon(exe: Path, size: int = 256):
    """The icon built into a Windows program, as a picture (None if it has none)."""
    if not IS_WIN:
        return None
    from PIL import Image

    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    gdi = ctypes.WinDLL("gdi32")
    hicon = wintypes.HICON()
    got = _u32.PrivateExtractIconsW(str(exe), 0, size, size, ctypes.byref(hicon), None, 1, 0)
    if got < 1 or not hicon:
        return None
    info = ICONINFO()
    try:
        if not _u32.GetIconInfo(hicon, ctypes.byref(info)):
            return None
        bmi = BITMAPINFOHEADER()
        bmi.biSize, bmi.biWidth, bmi.biHeight = ctypes.sizeof(BITMAPINFOHEADER), size, -size
        bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
        buf = ctypes.create_string_buffer(size * size * 4)
        hdc = _u32.GetDC(None)
        try:
            lines = gdi.GetDIBits(hdc, info.hbmColor, 0, size, buf, ctypes.byref(bmi), 0)
        finally:
            _u32.ReleaseDC(None, hdc)
        if lines != size:
            return None
        img = Image.frombuffer("RGBA", (size, size), buf.raw, "raw", "BGRA", 0, 1)
        if img.getchannel("A").getextrema()[1] == 0:          # old-style icon without alpha
            img.putalpha(255)
        return img.copy()
    finally:
        for h in (info.hbmColor, info.hbmMask):
            if h:
                gdi.DeleteObject(h)
        _u32.DestroyIcon(hicon)


def app_icon(app: AppDef) -> Optional[Path]:
    """The picture the app uses as its own (taskbar) icon, for its tile. Kept up to
    date: re-read when the app's files change."""
    if app.icon:
        p = ASSETS / app.icon
        return p if p.is_file() else None
    if not app.installed:
        return None
    out = ART_DIR / f"{app.id}_icon.png"
    if app.kind == "neutralino":
        src = app.dir / "resources.neu"
    elif app.kind in ("external", "custom") and app.exe_path.suffix.lower() == ".exe":
        src = app.exe_path
    else:
        return None
    try:
        if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime:
            return out
    except OSError:
        return None
    try:
        ART_DIR.mkdir(parents=True, exist_ok=True)
        if app.kind == "neutralino":
            cfg = json.loads(neu_file(src, "neutralino.config.json") or b"{}")
            icon = ((cfg.get("modes") or {}).get("window") or {}).get("icon") or "/resources/icons/appIcon.png"
            data = neu_file(src, icon)
            if not data:
                return None
            out.write_bytes(data)
        else:
            img = exe_icon(src)
            if img is None:
                return None
            img.save(out)
    except Exception:
        return None
    return out


def art_path(app: AppDef) -> Optional[Path]:
    p = ART_DIR / f"{app.id}.png"
    return p if p.is_file() else None


def is_admin() -> bool:
    if not IS_WIN:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def single_instance() -> bool:
    """False if the hub is already open (and brings that one to the front)."""
    if not IS_WIN:
        return True
    _k32.CreateMutexW(None, False, "Local\\DansWorkshopHub")
    if ctypes.get_last_error() == 183:                       # ERROR_ALREADY_EXISTS
        hwnd = _u32.FindWindowW(None, APP_NAME)
        if hwnd:
            bring_to_front(hwnd)
        return False
    return True


def task_xml(exe: Path) -> str:
    """Scheduled task that starts the hub as administrator without a prompt."""
    import getpass
    from xml.sax.saxutils import escape
    user = os.environ.get("USERDOMAIN", "") + "\\" + (os.environ.get("USERNAME") or getpass.getuser())
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Opens Dan's Workshop as administrator without the Windows prompt.</Description></RegistrationInfo>
  <Principals><Principal id="Author"><UserId>{escape(user)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>Parallel</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>4</Priority>
  </Settings>
  <Actions Context="Author"><Exec><Command>"{escape(str(exe))}"</Command><WorkingDirectory>{escape(str(exe.parent))}</WorkingDirectory></Exec></Actions>
</Task>
"""


def _run_hidden(args: List[str], timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=0x08000000 if IS_WIN else 0)      # CREATE_NO_WINDOW


def setup_no_prompt(exe: Path) -> Tuple[bool, str]:
    """Register the scheduled task and make the desktop shortcut use it."""
    if not IS_WIN:
        return False, "only on Windows"
    if not is_admin():
        return False, "the hub needs to be running as administrator to set this up"
    xml = DATA_DIR / "task.xml"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    xml.write_text(task_xml(exe), encoding="utf-16")
    r = _run_hidden(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml), "/F"])
    xml.unlink(missing_ok=True)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip() or "Windows refused to make the task"
    ok, msg = make_shortcut(exe)
    return ok, msg


def desktop_dir() -> Path:
    if IS_WIN:
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)     # CSIDL_DESKTOPDIRECTORY
            if buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return home() / "Desktop"


ICON_REV = 2          # bump when the Workshop's icon changes: shortcuts and Windows' icon cache get refreshed


def pinned_shortcut() -> Path:
    return appdata() / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar" / f"{APP_NAME}.lnk"


def refresh_icons(exe: Path) -> None:
    """Re-save the desktop and pinned taskbar shortcuts and ask Windows to reload
    its icon cache, so a new icon shows instead of the old cached one."""
    for lnk in (desktop_dir() / f"{APP_NAME}.lnk", pinned_shortcut()):
        if lnk.exists():
            make_shortcut(exe, lnk)
    try:
        _run_hidden(["ie4uinit.exe", "-show"], timeout=15)
    except Exception:
        pass


def make_shortcut(exe: Path, lnk: Optional[Path] = None) -> Tuple[bool, str]:
    lnk = lnk or desktop_dir() / f"{APP_NAME}.lnk"
    schtasks = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "schtasks.exe"
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + q(lnk) + ");"
          f"$s.TargetPath={q(schtasks)};"
          f"$s.Arguments={q('/run /tn ' + chr(34) + TASK_NAME + chr(34))};"
          f"$s.IconLocation={q(str(exe) + ',0')};"
          f"$s.WorkingDirectory={q(exe.parent)};"
          "$s.WindowStyle=7;"
          f"$s.Description={q('Open ' + APP_NAME)};"
          "$s.Save()")
    r = _run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
    if r.returncode != 0 or not lnk.exists():
        return False, (r.stderr or "couldn't make the shortcut").strip()
    return True, str(lnk)


def task_ok(settings: dict, exe: Path) -> bool:
    if not IS_WIN:
        return False
    if settings.get("task_path") != str(exe):
        return False
    r = _run_hidden(["schtasks", "/Query", "/TN", TASK_NAME], timeout=10)
    return r.returncode == 0


# ----------------------------------------------------------------------------- hub self-update

UPDATE_DIR_NAME = "update"


def hub_latest() -> Optional[UpdateInfo]:
    d = http_json(f"https://api.github.com/repos/{HUB_REPO}/releases/latest")
    a = next((x for x in d.get("assets", []) if x.get("name") == HUB_ASSET), None)
    if not a:
        return None
    return UpdateInfo(str(d.get("tag_name", "")).lstrip("vV"), (d.get("body") or "").strip(),
                      a["browser_download_url"], int(a.get("size") or 0))


def _detached(args: List[str], cwd: Path) -> subprocess.Popen:
    """Start a program that keeps running after this one closes, even when the
    Workshop itself was started by the Windows task."""
    if not IS_WIN:
        return subprocess.Popen(args, cwd=str(cwd), env=clean_env(), close_fds=True)
    base = 0x00000008 | 0x00000200                      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        return subprocess.Popen(args, cwd=str(cwd), env=clean_env(), close_fds=True,
                                creationflags=base | 0x01000000)        # CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        return subprocess.Popen(args, cwd=str(cwd), env=clean_env(), close_fds=True, creationflags=base)


def start_hub_update(info: UpdateInfo, progress=lambda f: None) -> None:
    """Download and unpack the new Workshop, then start it in 'installer' mode:
    it waits for this copy to close, swaps itself in and starts the Workshop.
    The caller should close the window straight after this returns."""
    import zipfile
    up = DATA_DIR / UPDATE_DIR_NAME
    shutil.rmtree(up, ignore_errors=True)
    up.mkdir(parents=True, exist_ok=True)
    z = up / "new.zip"
    download(info.url, z, info.size, "", progress)
    new_dir = up / "new"
    with zipfile.ZipFile(z) as zf:
        zf.extractall(new_dir)
    if not (new_dir / EXE_NAME).exists():
        inner = [p for p in new_dir.iterdir() if (p / EXE_NAME).exists()]
        if not inner:
            raise RuntimeError("the update didn't contain the program")
        new_dir = inner[0]
    z.unlink(missing_ok=True)
    _detached([str(new_dir / EXE_NAME), "--install-update", str(os.getpid()), str(BASE)], new_dir)


def _wait_for_exit(pid: int, timeout: float = 60) -> None:
    if IS_WIN:
        h = _k32.OpenProcess(0x00100000, False, pid)            # SYNCHRONIZE
        if h:
            _k32.WaitForSingleObject(h, int(timeout * 1000))
            _k32.CloseHandle(h)
        return
    end = time.time() + timeout
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)


def _retry(fn, tries: int = 20, gap: float = 0.5):
    for i in range(tries):
        try:
            return fn()
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(gap)


def install_update_helper(old_pid: int, base: Path, src: Optional[Path] = None,
                          launch=lambda exe, args: _detached([str(exe)] + args, exe.parent),
                          start_timeout: float = 45) -> bool:
    """Runs inside the NEW version (started from workshop_data\\update\\new). Waits for
    the old Workshop to close, swaps the program files, starts the new Workshop and
    checks it really started; otherwise puts the old version back. Settings, apps,
    notes and backups are never touched (only the exe and _internal)."""
    base = Path(base)
    src = Path(src or Path(sys.executable).parent)
    exe, internal = base / EXE_NAME, base / "_internal"
    old_exe, old_internal = base / (EXE_NAME[:-4] + ".old.exe"), base / "_internal.old"
    flag = base / "workshop_data" / UPDATE_DIR_NAME / "started.flag"
    _wait_for_exit(old_pid)
    time.sleep(0.5)
    shutil.rmtree(old_internal, ignore_errors=True)
    try:
        old_exe.unlink(missing_ok=True)
    except OSError:
        pass
    moved = []
    try:
        _retry(lambda: os.replace(internal, old_internal)); moved.append("internal")
        _retry(lambda: os.replace(exe, old_exe)); moved.append("exe")
        shutil.copytree(src / "_internal", internal)
        shutil.copy2(src / EXE_NAME, exe)
    except Exception:
        _rollback(base, moved)
        launch(exe, ["--update-failed"])
        return False
    flag.unlink(missing_ok=True)
    proc = launch(exe, ["--updated", __version__])
    end = time.time() + start_timeout
    while time.time() < end:
        if flag.exists():
            return True
        if proc is not None and proc.poll() is not None and not flag.exists():
            break
        time.sleep(0.3)
    try:
        if proc is not None:
            proc.kill()
    except Exception:
        pass
    time.sleep(0.5)
    _rollback(base, ["internal", "exe"])
    launch(exe, ["--update-failed"])
    return False


def _rollback(base: Path, moved: List[str]) -> None:
    exe, internal = base / EXE_NAME, base / "_internal"
    old_exe, old_internal = base / (EXE_NAME[:-4] + ".old.exe"), base / "_internal.old"
    if "exe" in moved:
        try:
            exe.unlink(missing_ok=True)
            _retry(lambda: os.replace(old_exe, exe))
        except OSError:
            pass
    if "internal" in moved:
        shutil.rmtree(internal, ignore_errors=True)
        try:
            _retry(lambda: os.replace(old_internal, internal))
        except OSError:
            pass


def hub_startup(args: List[str]) -> str:
    """Tidy after an update. Returns a message to show, if any."""
    msg = ""
    up = DATA_DIR / UPDATE_DIR_NAME
    if "--updated" in args:
        try:
            (up).mkdir(parents=True, exist_ok=True)
            (up / "started.flag").write_text("ok")
        except OSError:
            pass
        msg = f"Dan's Workshop updated to v{__version__}"
        log_activity(APP_NAME, f"updated to v{__version__}")
    elif "--update-failed" in args:
        msg = "The update didn't start properly, so the previous version was put back."
    else:
        shutil.rmtree(BASE / "_internal.old", ignore_errors=True)
        try:
            (BASE / (EXE_NAME[:-4] + ".old.exe")).unlink(missing_ok=True)
        except OSError:
            pass
        if (up / "started.flag").exists():
            shutil.rmtree(up, ignore_errors=True)
    return msg


# ----------------------------------------------------------------------------- background checks

class Checker:
    """Runs the update checks off the main thread."""

    def __init__(self):
        self.lock = threading.Lock()
        self.results: Dict[str, Optional[UpdateInfo]] = {}
        self.errors: Dict[str, str] = {}
        self.releases: Dict[str, List[dict]] = {}
        self.last_checked: Optional[float] = None
        self.busy = False

    def run(self, apps: List[AppDef], done: Callable[[], None]) -> bool:
        if self.busy:
            return False
        self.busy = True

        def work():
            res, errs, rels = {}, {}, {}
            for app in apps:
                if app.kind in ("custom", "external", "script"):
                    continue
                try:
                    if app.kind == "github-exe":
                        rels[app.id] = github_releases(app.repo)
                    res[app.id] = latest_for(app, rels.get(app.id))
                except Exception as e:                   # offline, rate limited...
                    errs[app.id] = str(e)
            try:
                res["hub"] = hub_latest()
            except Exception as e:
                errs["hub"] = str(e)
            with self.lock:
                self.results, self.errors, self.releases = res, errs, rels
                self.last_checked = time.time()
                self.busy = False
            done()

        threading.Thread(target=work, daemon=True).start()
        return True
