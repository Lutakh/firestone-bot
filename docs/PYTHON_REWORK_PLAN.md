# Firestone Bot: AHK v1.1 to Python rework plan

Status: approved by the repo owner. This branch (`python-rework`) is where the port lives.
This document is the hand-off between the cloud analysis session (which wrote it) and the
Claude Code session running on the owner's Windows gaming machine (which executes it).

Everything in the new code base is in English: code, comments, GUI, docs, commit messages.

## 1. Context the executing session must know

### 1.1 What the AHK bot does today

- ~6,200 lines of AutoHotkey v1.1: `firestone-bot.ahk` (main loop), `Gui.ahk` (5-tab settings
  GUI, ~90 settings persisted in `settings.ini`), `Functions/*.ahk`, `Functions/subFunctions/*.ahk`.
- Automation is 100 % screen-coordinate based:
  - ~247 `PixelSearch` calls: look for an exact RGB colour (with a per-channel variation of 0..10,
    mostly 3) inside a fixed rectangle. The dominant colours are the green "affordable/claim" button
    `0x0AA008` (117 uses) and `0x16BC15`, the red notification dot `0xF40000`, brown idle-troop
    `0x542710`, orange `0xF9AA47`/`0xFCAC47`.
  - ~470 `MouseMove x,y` + `Click` at fixed coordinates, always followed by `Sleep` (mostly 1000 ms,
    ~1,000 sleeps in total).
  - A handful of places click the pixel that `PixelSearch` FOUND rather than a fixed point:
    `OpenChestType`, `OraclesGift`, `MysteryBox`, `ResearchStart`, `WMUpgrade` (war machine
    selection by signature colour in the bottom roster strip).
  - Mouse wheel scrolling by fixed notch counts (`Send {WheelDown}` loops of 5/13/15/35 notches,
    200 ms apart) followed by clicks at fixed coordinates.
  - Keyboard: game hotkeys `M` (map), `T` (town), `U` (upgrades), `Alt+Tab` (in `MainMenu`),
    arrow keys `Left` (held 2 s) and `Right` (pressed N times) in `Guardian`.
  - ~107 timed `MsgBox` toasts (1.5 to 2 s) used as progress indicators. They also act as delays.
  - `Goto`-based control flow, deeply nested if/else, copy-pasted blocks (13 war machines,
    20 personal-tree nodes, 20 chest types).
  - Runtime functions read the LIVE GUI state (`GuiControlGet`) rather than a settings object.
- No `ImageSearch` anywhere. `Images/` contains only artwork (logo, splash). There are NO
  reference screenshots of the game UI in the repository.
- All coordinates are absolute SCREEN coordinates assuming: 1920x1080 monitor, DPI 100 %, taskbar
  at the bottom and visible, game windowed at 1920x1080 then maximized, Steam or Epic client.
  Coordinates used span x 56..1905, y 32..1039. The game client area is therefore roughly
  1920x1009 starting at y=31 (title bar) on Windows 10; this MUST be measured (see 4.1).
- Windows-only pieces: `ControlFocus`/`WinActivate` on `ahk_exe Firestone.exe`; `Process Close`
  then relaunch via `explorer.exe steam://rungameid/1013320` or
  `com.epicgames.launcher://apps/bda8d2133655435982b9118972792328%3Ae0aa26672dcb40c3a137ced30ed1f160%3A43d4ef20fcb94eb39a864d13164fe3ca?action=launch&silent=true`;
  heartbeat HTTP POST (WinHttpRequest COM) to `https://fs-bot-logs.lutak.ovh/api/heartbeat`
  (only when `[SettingsNoGui] EnableHeartbeat=1`); `DllCall` Wininet connectivity check; exit
  hotkey `Win+Esc`.
- State files next to the exe: `settings.ini` (the example is UTF-16 LE with BOM; AHK writes
  whatever encoding it reads) and `MapStartState.ini` (map points already clicked this session).
- The campaign map: ~75 hard-coded click points on a world-space map that must never be moved or
  zoomed. Priority order of 5 mission categories comes from settings.

### 1.2 Known quirks in the AHK source (keep behaviour, fix the typos)

