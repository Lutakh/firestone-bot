# Measurements

Facts measured on the owner's gaming machine. Updated as the plan (docs/PYTHON_REWORK_PLAN.md)
progresses. Captures live under `docs/captures/` (PNG, lossless, cropped to the game client area).

## Machine (2026-09-03)

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| Monitor | 1 x 1920x1080, primary, DPI 96 (100 %) |
| Taskbar | bottom, visible, 48 px (working area 1920x1032) |
| Python | 3.12.10 (winget `Python.Python.3.12`, user scope) in `.venv`; 3.13.7 also present |
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

## 4.2 Scaling behaviour

Captures (`docs/captures/main_*.png`, main screen, Epic build): 1920x1009 maximized (reference),
1600x1000, 1280x720, 960x540, 1280x673 (same aspect as the reference), 1920x1080 fullscreen
(Alt+Enter). Windows were resized with `tools/window_tool.py`.

Measurement: centre of the gold-coin icon (top right), largest connected component of colour
0xF6C21D±40 in the top-right region, client pixels:

| Client | Coin centre | Coin width | Canvas scale `min(w/1920, h/1080)` | Right offset / scale | Top offset / scale |
|---|---|---|---|---|---|
| 1920x1009 | (1594.5, 47.5) | 40 | 0.934 | 348.5 | 50.9 |
| 1600x1000 | (1310.0, 42.5) | 35 | 0.833 | 348.0 | 51.0 |
| 1280x720 | (1047.5, 34.0) | 28 | 0.667 | 348.8 | 51.0 |
| 960x540 | (786.0, 25.0) | 23 | 0.500 | 348.0 | 50.0 |
| 1280x673 | (1064.0, 31.5) | 29 | 0.623 | 346.7 | 50.6 |
| 1920x1080 fullscreen | (1572.0, 51.0) | 43 | 1.000 | 348.0 | 51.0 |

Conclusions:

- **No letterbox.** The UI is a Unity canvas with a 1920x1080 reference and
  `scale = min(client_w / 1920, client_h / 1080)`; widgets are anchored to the screen edges (the
  coin keeps a constant 348 canvas px from the right edge and 51 from the top at every size,
  including the non-16:9 ones). At non-16:9 sizes the extra space goes between the anchored
  groups, not around the content.
- The plan's uniform "scale + centre" model is exact only when the live client has the SAME
  aspect as the reference (1920:1009). Check at 1280x673: coin error 1.0 px. At 16:9 it is wrong:
  1280x720 gives a 15x21 px error on the coin, fullscreen 1920x1080 a 22x32 px error.
- Implemented model (`vision/viewport.py`): per-entry anchor `(ax, ay)` in {0, 0.5, 1}; atlas
  numbers stay AHK screen coordinates on the reference client; mapping is
  `screen = client.origin + a * client.size + (logical - REF.origin - a * REF.size) / s0 * s`.
  Default anchor comes from the thirds rule on the point's position (`atlas.default_anchor`);
  it only matters at non-reference aspects and can be refined per entry when a probe misses
  (plan 4.6). Unit tests in `tests/test_viewport.py` check the coin positions above.
- Wheel-notch scrolling at two sizes: NOT measured yet (needs a scrollable list, i.e. clicking
  into a menu). To be done when the first wheel-using module (`open_chests`) is ported in 4.4.
- 125 % DPI: deferred to 4.6.

Consequence for users: "maximized on a 1920x1080 monitor" is still the reference setup. Any
window with aspect 1920:1009 is exact; 16:9 windows/fullscreen depend on the anchor guesses.

## 4.3 Live smoke test (2026-09-03)

`python -m firestone_bot.tools.smoke_test --move X,Y`: window found (Epic, client (0,23,1920,1009),
canvas scale 0.9343, rel_scale 1.0), capture of the client in ~110 ms, pixel_search on a probe
rect in < 0.2 ms. Mouse moved to `MAIL_ICON` (56,777) -> screen (56,769) and to `BIG_CLOSE`
(1851,84) -> (1851,76): the cursor cross sits on the envelope and on the gear (checked on
annotated captures).

Map screen (key `M`, capture `docs/captures/map_1920x1080_max.png`): `MAP_TROOP_IDLE`
(1175,996)-(1187,1012) 0x542710±10 HITS at screen (1178,988), i.e. inside the 12x16 rect after
the -8 px shift. This confirms `REF.y = 31`. `BigClose` click at (1851,76) closed the map.

## 4.5 Unattended run (2026-09-03)

`python -m firestone_bot.tools.dry_run --live --cycles 3` with the owner's settings.ini, Epic
build, 1920x1009 maximized:

| Cycle | Duration | Notes |
|---|---|---|
| 1 | 15 min | includes the arena (5 battles) |
| 2 | 8 min | arena skipped (6 h timer) |
| 3 | 7 min | |

Total 2194 traced actions, 600 clicks, no exception, no safety cap hit, game on the main screen
at the end. Log: `captures/live3.log` (not committed).

## 4.6 Resolution run at 1280x720 (2026-09-03)

