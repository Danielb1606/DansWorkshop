"""Offline checks for Dan's Workshop. Run: python tests/test_core.py"""
import json, os, struct, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workshop import core

ok = 0
def check(cond, what):
    global ok
    if not cond:
        raise SystemExit(f"FAIL: {what}")
    ok += 1

tmp = Path(tempfile.mkdtemp())
core.set_base(tmp / "Dan's Workshop")
os.environ["USERPROFILE"] = str(tmp / "home")
os.environ["APPDATA"] = str(tmp / "home" / "AppData" / "Roaming")

# versions
check(core.newer("1.5.2", "1.5.1") and not core.newer("1.5", "1.5.0") and core.newer("v2.0", "1.9.9"), "version compare")

# a fake resources.neu (asar) with a version inside
def fake_neu(path, version):
    cfg = json.dumps({"version": version}).encode()
    header = json.dumps({"files": {"neutralino.config.json": {"size": len(cfg), "offset": "0"}}}).encode()
    hs = len(header)
    path.write_bytes(struct.pack("<IIII", 4, hs + 8, hs + 4, hs) + header + cfg)
fake = tmp / "r.neu"; fake_neu(fake, "1.5.5")
check(core.neu_version(fake) == "1.5.5", "read version from resources.neu")
check(core.neu_version(tmp / "missing") == "", "missing resources.neu")

# release matching by size
rels = [{"tag_name": "v1.5.1", "assets": [{"name": "DanielsAssignment.exe", "size": 111}]},
        {"tag_name": "v1.5.0", "assets": [{"name": "DanielsAssignment.exe", "size": 222}]}]
check(core.match_release_by_size(rels, "DanielsAssignment.exe", 222) == "1.5.0", "match by size")
check(core.match_release_by_size(rels, "DanielsAssignment.exe", 5) == "", "no match")

# importing: originals stay, skips work, profile comes along
pt_src = tmp / "home" / "Desktop" / "Poker Trainer"
(pt_src / "overlay misses").mkdir(parents=True)
(pt_src / "overlay misses" / "a.png").write_bytes(b"x")
(pt_src / "Poker Trainer Dev.exe").write_bytes(b"exe")
fake_neu(pt_src / "resources.neu", "1.5.5")
(pt_src / ".tmp").mkdir(); (pt_src / ".tmp" / "window_state.config.json").write_text("{}")
prof = tmp / "home" / "AppData" / "Roaming" / "Poker Trainer Dev.exe" / "EBWebView" / "Default" / "Local Storage"
prof.mkdir(parents=True); (prof / "leveldb.log").write_text("profiles")
da_src = tmp / "home" / "Desktop" / "GamingProgram"
(da_src / "daniels_assignment_data").mkdir(parents=True)
(da_src / "DanielsAssignment.exe").write_bytes(b"e" * 222)
(da_src / "DanielsAssignment.old.exe").write_bytes(b"old")
(da_src / "DanielsAssignment-report-20261116-010439.zip").write_bytes(b"z")
(da_src / "daniels_assignment_data" / "config.json").write_text("{}")

st = core.load_state()
c = core.import_candidates(st)
check({a.id for a, _ in c} == {"poker-trainer", "daniels-assignment"}, "finds both apps on the Desktop")
for app, src in c:
    core.import_app(app, src)
pt = next(a for a in core.BUILTIN if a.id == "poker-trainer")
da = next(a for a in core.BUILTIN if a.id == "daniels-assignment")
check(pt.installed and da.installed, "both installed")
check(not (pt.dir / "overlay misses").exists(), "screenshots left behind")
check((pt.dir / ".tmp" / "window_state.config.json").exists(), "window state copied")
check((pt.profile_dir / "EBWebView" / "Default" / "Local Storage" / "leveldb.log").read_text() == "profiles", "profiles copied into the app folder")
check((pt_src / "Poker Trainer Dev.exe").exists() and (prof / "leveldb.log").exists(), "originals untouched")
check(not (da.dir / "DanielsAssignment.old.exe").exists() and not list(da.dir.glob("*report*")), "leftovers skipped")
check((da.dir / "daniels_assignment_data" / "config.json").exists(), "DA data copied")
check(core.import_candidates(st) == [], "nothing left to import")

