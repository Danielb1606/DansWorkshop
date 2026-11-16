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
- **Deadlock Auto Config** (`deadlock-config`, kind `script`): Dan's PowerShell tool (from an Oct 2026 chat) that
  re-applies his Deadlock settings and mods after patches: patch-safe merges into gameinfo.gi and video.txt
  (video.txt lives in Steam\userdata\<id>\1422450\local\cfg), mods/ copied to game\citadel\Addons as pakNN_dir.vpk.
  Imported from Desktop\Deadlock config files\Deadlock Auto Config (scripts\, files\, patches\, mods\, backups\).
  Main button = Apply Deadlock Settings.bat; menu: Save My Current In-Game Settings, Change Aspect Ratio,
  Open mods folder. .bat files run in their own console (they pause at the end). No repo, no updates.
- **Obsidian** (`obsidian`, kind `external`): Dan's notes. Linked, NOT copied (it has its own installer and
  updater); found at %LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe (hidden if not installed). Launched as the
  normal user via explorer.exe (admin breaks obsidian:// links / drag-drop). Vaults read from
  %APPDATA%\obsidian\obsidian.json; card menu: Open vault, Play opens… (state `vault`). No updates row.
- Notes: vaults can be moved into `Dan's Workshop\notes\<vault>` (copy, verify, then Obsidian's vault list
  is switched; original left as backup; warns for OneDrive/Dropbox/Obsidian Sync/git). Stored as `workshop:<name>`
  so it survives moving PC; on start / when Obsidian closes, Workshop vaults are added to obsidian.json if
  missing. When Obsidian closes, changed vaults are zipped to `backups\Obsidian\<vault>\` (keep 20); Restore
  keeps the current version renamed "before restore". Install Obsidian button downloads the latest installer
  from obsidianmd/obsidian-releases and runs it as the normal user.
- Custom apps: "Add an app" copies the exe's folder into apps\ (kind `custom`, no updates).

## Behaviour decisions (from Dan)
- Graphite and gold look (Steam-like library), toolbox icon, 4 rail pages: Library, Updates, Activity, Settings.
- Library is always 3 x 2 tiles visible (Dan's rule): tiles size to fit both width and height, and after a
  resize the window snaps to the shape that fits 3 x 2 exactly (keeps whichever side you dragged most; not when
  maximised). All tiles the same height (one-line description with …). Slim scrollbar, nearly invisible until
  the mouse is over the tiles, for more than 6.
- Card art = screenshot of the app's main window, taken automatically when it's in front for ~4 s,
  retaken after updates; "Change picture" on the card menu.
- Everything runs as administrator. A scheduled task (`Dan's Workshop`, RunLevel Highest, Priority 4) +
  Desktop shortcut (`schtasks /run`) skip the UAC prompt; set up automatically on first elevated run and
  re-done if the folder moves (settings.task_path).
- "Check for updates" button checks every app + the hub. Hub self-update: zip download + extract to
  workshop_data\update\new, then that NEW exe is started with `--install-update <old pid> <base>`: it waits for
  the old one to exit, swaps exe + _internal (keeps .old), starts the Workshop with `--updated`, and rolls back
  if it doesn't write `update\started.flag` in 45 s. (1.0-1.3.1 used a swap.cmd whose wait loop failed when
  detached - updates from those versions never installed; Dan had to extract 1.3.2 by hand once.)
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
- 1.3.7 - Rename… and Change picture… at the top of every tile's ⋯ menu (state apps[id].name; empty = default);
  square custom pictures show whole like icons; 'Use its own picture again' resets.
- 1.3.6 - icon = design B: gold toolbox on a dark tile with a gold edge, NO glow (Dan's pick); each size drawn
  separately with straight edges snapped to whole pixels for maximum sharpness (make_icon.py).
- 1.3.5 - real taskbar fix: window icons set with WM_SETICON from the .ico at the DPI's SM_CXICON/SM_CXSMICON
  (Tk's iconphoto handed Windows the 256 px tile version, which it shrank and blurred - never use iconphoto).
  Obsidian tile = Dan's purple stone picture, background removed, upscaled + sharpened (assets/app_obsidian.png).
- 1.3.4 - equal tile heights; window keeps a 3 x 2 shape; ghost scrollbar.
- 1.3.3 - taskbar sizes of the toolbox icon fill the slot (no dark tile, thin outline); shortcuts + pinned
  shortcut re-saved and Windows icon cache refreshed (ie4uinit -show) when ICON_REV changes; tiles show each
  app's OWN icon (Dan's rule: taskbar icon = tile picture): assets icon, else extracted from resources.neu
  (Neutralino) or from the exe (PrivateExtractIconsW), upscaled + sharpened when small.
- 1.3.2 - fixed self-update (new version installs itself instead of swap.cmd).
- 1.3.1 - app icons on tiles (`icon` field, assets/app_<id>.png): Daniels Assignment = red flask (Dan picked option A); Deadlock = DL art-deco diamond with a big outlined brass gear (option 3).
- 1.3.0 - Deadlock Auto Config tile; cards no longer cut off by the scrollbar.
- 1.2.0 - notes in the Workshop, automatic notes backups, restore, Install Obsidian.
- 1.1.0 - Obsidian tile.
- 1.0.1 - sharper, bolder toolbox icon (each size drawn separately by make_icon.py; window uses iconphoto with all sizes).
