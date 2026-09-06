# Firestone Bot

Automation bot for Firestone Idle RPG (Steam and Epic builds), written in Python 3.12. It is a
behaviour-for-behaviour port of the original AutoHotkey bot: same features, same
`settings.ini`, same screen-reading approach (pixel probes and simulated input, no memory
reading, no network calls to the game).

## Requirements

- Windows 10/11 (Steam or Epic version of the game) or macOS 13+ (Steam version; see the
  macOS section below).
- Reference setup: 1920x1080 monitor, 100 % DPI, game windowed and maximized, taskbar at the
  bottom, game language English. Both main-screen layouts are supported: the classic one and
  the "new adventure style" (heroes row at the bottom); the style is detected on the main
  screen at each cycle (Advanced > Game launch > Interface style forces one). The Status panel on the
  Home tab reports the detected window, client size, scale and aspect. Any window with the
  reference aspect (1920:1009) maps exactly; 16:9 windows and fullscreen use per-widget anchors
  and are still being validated.
- Do not move or zoom the world map.
- The bot owns mouse and keyboard while it runs: the Unity client reads the real cursor, so
  the PC cannot be used for something else at the same time (see
  `docs/PYTHON_REWORK_PLAN.md` section 8 for the planned browser-based alternative).

## Install (packaged build)

Download `FirestoneBot-windows.zip` from the Releases page, unzip anywhere and run
`FirestoneBot.exe`. Put your existing `settings.ini` next to it (or start from
`settings.ini.example`). Settings are also editable in the GUI.

The executable is not code-signed: Windows SmartScreen shows "Windows protected your PC" the
first time; click "More info", then "Run anyway".

## Run from source

```bash
python -m venv .venv
.venv\Scripts\pip install -e .[dev]
.venv\Scripts\python -m firestone_bot
```

`settings.ini` and `MapStartState.ini` are read from the current directory (from the exe's
directory in the packaged build).

## macOS

Ported on 2026-09-05 (Apple silicon MacBook Pro, macOS 26, Retina 1512x982 pt at 2x, Steam
build). What differs from Windows:

- **Game settings**: in the game's Settings > Graphics turn **Fullscreen OFF**. The macOS
  fullscreen Space letterboxes the 16:9 canvas with black bars and hides the menu bar; the
  bot copes (bars are measured and removed) but a normal window zoomed to the visible screen
  (menu bar and Dock showing) is the reference setup on the Mac.
- **Permissions** (System Settings > Privacy & Security), both required:
  - *Screen Recording*: without it macOS hands the bot a capture of the wallpaper only and
    every probe misses.
  - *Accessibility*: mouse and keyboard events (pynput) and un-minimising / resizing the game
    window go through it.

  Grant them to `FirestoneBot.app` when you use the bundle, or to the terminal application
  (Terminal, iTerm...) that runs the bot from source: macOS attributes the permissions to
  the application that launched the process. The Dashboard's Environment card says which
  one is missing. macOS shows the prompts the first time; a newly granted Screen Recording
  permission needs the bot to be restarted.
- **Retina**: the bot works in physical pixels (captures are 2x), the mouse is driven in
  points; the Environment card shows the factor. Captures are colour-matched to sRGB (the
  raw screen is Display P3), so the atlas colours apply unchanged.
- **Exit hotkey**: Cmd+Esc (Win+Esc on Windows).
- **pynput on macOS 26**: the keyboard layout lookups pynput makes assert the main thread
  (SIGTRAP otherwise), so the bot computes them once on the Tk thread at start-up
  (`platform/mac/pynput_fix.py`). If a Python GUI process ever crashes, macOS then shows a
  "Python quit unexpectedly while reopening windows" alert at every Tk start-up and the
  window never appears until it is answered; disable that restoration once with
  `defaults write org.python.python ApplePersistenceIgnoreState -bool YES`.
- **Epic** has no macOS client: only Steam is looked up and launched (`steam://rungameid/`).
- The game keeps a 16:9 canvas on the Mac, so the per-widget anchors of the 16:9 layout are
  used (validated live: main screen, mail, hero upgrades, one full cycle).