# versions of installed apps
check(core.installed_version(pt, st) == "1.5.5", "PT version")
check(core.installed_version(da, st, rels) == "1.5.0", "DA version by size")

# launch environment points the browser data at the app folder
env = core.launch_env(pt)
check(env["WEBVIEW2_USER_DATA_FOLDER"] == str(pt.profile_dir), "portable profile env")
os.environ["_MEIPASS2"] = "x"; os.environ["_PYI_X"] = "y"
env = core.clean_env()
check("_MEIPASS2" not in env and "_PYI_X" not in env and env["PYINSTALLER_RESET_ENVIRONMENT"] == "1", "clean env")

# activity
core.log_activity("Poker Trainer", "opened", time.time() - 10)
core.log_activity("Daniels Assignment", "updated to v1.5.2")
a = core.activity()
check(a[0]["event"] == "updated to v1.5.2" and len(a) == 2, "activity newest first")
check(core.nice_date(time.time()) == "Today" and core.nice_date(time.time() - 86400) == "Yesterday", "dates")
check(core.ago(time.time() - 120) == "2 min ago" and core.ago(None) == "never", "ago")

# custom apps
ext = tmp / "Other" / "Thing"; ext.mkdir(parents=True); (ext / "thing.exe").write_bytes(b"x"); (ext / "save.dat").write_text("1")
app = core.add_custom_app("My Thing", ext / "thing.exe", True, st)
check(app.installed and (app.dir / "save.dat").exists(), "custom app copied in")
check(any(x.id == app.id for x in core.all_apps(core.load_state())), "custom app saved")
core.remove_custom_app(app.id, st)
check(all(x.id != app.id for x in core.all_apps(core.load_state())), "custom app removed")

# settings
s = core.load_settings(); s["accent"] = "nope"; core.save_settings(s)
check(core.load_settings()["accent"] == "gold", "bad accent falls back")

# change brief + task + updater script
b = core.change_brief(pt, "1.5.5")
check("CLAUDE.md" in b and "1.5.5" in b and "Danielb1606/PokerTrainer" in b, "change brief")
x = core.task_xml(Path(r"C:\Users\Dan\Dan's Workshop\Dan's Workshop.exe"))
check("HighestAvailable" in x and "<Priority>4</Priority>" in x and "Dan's Workshop.exe" in x, "task xml")
sc = core.updater_script(Path(r"C:\W"), Path(r"C:\W\workshop_data\update\new"), Path(r"C:\W\workshop_data"), 1234, "1.0.1")
check("PID eq 1234" in sc and "_internal.old" in sc and "--update-failed" in sc and "started.flag" in sc, "swap script")

# hub startup marks the new version as started
msg = core.hub_startup(["--updated", "1.0.0"])
check("updated" in msg and (core.DATA_DIR / "update" / "started.flag").exists(), "update handshake")

# Obsidian: linked (not copied), only shown when installed, vaults read from its settings
os.environ["LOCALAPPDATA"] = str(tmp / "home" / "AppData" / "Local")
check(all(a.id != "obsidian" for a in core.all_apps(core.load_state())), "Obsidian hidden when not installed")
ob = tmp / "home" / "AppData" / "Local" / "Programs" / "Obsidian"; ob.mkdir(parents=True); (ob / "Obsidian.exe").write_bytes(b"x")
o = next((a for a in core.all_apps(core.load_state()) if a.id == "obsidian"), None)
check(o is not None and o.installed and o.exe_path == ob / "Obsidian.exe", "Obsidian found where it's installed")
check(not str(o.exe_path).startswith(str(core.APPS_DIR)), "Obsidian is linked, not copied")
cfgdir = tmp / "home" / "AppData" / "Roaming" / "obsidian"; cfgdir.mkdir(parents=True)
(cfgdir / "obsidian.json").write_text(json.dumps({"vaults": {"a": {"path": r"C:\Notes\Dan Notes", "ts": 5, "open": True},
                                                            "b": {"path": r"C:\Old Vault", "ts": 1}}}))
v = core.obsidian_vaults()
check([x["path"] for x in v] == [r"C:\Notes\Dan Notes", r"C:\Old Vault"], "vaults listed, newest first")
check(core.obsidian_link(r"C:\Notes\Dan Notes") == "obsidian://open?path=C%3A%5CNotes%5CDan%20Notes", "vault link")