- `Functions/UpgradeBlessings.ahk:100`: `PixelSearch ... 1091, 510, 1115, 5541` (y2 typo, meant 554-ish).
- `Functions/Guardian.ahk`: colour literal `0x0F40000` (7 hex digits; AHK reads it as 0xF40000).
- `Functions/subFunctions/WMUpgrade.ahk`: `ControlFocus,, ahk_exe Firestone.ex` (typo).
- `Functions/subFunctions/PTree.ahk:394`: stray top-level `BigClose()` after the function; dead code.
- `Functions/subFunctions/Awaken.ahk`: rectangles up to x=1910 (edge of screen).
- Some `PixelSearch` rectangles have inverted corners; normalise min/max.
- `Functions/subFunctions/MapStart.ahk.bak` and the 20 per-rarity chest files (`Golden.ahk`,
  `Mythic.ahk`, ...) are dead (superseded by `OpenChestType`). Do not port them.
- `Gui.ahk` ends its auto-execute section with `Return` before the function includes, which is
  why the stray `BigClose()` never fires.

### 1.3 Game facts (researched, medium confidence unless stated)

- Firestone is a Unity game (high). Steam app id 1013320. Epic slug `firestone-online-idle-rpg`.
  Browser versions on Kongregate, CrazyGames, Armor Games, R2 Games are Unity WebGL builds of the
  same code base (inferred, not proven). Accounts are per platform.
- The Unity client renders at any window size and the UI rescales with the window. Whether it
  letterboxes or re-anchors widgets at non-16:9 aspect ratios is UNKNOWN. Must be measured (4.2).
- Documented hotkeys: A Alchemist, B Bag, C Character, E Temple, G Guardian, H Hall, K, L, M Map,
  Q Quests, S, T Town, U Upgrades, X Exotic Merchant. Alt+Enter toggles fullscreen.
- Unity on Windows reads the mouse through Raw Input and the real cursor position. Injected
  input must go through `SendInput` with real scan codes (pynput does this). Background input
  via `PostMessage` to the Unity window does NOT work reliably. See section 8.
- Linux: Unity's Linux player is X11; Proton games are XWayland windows; process stays
  `Firestone.exe` under Proton. Whether Steam still ships a native Linux build is unverified.
- Holyday's written Terms of Use forbid bots; their Steam forum policy tolerates input-simulating
  scripts. The port stays strictly input simulation + screen reading, exactly like the AHK bot.

## 2. Target

Same features, same behaviour, same settings, new runtime:

| Requirement | Target |
|---|---|
| Language | Python 3.12 (64-bit) |
| OS | Windows 10/11 (tier 1), Linux X11 session incl. XWayland game window (tier 1), Linux Wayland (tier 3, experimental: detect and advise Xorg session) |
| Resolution | Any client size at 16:9 aspect, any DPI (tier 1). Other aspect ratios: measured in 4.2, then either letterbox model, per-anchor model, or auto-fit-to-16:9 by resizing the game window |
| Platform | Steam, Epic (tier 1). Browser (tier 2, after tier 1 is validated) |
| Distribution | One ZIP per OS built by GitHub Actions: `FirestoneBot.exe` + `_internal/` (PyInstaller onedir). No Python, no pip, no installer. Linux: tar.gz + optional AppImage |
| Settings | `settings.ini` and `MapStartState.ini` read/written with the SAME sections and keys, UTF-16 or UTF-8 accepted, so existing users just copy their files |
| GUI | Same 5 tabs and controls (Home, General Options, Guild & Personal Tree, War Machines, Settings) plus a Status panel on Home |
| Not in scope | New features, smarter logic, removing delays. Behaviour parity first |

## 3. Architecture

