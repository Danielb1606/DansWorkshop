# Dan's Workshop

One place for all of Dan's apps: open them, see which are running, and keep them up to date.
Each app stays its own separate program, living (with its saved data) inside the Workshop folder.

## Install

1. Download `DansWorkshop.zip` from the latest [release](../../releases/latest).
2. Right-click it, choose Extract All, and extract into `C:\Users\Dan` (you get `C:\Users\Dan\Dan's Workshop`).
3. Open `Dan's Workshop.exe` inside it and say Yes to the Windows prompt (only this once).
4. It makes a "Dan's Workshop" shortcut on the Desktop. Right-click it, Pin to taskbar.
   From then on it opens as administrator without the prompt.
5. Press "Bring them in" to copy Poker Trainer and Daniels Assignment (with their saved data) into the Workshop.

## Develop

    pip install pillow
    python dans_workshop.py          # uses ./_dev_workshop as the Workshop folder
    python tests/test_core.py