# notes: move a vault into the Workshop, Obsidian follows, backups and restore
vault = tmp / "home" / "Documents" / "Dan Notes"
(vault / ".obsidian" / "plugins" / "calendar").mkdir(parents=True)
(vault / ".obsidian" / "plugins" / "calendar" / "data.json").write_text("{}")
(vault / "Daily").mkdir(); (vault / "Daily" / "Monday.md").write_text("hello")
(vault / ".trash").mkdir(); (vault / ".trash" / "old.md").write_text("x")
(cfgdir / "obsidian.json").write_text(json.dumps({"vaults": {"abc": {"path": str(vault), "ts": 9, "open": True}}}))
check(core.vault_warnings(str(vault)) == [], "no warnings for a plain vault")
check(core.vault_warnings(r"C:\Users\Dan\OneDrive\Notes"), "OneDrive vault warns")
new = core.move_vault_in(str(vault))
check(new == core.NOTES_DIR / "Dan Notes" and (new / "Daily" / "Monday.md").read_text() == "hello", "vault copied in")
check((new / ".obsidian" / "plugins" / "calendar" / "data.json").exists(), "plugins and settings came along")
check(not (new / ".trash").exists() and (vault / "Daily" / "Monday.md").exists(), "trash skipped, original kept")
oj = json.loads((cfgdir / "obsidian.json").read_text())["vaults"]
check(list(oj) == ["abc"] and oj["abc"]["path"] == str(new) and oj["abc"]["open"], "Obsidian now points at the Workshop copy")
check(core.stored_vault(str(new)) == "workshop:Dan Notes" and core.vault_path("workshop:Dan Notes") == str(new), "stored relative to the Workshop")
# another PC: Obsidian doesn't know the vault yet
(cfgdir / "obsidian.json").write_text(json.dumps({"vaults": {}}))
check(core.register_workshop_vaults() == 1 and core.register_workshop_vaults() == 0, "vault registered once on a new PC")
# backups: made, skipped when unchanged, restored with the current version kept
z1 = core.backup_vault(str(new))
check(z1 is not None and z1.exists(), "backup made")
check(core.backup_vault(str(new)) is None, "no backup when nothing changed")
time.sleep(1.1); (new / "Daily" / "Monday.md").write_text("changed")
z2 = core.backup_vault(str(new))
check(z2 is not None and len(core.list_backups("Dan Notes")) == 2, "new backup after a change")
core.restore_backup(z1, str(new))
check((new / "Daily" / "Monday.md").read_text() == "hello", "restored the older version")
check(any("before restore" in p.name for p in core.NOTES_DIR.iterdir()), "current version kept before restoring")
core.KEEP_BACKUPS = 2
for i in range(3):
    time.sleep(1.1); (new / "n.md").write_text(str(i)); core.backup_vault(str(new))
check(len(core.list_backups("Dan Notes")) == 2, "old backups pruned")

# Deadlock Auto Config: a folder of scripts, copied in with its files, mods and patches
dl = tmp / "home" / "Desktop" / "Deadlock config files" / "Deadlock Auto Config"
(dl / "mods").mkdir(parents=True); (dl / "patches").mkdir(); (dl / "scripts").mkdir()
for f in ("Apply Deadlock Settings.bat", "Save My Current In-Game Settings.bat", "Change Aspect Ratio.bat", "README.txt"):
    (dl / f).write_text("@echo off")
(dl / "mods" / "pak05_dir.vpk - daylock").write_bytes(b"v"); (dl / "patches" / "convars.txt").write_text("c")
st = core.load_state()
c = [a for a, _ in core.import_candidates(st)]
check([a.id for a in c] == ["deadlock-config"], "Deadlock Auto Config found on the Desktop")
dla = c[0]; core.import_app(dla, dl)
check(dla.installed and (dla.dir / "mods" / "pak05_dir.vpk - daylock").exists() and (dla.dir / "patches" / "convars.txt").exists(),
      "scripts, mods and patches copied in")
check(dla.kind == "script" and dla.play_label == "Apply settings" and len(dla.actions) == 2, "Apply is the main button, two more on the menu")
try:
    core.run_script(dla, "missing.bat"); check(False, "missing script should fail")
except RuntimeError:
    check(True, "missing script reported")
check("README" in core.change_brief(dla, ""), "change brief for scripts")

print(f"all {ok} checks passed")
