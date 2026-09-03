# Measurements

Facts measured on the owner's gaming machine. Updated as the plan (docs/PYTHON_REWORK_PLAN.md)
progresses. Captures live under `docs/captures/` (PNG, lossless, cropped to the game client area).

## Machine (2026-09-03)

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| Monitor | 1 x 1920x1080, primary, DPI 96 (100 %) |
| Taskbar | bottom, visible, 48 px (working area 1920x1032) |
| Python | 3.12.10 (winget `Python.Python.3.12`, user scope) in `python/.venv`; 3.13.7 also present |
| Game installs | Steam (`C:\Program Files (x86)\Steam\steamapps\common\Firestone`) and Epic (`C:\Program Files\Epic Games\FirestoneOnlineIdleRPG`) |
| Process name | `Firestone.exe` (same for both stores) |
| Window title | `Firestone` |

## 4.0 capture self-test

Game maximized (Epic build running). `capture_tool` reported, DPI mode `per-monitor-v2`:

| Rect | x | y | w | h |
|---|---|---|---|---|
| Window (outer, incl. invisible 8 px frame) | -8 | -8 | 1936 | 1048 |
| Client | 0 | 23 | 1920 | 1009 |

- Client size 1920x1009 matches the plan's expectation (`REF.w`, `REF.h`).
- Client top is y=23 here, not the y=31 the AHK numbers imply (Windows 10 with a 40 px taskbar:
  1080 - 40 - 1009 = 31). On this Windows 11 machine the taskbar is 48 px, so the maximized
  window is 8 px shorter in outer height and the client starts 8 px higher. The AHK coordinates
  (y 32..1039) therefore point 8 px too low on this machine; the viewport model (client rect
  measured live, logical frame `REF = (0, 31, 1920, 1009)`) absorbs this. To be confirmed by
  `tools/probe_check.py` in 4.1.
- Capture of the client rect renders correctly (BGRA from mss, converted to RGB for PNG).

## 4.1 Reference frame

Tools: `python -m firestone_bot.tools.measure_reference`, `python -m firestone_bot.tools.probe_check`.
Capture: `docs/captures/main_1920x1080_max.png` (+ `.json` sidecar), Epic build, maximized,
main screen, 2026-09-03.

Result: **`REF = (0, 31, 1920, 1009)`** recorded in `vision/atlas.py`.

- Live client rect on this machine: (0, 23, 1920, 1009); `measure_reference` reports
  `client_top_delta_vs_ref = -8`, scale 1.0, offset (0, 0).
- Why y0 = 31 and not 23: the AHK code clicks as low as y = 1039, so on the author's machine the
  client bottom was at 1040 and the top at 1080 - 40 - 1009 = 31 (Windows 10, 40 px taskbar).
  On this Windows 11 machine (48 px taskbar) every AHK y is 8 px too low; the viewport maps
  logical y through `client.y - REF.y`, so it is corrected automatically.
- Cross-check on the capture. Both candidate y0 values land inside the sprites, 8 px apart, so
  this check alone cannot discriminate; the structural argument above decides.

| Atlas item | Logical (AHK) | Screen with y0=31 | Colour there | Comment |
|---|---|---|---|---|
| `BIG_CLOSE` (1851,84) | settings gear on the main screen | (1851,76) | 0xF5CA89 | on the gear |
| `MAIL_ICON` (56,777) | mail envelope | (56,769) | 0xFDCD6B | on the envelope |
| `MAIL_CLAIM_ALL` probe | needs the mail dialog open | | miss (expected) | re-check in 4.4 `check_mail` |
| `MAP_TROOP_IDLE` probe | needs the map screen | | miss (expected) | re-check in the 4.3 smoke test |

- Aspect: the client is 1920x1009, not 16:9. Both machines had the same client size, so the
  content layout is identical; only the screen offset differs.