Run from source (Python 3.12 from Homebrew, with Tk):

```bash
brew install python@3.12 python-tk@3.12
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m firestone_bot
```

or double-click `firestone-bot-mac.command` (creates `.venv` on first use). Build the bundle
with `pyinstaller firestone-bot.spec`: `dist/FirestoneBot.app` (ad-hoc signed, not
notarised: see the step-by-step below for the Gatekeeper warning). `settings.ini` is read
from the current directory when run from source and from the directory holding
`FirestoneBot.app` when the bundle is launched from Finder.

### macOS: install from a release (step by step)

1. Download `FirestoneBot-macos.zip` from the
   [releases page](https://github.com/Lutakh/firestone-bot/releases/latest) and unzip it.
   Move `FirestoneBot.app` into a folder of its own (for instance `~/Documents/FirestoneBot`):
   the bot creates `settings.ini`, `MapStartState.ini`, `gui_state.json` and its log NEXT TO
   the bundle. Already have a `settings.ini`? Put it in that folder, or let the bot offer to
   import it at first start.
2. Double-click `FirestoneBot.app`. macOS refuses: *"Apple could not verify FirestoneBot.app
   is free of malware"* with **Move to Trash** / **Done**. Click **Done** (never Move to
   Trash). The app is signed with the project's own certificate but not notarised by Apple,
   which needs a paid developer account; the warning is expected.
3. Open **System Settings > Privacy & Security**, scroll down to the *Security* section: a
   line says *"FirestoneBot.app was blocked to protect your Mac"* with an **Open Anyway**
   button. Click it, confirm with your password or Touch ID, and answer **Open** to the
   last prompt. (On macOS 14 and earlier, right-click > Open on the app does the same.)

   If the app still does not appear afterwards (no window, no error: macOS sometimes keeps
   the quarantine flag), clear the flag once from Terminal, adapting the path, then launch
   the app again:

   ```bash
   xattr -dr com.apple.quarantine ~/Documents/FirestoneBot/FirestoneBot.app
   ```

4. Launch the app again. It names the permissions that are missing, triggers the system
   prompts and opens System Settings on the right pane. Enable FirestoneBot under
   **Screen Recording** and **Accessibility**, then quit and relaunch the bot (macOS applies
   Screen Recording at the next start). The Dashboard's Environment card keeps saying which
   one is still missing.
5. In the game: Settings > Graphics > **Fullscreen OFF**, window zoomed (green button),
   Steam only (no Epic client on macOS).
6. Start the bot from the Dashboard. Cmd+Esc stops it. Updates arrive through the Dashboard
   banner (see Updates below) and keep the same signature, so the permissions are not asked
   again; a manually downloaded new version goes through steps 2 and 3 again.

### Sharing your own macOS build

Build it (`pyinstaller firestone-bot.spec`) and zip `dist/FirestoneBot.app` (zip keeps the
signature; do not copy the bare folder through a cloud drive). The other person follows the
steps above. The CI bundle is signed with the project's self-signed certificate ("Firestone
Bot", see `tools/mac_codesign.py`) so the identity, and with it the Screen Recording /
Accessibility grants, stays the same across updates; an ad-hoc local build (no certificate)
would ask for them again after each update.

## Updates

The bot checks the project's GitHub releases at start-up and once a day (public API, no
account). When a newer version exists an orange banner across the top of the window says
"Version X is available" with an **Update** button that opens the release notes; **Download**
fetches the archive for the current OS, its
SHA256 checked against the release's `SHA256SUMS.txt`, unpacked next to the install, and
the banner turns green and a last dialog offers **Install and restart**: the bot closes, a
small script moves the program files aside
(renamed, never deleted first), puts the new ones in place and relaunches the bot. Only the
program files move: the `.app` on macOS, `FirestoneBot.exe` + `_internal/` on Windows
(`FirestoneBot` + `_internal/` on Linux), so `settings.ini`, `MapStartState.ini`,
`gui_state.json` and the log, which sit next to the exe, are never touched. Advanced >
Updates has a "Check for updates now" button. Running from source only gets the
notification (update with `git pull`). Nothing is downloaded or installed without a click.