```
python/                       (new; the AHK files stay untouched at the repo root during the port)
  pyproject.toml
  firestone_bot/
    __main__.py               entry point; sets DPI awareness FIRST, then imports everything else
    app.py                    wires settings, GUI, runner
    settings.py               INI compatibility layer (same sections/keys as Gui.ahk SettingsMap)
    state.py                  MapStartState.ini
    gui/                      tkinter/ttk (stdlib, smallest bundle). Same tabs/controls/variable names
    runner.py                 main cycle = literal port of MainScript() incl. arena 6 h timer,
                              restart timer, end-of-cycle delay, stop event, Win+Esc hotkey
    platform/
      dpi.py                  SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2) with fallbacks
      window.py               GameWindow provider: find window, client rect in physical pixels,
                              activate. Backends: win32 (ctypes), x11 (python-xlib/EWMH),
                              browser (window by title, canvas located later)
      capture.py              mss; grab(rect) -> numpy BGRA
      input.py                pynput: move, click, click_at, wheel(notches), key, key_down/up
      process.py              psutil: find Firestone.exe / Firestone.x86_64, exe path, kill, launch
    vision/
      atlas.py                the logical 1920x1080 canvas: every point, rect, colour, variation
      viewport.py             Viewport(rect, scale, offset); logical<->screen mapping
      probes.py               pixel_search(rect, colour, variation) -> (x,y)|None, on the mapped rect
    features/                 one module per AHK file, same function names in snake_case:
      main_menu.py big_close.py go_map.py open_town.py map_close.py
      claim_events.py quests.py shop.py check_mail.py open_chests.py open_chest_type.py
      oracles_gift.py mystery_box.py guardian.py claim_beer.py use_tavern_token.py
      craft_artifact.py scarab.py scarab_token.py claim_rituals.py upgrade_blessings.py
      click_bless.py oracle_daily.py claim_engineer.py wm_upgrade.py wm_level_only.py
      wm_blueprints_only.py exotic_merchant.py exotic_upgrades.py buy_exotic.py arena.py
      arena_battle.py alchemist.py research.py research_start.py research_slot_test.py
      research_after_start_test.py research_clicks.py guild.py awaken.py ptree.py
      liberation_missions.py liberation_in_progress_check.py firestone_new_1st.py chaos.py
      map_redeem.py map_start.py claim_campaign.py hero_upgrade.py
      restart_game_routine.py heartbeat.py
    tools/
      measure_reference.py    prints the game window client rect (see 4.1)
      capture_tool.py         saves lossless PNG of the game client area + metadata JSON
      dry_run.py              runs one full cycle with input disabled, logs every click/probe
      probe_check.py          replays all atlas probes against a saved PNG and reports hits
  tests/                      pytest: viewport maths at 3 scales, pixel_search semantics on
                              synthetic images, INI round trip incl. UTF-16, atlas integrity
.github/workflows/build.yml   matrix windows-latest + ubuntu-22.04, PyInstaller onedir, upload
```

### 3.1 Coordinate model (the core of resolution independence)

- Every number from the AHK code is kept verbatim but lives in a LOGICAL canvas whose reference
  frame is the client area of the game on the original setup: `REF = (x0, y0, w, h)`, expected
  `(0, 31, 1920, 1009)` on Windows 10, to be confirmed by `tools/measure_reference.py`.
- At runtime the `GameWindow` provider returns the live client rect `C` in physical pixels.
  `scale = min(C.w / REF.w, C.h / REF.h)`; content is assumed centred (letterbox offsets
  `ox = (C.w - REF.w*scale)/2`, `oy = (C.h - REF.h*scale)/2`).
  Logical `(x, y)` -> screen `(C.x + ox + (x - REF.x0)*scale, C.y + oy + (y - REF.y0)*scale)`.
- Probe rectangles are mapped corner by corner, normalised, grown by 1-2 logical px to survive
  rounding at small scales. Colour variation gets a global boost (default +0 at scale 1.0,
  +2 otherwise) because sprites scaled by Unity drift by a few units while flat UI fills do not.
- Found-pixel clicks convert screen -> logical and back, or just click the found screen pixel.
- Wheel scrolling stays "N notches, 200 ms apart" (Unity ScrollRect scrolls in UI units, which
  scale with the canvas). Verify on the real game at two sizes (4.2); if it does not hold,
  switch those sequences to scroll-until-anchor.
- Sleeps and toast delays are kept as-is (toasts become non-blocking status lines + the same
  sleep, so timing stays identical).

### 3.2 Feature modules: translation rules

- One Python function per AHK function, same order of operations, same sleeps.
- `Goto` becomes structured control flow; label fall-through is reproduced explicitly and noted
  in a comment with the AHK file:line.
- `GuiControlGet X` becomes `settings.X` read from a live settings object mirrored by the GUI
  (the GUI updates the object on every change, matching the AHK behaviour of reading live state).
- `ControlFocus,, ahk_exe Firestone.exe` / `WinActivate` become `window.activate()`.
- `Send, !{Tab}` in `MainMenu` becomes `window.activate()` (no Alt+Tab).
- `MsgBox , , title, text, 2` becomes `status(text); sleep(2)`.
- Copy-paste blocks (war machines, personal tree, chest rarities, exotic upgrade grid) become
  data tables in `atlas.py` with the same values; the loops replace the nesting.
- Keep the unbounded loops (`MainMenu` settings finder, hero upgrade click loops) but add an
  optional safety cap setting defaulting to OFF so parity is preserved.

## 4. Execution plan for the local Windows session