Window resized with `window_tool --client 1280x720` (canvas scale 0.667, rel_scale 0.714,
aspect 16:9 so the per-entry anchors are in play). All live on the Epic build:

| Check | Result |
|---|---|
| `smoke_test --move 56,777` (mail icon) / `1851,84` (gear) | cursor on the envelope / on the gear (thirds rule gives left-bottom / right-top) |
| `check_mail` | claim-all and delete probes hit, mail claimed (4 -> 3), dialog closed, back on the main screen |
| `open_town`, `claim_beer` | town opened, tavern flow ran, back on the town screen |
| `alchemist` | probes hit (coin experiment collected, blood "running" detected) |
| `go_map` + `MAP_TROOP_IDLE` | miss, but legitimately: the map showed 0/26 idle troops |

World map anchoring: the purple rift-paw mission icon sits at client (871.5, 426.0) on the
1920x1009 capture and (576.6, 304.5) on the 1280x720 capture. Centre anchor predicts
(576.8, 304.0); a top-left anchor would predict (621.9, 304.0). The map is therefore centred
and scaled with the canvas, and `map_start` now clicks every mission point with an explicit
centre anchor (`atlas.ANCHOR_CENTER`); the thirds rule would have been 45 px off for points
near the edges.

Not done: 125 % DPI (needs a change of the Windows display scaling, left to the owner), a
third window size, the wheel-notch comparison at two sizes, and a full cycle at 1280x720.

## 4.7 Steam build (2026-09-03)

`process.kill_game()` closed the Epic build; `process.launch_game("steam")` opened
`steam://rungameid/1013320`; the process was up after 49 s and the window came up maximized at
the same client rect (0, 23, 1920, 1009). `detect_platform` returned `steam` from the exe path.
The RestartGameRoutine wait loop found `RESTART_START_BUTTON` (0x16BC15 in (845,860)-(1080,937))
on the first check: on this account it was the green "Claim" of the offline-progress dialog,
which is what the AHK routine clicks too. Captures: `captures/steam_boot.png`,
`steam_after_start.png` (not committed; they show a different account).

## Game UI changes since the AHK bot (2026-09-04, Epic build, 1920x1009)

- Tavern > Beer tab > token shop: the "1500 beer" buy button is green 0x0AA008, bbox client
  (407,580)-(652,623), i.e. logical (407,611)-(652,654). The AHK click (544,630) is still on it.
- Shop > Daily deals: horizontal card row. While the free "Mystery box" is claimable it is the
  FIRST card (green button, client (466,781)-(711,821) -> logical (466,812)-(711,852), observed
  right after the 10:00 reset on 2026-09-04); once claimed the card moves to the END of the row
  ("Claimed" text) and a paid deal takes the first slot. Claiming shows no pop-up; the box goes
  to the bag. The main-screen shop red dot was present after the reset (check-in pending).
- Guild > Chaos rift: two token counters top right, free (blue moon + cyan orb, 0x3182C6 /
  0x3969AD, client (1370..1430, 10..60)) and paid (orange medallion 0xA54510 / 0xB53400,
  client (1555..1615, 10..60)). The same icon is drawn inside the green Hit button, client
  (905..955, 880..920): probing that area tells which token the next hit would spend. A hit
  greys the button for a 3-4 min animation, but closing the rift (BigClose) and clicking it
  again on the guild screen resolves the battle immediately (tokens and damage updated).
- Guardian screen (Magic Quarter): tabs at client y ~140, third tab "Chaos rift" at x 1360 with
  its bell at (1400,95); roster portraits at client x 750/890/1030/1170, y 935, bells at the
  top-right corner (x 805/945/1085/1225, y 878); green "Upgrade" button at client
  (1560,655)-(1785,755), grey when unaffordable. Logical = client y + 31.
- Tavern > Scarab game: counters top right, free (silver coin with a scarab, client
  (1365..1420, 15..70)) and paid (gold coin with a purple ring, client (1555..1615, 15..70)).
  Purple 0x9C1C9C..0xB53CF7 only exists on the paid coin; the free coin is silver 0xBFC5C5.
  The icon inside the green Play button is at client (905..955, 900..950). The Play button
  turns 0x16BC15 while hovered (the AHK probe 0x0AA008 misses then).
- Guild shop > Supplies: the "Free pickaxes" card now has a green 0x0AA008 Claim button at
  client (590,692)-(835,735) -> logical (590,723)-(835,766); the AHK teal probe (0x1EA569 in
  (764,617)-(869,653)) and click (716,637) point at the "Next free" timer text instead.
- Chaos rift shop (2026-09-04): Shop button right column, client (1815,690), bell at (1880,610);
  shop left menu "Monthly pass" / "Supplies" (client (115,556), bell (205,522)); Supplies page:
  "Tome of power" green price button client (553,739)-(798,783), price rises per purchase
  (3,822 -> 3,994 -> ... 5,435 after 8 books), no confirmation; when unaffordable the button is
  still green and the click opens "You need N more Dark rune" with a green OK at client
  (805,595)-(1100,672). The price button turns 0x16BC15 while hovered.
