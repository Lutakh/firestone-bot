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
- Events (2026-09-04): main-screen Events button client (583,930), bell (609,907); list cards
  175 px apart starting at client y 263 (bell at (1432,283)), list X at client (1490,50); event
  page tabs "Events"/"Challenges" (Challenges bell at client (1305,28)), page X at (1715,93);
  Claim buttons client (1343,329)-(1626,388) and the two rows below, matching the AHK probes.
- New adventure style (2026-09-05, main screen only; dialogs, town, guild, map unchanged):
  right column icons Town / Map / Guild / Shop / Events / Battle pass at client x 1862, y 165 /
  275 / 400 / 525 / 650 / 780 (125 px apart), bell at (+38, -34) from the icon centre (seen on
  Map: client (1886..1915, 221..259)); settings gear at (1860,55); mail at client (55,575);
  bottom row Sale (optional) / Bag / Fellowship / Party at client y 790, Bag at x 1455; hero
  cards at client y 925 with centres x 165 (leader), 620, 800, 980, 1160, 1340 (guardian),
  1520 (Special), border orange 0xFCAC47 when upgradable, grey 0xB7B7B7 otherwise; blue
  0x1089FF mode button at client (1630..1810, 915..985) with white text. Bag panel anchored top
  right: X at client (1868,68), tabs at x 1487 y 100/190/285/370, chest grid client
  (1543..1887, 120..730). Chest dialog X at client (1413,55); its three open buttons are wider
  (client x 615-810 / 860-1060 / 1105-1305, y 750-830) but the AHK probes still fall inside
  them. Character page X at client (1795,72), Options X at (1725,85). Logical = client y + 31.
- World map north edge (2026-09-05): the Doomfire Island (volcano, "Guardian of Doomfire",
  Titan mission, 4 squads, timed) icon centre is at client (1300,-5), hidden behind the HUD
  with only its pin and timer visible next to the 21/27 squad counter. Dragging the map from
  client (350,600) to (350,680) moves it by exactly 80 px and the reverse drag restores it
  (strip correlation 0 px); the icon is then at client (1300,75). Its pop-up has the usual
  green "Start mission" button and X.

## macOS (2026-09-05)

Owner's MacBook Pro (Apple silicon, macOS 26.6), built-in Liquid Retina XDR 3024x1964 px =
1512x982 pt (backing scale 2.0), menu bar 34 pt, Dock 65 pt (visible frame 1512x883 pt at
y=65 from the bottom). Steam build, process name `Firestone`, bundle
`com.HolydayStudios.Firestone`, window title `Firestone`. Python 3.12.14 (Homebrew,
`python-tk@3.12` needed for tkinter).

| Item | Value |
|---|---|
| Quartz window bounds, zoomed window (fullscreen OFF in the game) | (0, 34, 1512, 883) pt = (0, 68, 3024, 1766) px |
| Title bar | 28 pt + 1 px separator = 57 px measured on the window image (AppKit's `contentRectForFrameRect` says 32 pt on macOS 26, which put every top-anchored point 8 px too low: the settings gear was missed) |
| Client | (0, 125, 3024, 1709) px, aspect 1.770 (16:9), canvas scale 1.575, rel 1.686 |
| Fullscreen Space (game Fullscreen ON) | window (0, 33, 1512, 949) pt below the menu bar, no title bar, the game letterboxes a 16:9 canvas with 94 px black bars top and bottom -> client (0, 160, 3024, 1710); measured on the per-window Quartz capture. Not the reference setup on the Mac: the Space switch animates for ~1 s and other windows are hidden |
| Capture colour space | raw `CGWindowListCreateImage` pixels are Display P3: blue mode button 0x1089FF read 0x3C84F7, gear 0xF5CA89 read 0xD49B50. Drawn into an sRGB `CGBitmapContext`: 0x0B86FF / 0xDE983F, inside the atlas tolerances |
| Capture timing | full client 41 ms, 60x40 px probe 17 ms (Quartz call overhead) |
| Settings gear bounding box, canvas units | Windows 16:9 reference x 1833-1889, y 28-61; Mac x 1833-1889, y 22-57 (after the title-bar fix the point (1846,57) is inside) |
| Activation | `NSRunningApplication.activateWithOptions_` returns True but does not activate from a background process on macOS 26; `AXUIElementSetAttributeValue(app, kAXFrontmost, True)` does (Accessibility granted); `open -b` kept as the last fallback |
| Permissions | Screen Recording denied = wallpaper capture, no error; both permissions are attributed to the app that launched the process (Claude / Terminal for a venv run, the bundle for FirestoneBot.app) |

Live checks on the Mac: `window_tool`, `capture_tool`, `smoke_test` (main-screen probes hit:
`ns_style_probe`, shop/events/battle-pass bells), `probe_check` on the capture, `run_feature
check_mail` (mail claimed and deleted, back on the main screen), `run_feature hero_upgrade`
(6 cards clicked), `tools/dry_run.py` (376 actions), `tools/dry_run.py --live --cycles 1`
(one real cycle through the runner).

### Centred screens at 16:9 (macOS, 2026-09-06)

The main screen HUD is edge-anchored and mapped correctly, but three screens are centred
dialogs / scenes whose entries had the default thirds-rule anchors: at the Mac's 16:9 client
their right-hand parts sat 47-125 px away from the probes. Anchored to the centre in the atlas
(`(CENTER, CENTER)`), no coordinate changed:

| Screen | Entries | Measured |
|---|---|---|
| Events list | cards, card bells, X | card bell at client x 2300 vs edge-anchored rect 2174-2229; centre-anchored 2307 |
| Event page | Challenges tab + bell, claim buttons, X | tab bell at 2082-2116 vs rect 1960-2015; centre-anchored 2066-2121 |
| Guild map + dialogs | expedition dot / buttons, shop, pickaxes, crystal | expeditions bell at x 591 vs left-anchored rect 638-761; centre-anchored 593 |

After the change: `run_feature guild` started the expedition (dot found at logical
(414,439), gone afterwards), `run_feature claim_events` claimed one challenge reward.