The owner has given full control of the gaming machine and a TEST ACCOUNT. Steam, Epic and
browser versions are available. In-game actions are allowed on the test account. Nothing else
runs on that machine.

### 4.0 Environment setup (first thing)

1. Install Python 3.12 64-bit if missing (winget or python.org installer; add to PATH).
2. `cd python && python -m venv .venv && .venv\Scripts\pip install -e .[dev]`.
3. Confirm the game is installed (Steam) and launch it once manually to the main screen.
4. Verify screenshots work: `python -m firestone_bot.tools.capture_tool --out captures/probe.png`
   then open the PNG (the session can view images) to confirm the frame is the game client area.

### 4.1 Measure the reference frame (before any port code)

Run the ORIGINAL setup conditions (1920x1080 monitor, 100 % DPI, game windowed 1920x1080 then
maximized, taskbar bottom) and `tools/measure_reference.py`. Record `REF` in `atlas.py`.
Cross-check by capturing the main screen and verifying a few AHK probes on the PNG with
`tools/probe_check.py` (e.g. `BigClose` button at logical (1851,84), mail icon at (56,777),
troop-idle probe rect (1175,996)-(1187,1012) colour 0x542710 on the map screen).

### 4.2 Measure the game's scaling behaviour

Capture the main screen at: 1920x1080 maximized (reference), 1280x720 windowed, 2560x1440 or
fullscreen 1920x1080 if the monitor allows, and one non-16:9 window (e.g. 1600x1000). Compare:

- If all elements keep the same relative positions inside a 16:9 letterboxed area: the
  uniform-scale model is enough. Non-16:9 windows are handled by letterbox offsets.
- If widgets stick to edges at non-16:9: add `anchor` per atlas entry (left/right/top/bottom/
  center) and use ok-script style anchor mapping; or default to auto-fit (resize the window to
  the largest 16:9 that fits) and make anchors a later refinement.
- Also verify wheel-notch scrolling covers the same fraction of a list at two sizes.

Write findings to `docs/MEASUREMENTS.md` with the PNGs under `docs/captures/` (PNG, lossless).

### 4.3 Build the platform and vision layers, with tests

`dpi.py`, `window.py` (win32 first), `capture.py`, `input.py`, `process.py`, `atlas.py`,
`viewport.py`, `probes.py`. Unit tests with synthetic images. Then a live smoke test: find the
window, print the client rect and scale, capture, run `pixel_search` for the main-screen probes,
move the mouse to a logical point and verify visually with a capture that the cursor is on the
expected button (do not click yet).

### 4.4 Port the feature modules, in main-loop order, testing each on the test account

Order (same as `MainScript`): helpers (`big_close`, `main_menu`, `open_town`, `go_map`,
`map_close`) -> `claim_events` -> `quests` -> `shop` -> `check_mail` -> `open_chests` /
`open_chest_type` / `oracles_gift` / `mystery_box` / `open_bless_chests` -> `guardian` ->
`claim_beer` / `use_tavern_token` / `craft_artifact` -> `scarab_token` / `scarab` ->
`claim_rituals` / `upgrade_blessings` / `oracle_daily` -> `claim_engineer` / `wm_*` ->
`exotic_merchant` / `exotic_upgrades` / `buy_exotic` -> `arena` / `arena_battle` ->
`alchemist` -> `research*` -> `guild` / `awaken` / `ptree` / `liberation*` / `firestone_new_1st`
/ `chaos` -> `map_redeem` / `map_start` / `claim_campaign` -> `hero_upgrade` ->
`restart_game_routine` -> `heartbeat`.

For each module: port, run it alone via `python -m firestone_bot.tools.run_feature <name>`
with the game on the right screen, capture before/after, fix, commit with the AHK file name in
the message. Keep a `docs/PARITY.md` checklist: module, tested on Steam (y/n), Epic (y/n),
notes.

### 4.5 Settings, GUI, runner