**Going back.** The version you had before the update is kept next to the install as
`FirestoneBot.previous` (the exact one that was running, whatever its number, with its
version recorded in `FirestoneBot.previous.json`). Advanced > Updates then shows
"Restore previous version (X)": one click, a confirmation, and the bot swaps the program
files back and restarts; the newer version takes the `.previous` place, so the same button
brings it back again. Each update replaces the kept copy, so exactly one older version is
kept at a time (a full build, about the size of the install).

**Downloaded a release by hand?** Unzip it anywhere and start it. Without a `settings.ini`
next to the exe the bot runs with defaults and, at start-up, looks for a settings.ini of a
previous bot folder around the new one and in Desktop / Downloads / Documents; it offers to
copy it (with `MapStartState.ini` and `gui_state.json`), leaving the old folder untouched
and never overwriting a file already there. Advanced > Files > "Import settings from another
folder…" does the same for any folder you pick.

Releasing: bump `__version__` in `firestone_bot/__init__.py` (and `pyproject.toml`), create an
annotated tag whose message is the changelog, `git tag -a vX.Y.Z --cleanup=verbatim -F notes.md`
(without `--cleanup=verbatim` git drops the `## Heading` lines as comments), push the tag;
CI builds the Windows zip, the Linux tarball and the macOS zip, writes `SHA256SUMS.txt` and
attaches everything to the GitHub release with the tag message as body (the tag must equal
`v` + `__version__`). The bot falls back to the tag annotation when a release has no body.
`python -m firestone_bot --start` starts the bot as soon as the window is up.

## GUI

The window (customtkinter, "dark-blue" theme) has a sidebar with seven pages and the
START / DRY RUN / STOP buttons, plus a status strip at the bottom.

| Page | What lives there |
|---|---|
| Dashboard | Control (Start, Dry run, Stop, state, cycle number and duration of the last full cycle, current activity), Environment (game window, platform, client area, scale, DPI, capture, input; re-checked every 30 s while idle, F5 to re-check), Today (tavern tokens, chaos hits, scarab plays against their daily limits, arena done), Activity log |
| Main screen | claims (events, quests, mail, daily check-in), chests from the bag, hero upgrades |
| Town | guardian training and chaos-rift upgrade order, tavern (tokens, beer, scarab, daily limits), oracle, engineer, exotic merchant (selling strategy), arena, alchemist, research |
| Guild & Tree | guild visit (notifications, pickaxes, crystal, awaken, chaos rift + daily limit), personal tree upgrades |
| Missions & WM | mission priority order (move rows with the arrows), map reset, liberation and dungeon missions, war machine upgrades, legacy talent values |
| Advanced | end-of-cycle delay, **Safety cap**, game restart, Steam warning, **Heartbeat** (opt-in, needs a Discord ID), appearance (System / Light / Dark), read-only daily counters with a manual reset, file paths, Save now / Reload from disk |
| Help | requirements, shortcuts, about |

- **Auto-save**: every change is written into the live settings object immediately (the bot
  reads it at call time) and `settings.ini` is saved 750 ms later; the status strip shows
  `Saved HH:MM:SS`. While the bot runs the save is deferred (`Change active, saved when the
  bot stops`) so the GUI never races the bot's own counter writes; this also applies to
  Ctrl+S / Save now. On exit the bot is stopped first, then the pending changes are written.
- **Positive switches**: every switch reads "ON = the bot does it". For the AHK "skip" keys
  (`Beer`, `Scarab`, `NoGuild`, `NoEng`, `Pickaxes`, `Alch`, `Dust`, `DragonBlood`, `Research`,
  `SkipOracle`, `NoHero`) the help line names the ini polarity, e.g. `settings.ini: Beer=0 when
  on`. The file keeps the AHK keys and values, so it stays compatible with the AutoHotkey bot.
