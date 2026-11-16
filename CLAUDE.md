# Dan's Workshop - notes for Claude

Read this before changing anything. Keep it up to date in the same commit as the change.

## What it is
A Steam-style launcher hub for Dan's own apps (Windows, Python 3.12 + Tkinter + Pillow, PyInstaller
**one-folder** build, built with `--uac-admin`). Apps stay completely separate programs; the hub installs,
opens, shows and updates them. Owner: GitHub `Danielb1606`. Repo: `Danielb1606/DansWorkshop`.

## Folder layout (portable - everything in one folder, default `C:\Users\Dan\Dan's Workshop`)
    Dan's Workshop.exe, _internal\          the hub (never edit _internal)
    apps\<App folder>\                     each app with its saved data
    workshop_data\settings.json            hub settings (accent, after_launch, name, task_path...)
    workshop_data\state.json               per-app state (version, ver_key, last_opened, recapture, custom_art), custom apps
    workshop_data\activity.json            opened/updated log (no play-time tracking - Dan asked for dates/times only)
    workshop_data\art\<app id>.png         card pictures (auto-captured from the app's window)

## Apps (workshop/core.py BUILTIN)
- **Poker Trainer** (`poker-trainer`): Neutralino 6.9 app, `Poker Trainer Dev.exe` + `resources.neu`.
  Exe name must never change. Version is read from neutralino.config.json inside resources.neu (asar).
  Updates: `https://danielb1606.github.io/PokerTrainer/win/update.json` (sha256 checked); the app also
  self-updates. Profiles/settings are in browser localStorage: the hub launches it with
  `WEBVIEW2_USER_DATA_FOLDER=apps\Poker Trainer\profile` so they live in the app folder (portable).
  Imported from `Desktop\Poker Trainer`, skipping `overlay misses` (Dan chose to leave screenshots behind);
  the old AppData profile `%APPDATA%\Poker Trainer Dev.exe` is copied into `profile\`.
- **Daniels Assignment** (`daniels-assignment`): one-file PyInstaller exe from `Danielb1606/DanielsAssignment`
  releases; self-updates. Installed version is found by matching the exe size to release asset sizes.
  Imported from `Desktop\GamingProgram`.
- Custom apps: "Add an app" copies the exe's folder into apps\ (kind `custom`, no updates).

## Behaviour decisions (from Dan)
- Graphite and gold look (Steam-like library), toolbox icon, 4 rail pages: Library, Updates, Activity, Settings.
- 3 cards per row, must stay usable in a non-fullscreen window (drops to 2/1 columns only when very narrow).
- Card art = screenshot of the app's main window, taken automatically when it's in front for ~4 s,
  retaken after updates; "Change picture" on the card menu.
- Everything runs as administrator. A scheduled task (`Dan's Workshop`, RunLevel Highest, Priority 4) +
  Desktop shortcut (`schtasks /run`) skip the UAC prompt; set up automatically on first elevated run and
  re-done if the folder moves (settings.task_path).
- "Check for updates" button checks every app + the hub. Hub self-update: zip download, `swap.cmd`
  swaps exe + _internal after exit, rolls back if the new one doesn't write `update\started.flag` in 45 s.
- "Request a change" (card menu) copies a brief pointing at the app's repo CLAUDE.md and opens claude.ai.
- Lightweight: no background work except a 3 s process check; nothing runs when idle.

## Working with Dan
- Before bigger changes, show suggestions/examples to pick between. Small fixes: just do them and mention after.
- Speed matters: push and reply without waiting for the GitHub build; screenshots only for new screens.
- Never delete whole repos.

## Releasing
Bump `__version__` in workshop/core.py and push to main. The workflow tests, builds and publishes
`DansWorkshop.zip`; the commit message becomes the release notes (write it for Dan, plain English).
Run `python tests/test_core.py` first.

## History
- 1.0.0 - first version.
- 1.0.1 - sharper, bolder toolbox icon (each size drawn separately by make_icon.py; window uses iconphoto with all sizes).