`settings.py` (read the owner's existing `settings.ini` unchanged), tkinter GUI with the 5 tabs
and Status panel (window found, platform, client rect, scale, DPI OK, session type, capture
self-test, input self-test, Dry-run button, Start/Stop), `runner.py` with the exact main loop.
Run 3 complete cycles unattended on the test account. Then run the AHK bot and the Python bot
on the same screens to compare behaviour where useful.

### 4.6 Resolution runs

Repeat a full cycle at 1280x720 and at another size, plus 125 % DPI. Fix probes/clicks that miss.
Record outcomes in `docs/PARITY.md`.

### 4.7 Epic

Switch to the Epic install, verify platform detection by exe path, run a full cycle, verify the
restart routine (kill + Epic URL + wait for the green start button).

### 4.8 Packaging and CI

`.github/workflows/build.yml`: matrix `windows-latest` + `ubuntu-22.04`, `pyinstaller --onedir
--noconsole`, no UPX, upload artifacts, attach to release on tags. Test the Windows ZIP on the
gaming machine from a clean folder without the venv. Document the SmartScreen prompt in README.

### 4.9 Linux (when a Linux machine is available)

`window.py` x11 backend (EWMH `_NET_CLIENT_LIST`, `_NET_WM_PID`, `WM_CLASS`, `translate_coords`),
`process.py` (Proton `Firestone.exe` or native), relaunch via `xdg-open steam://rungameid/1013320`
(and Flatpak variant). Wayland: detect `XDG_SESSION_TYPE=wayland`, try the X11 path against
XWayland, report; advise an Xorg session if capture is black.

### 4.10 Browser (tier 2)

Backend `browser`: find the browser window by title containing "Firestone", locate the game
canvas inside the client area (letterbox bounding box of non-background pixels constrained to
16:9, or two persistent HUD anchors matched with OpenCV once templates exist), fall back to a
two-click manual calibration stored per window title. Recommend F11 and 100 % zoom. Validate
Kongregate and CrazyGames in Chrome/Edge and Firefox. Then evaluate section 8.

## 5. Decisions already taken by the owner

- Full control of the local machine and a test account: in-game actions during tests are fine.
- Branch: `python-rework`.
- Everything in English.
- Not a full rework: parity first.

## 6. Decisions still open (ask the owner when reached)

- ZIP with one exe (recommended) vs single-file exe (slower start, more AV false positives).
- Code signing: none (SmartScreen prompt on each version), SignPath (needs OSI licence + public
  CI), or paid OV certificate.
- Keep the heartbeat POST as-is, make it opt-in (it already is, via `EnableHeartbeat`), or drop it.
- Whether "log into an Xorg session" is acceptable as the supported Linux path.
- Whether to enable the optional safety cap on unbounded loops by default.
- Whether to keep the old AHK sources in the repo after the Python bot reaches parity.

## 7. Stack (pinned in pyproject)

- `mss` (screen capture, ctypes only, Windows GDI + Linux XCB; sets DPI awareness itself, so our
  own DPI call must come first)
- `numpy` (pixel search: per-channel tolerance mask + argwhere, row-major first hit like AHK)
- `pynput` (SendInput with scan codes on Windows, XTest on X11; global hotkey listener)
- `psutil` (process lookup, exe path, kill)
- `python-xlib` (Linux only)
- `opencv-python-headless` (only when templates/anchors are introduced in 4.10; not needed for
  tier 1)
- `tkinter` (stdlib) for the GUI
- Dev: `pytest`, `ruff`, `pyinstaller`
- Do NOT use `pyautogui` (unmaintained, VK-only key injection, needs scrot on Linux).

## 8. Background operation (owner request from users)

Users want to run the bot while using the PC for other things.

- Steam/Epic (Unity client): NOT feasible reliably. Unity reads Raw Input and the real cursor;
  `PostMessage`/`SendMessage` clicks into the Unity window are not honoured. Only real options are
  a VM or a second Windows session, both out of scope. Document this clearly in the README.
- Browser build: feasible. Drive Chrome/Edge through the DevTools protocol (Playwright, connect
  to the user's browser or launch it): `page.mouse`/`page.keyboard` events go to the tab without
  touching the OS cursor; `page.screenshot` captures the tab even when covered. Launch with
  `--disable-backgrounding-occluded-windows` (and keep the tab active in its window) so WebGL
  keeps rendering. This is a separate `browser_cdp` backend for `capture.py` and `input.py`; the
  feature modules do not change. Plan it after 4.10.

## 9. Working conventions for the executing session

- Commit small and often on `python-rework`, one AHK file per commit during the port, with the
  AHK file name in the subject. Push regularly; the machine may be reclaimed.
- Never commit captures containing account names or Discord IDs; crop or blur if needed.
- Keep `docs/PARITY.md` and `docs/MEASUREMENTS.md` up to date; they are the memory between sessions.
- When the game UI differs from what the AHK numbers expect (game update since the AHK bot was
  written), fix the atlas value and note the AHK original in a comment.