- **Unknown values** found in `settings.ini` (a legacy `GuardianTrain=Vermilion`, an
  unexpected chest rarity, an invalid priority order) are shown as `(unknown) value` with a
  warning and are never rewritten until you pick something else.
- **Game launch**: START (and every cycle start) launches the game through Steam or Epic when
  it is not running (Advanced > Game launch, auto-detected by default) and restores it when it
  is minimised; the Dashboard check does the same instead of reporting an error.
- **Daily limits** (Town / Guild pages): tavern tokens, chaos hits, scarab plays and arcane
  crystal hits per game day (defaults 12 / 10 / 10 / 5, 0 = no limit); each is done in one
  visit and then skipped until the daily shop's free box is claimable again.
- **Per-action switches**: every action the bot performs has its own switch (section
  `[Actions]` of `settings.ini`, all ON by default): guardian visit/evolve/training/chaos
  upgrades, beer tokens, artifact, Pharaoh's token, rituals, engineer tools, alchemy collection,
  guild expedition, map missions, campaign, mail deletion, Oracle's gifts, mystery boxes,
  battle pass rewards.
- **Dry run** (sidebar or Dashboard) runs one full cycle with mouse and keyboard disabled and
  logs every probe and click, to check the setup without touching the game.
- **Safety cap** (Advanced): 0 by default (identical to the AHK bot). The original has loops
  that wait forever for a screen change (arena battle, liberation mission, hero upgrades,
  main-menu finder); a cap of N stops such a loop after N iterations.
- **Heartbeat** (Advanced): off by default. Sends progress messages to the maintainer's log
  server only when the toggle is on AND a Discord ID is set.
- `gui_state.json` (next to `settings.ini`) stores window geometry, last page and appearance
  (all restored on the next start); it is safe to delete.
- The Activity log shows the bot's log stream (`firestone-bot.log` at INFO level); status
  lines posted without a log entry are added to it too.
- Shortcuts: Win+Esc exits (global; Cmd+Esc on macOS), F5 re-checks the environment, Ctrl+S saves now,
  Ctrl+1..7 switch pages, Ctrl+Q exits.

## Tools

| Command | Purpose |
|---|---|
| `python -m firestone_bot.tools.capture_tool --out captures/x.png` | lossless capture of the game client + metadata |
| `python -m firestone_bot.tools.measure_reference` | window geometry, canvas scale |
| `python -m firestone_bot.tools.probe_check captures/x.png` | replay atlas probes on a capture |
| `python -m firestone_bot.tools.smoke_test --move 56,777` | find window, probe, move the mouse |
| `python -m firestone_bot.tools.run_feature check_mail [--dry-run --fast]` | run one feature module |
| `python -m firestone_bot.tools.dry_run [--live --cycles N]` | one full cycle, input disabled (or live) |
| `python -m firestone_bot.tools.window_tool --client 1280x720` | resize the game window for tests (pixels; on macOS through the Accessibility API) |
| `FIRESTONE_GUI_PAGE=town python -m firestone_bot` | open the GUI on a given page (`dashboard`, `main`, `town`, `guild`, `missions`, `advanced`, `help`); `FIRESTONE_GUI_APPEARANCE=light|dark|system` overrides the theme (screenshots) |

## Development

`ruff check .`, `pytest -q`, `pyinstaller firestone-bot.spec`. GitHub Actions runs the tests
and builds the Windows ZIP and Linux tarball on every push; tagged `v*` releases get the
archives attached. Plan, progress and measurements: `docs/`.

## Icon

The exe, the `.app` and the bot window use the game's own icon (the 256 px image of
`FirestoneEos.ico` from the Epic install, in `assets/icon-256.png`). `assets/icon.ico` and
`assets/icon.icns` are generated from it by `python -m firestone_bot.tools.make_icons`
(needs Pillow, development only), so Windows and macOS show the same icon.
