# Backlog (owner requests, not yet done)

- Windows cycle of 2026-09-07 14:54 (after the shop/tavern fix): several fast-timing entry
  probes missed once and cost a retry each (tavern_close_x x3 around the tavern chooser,
  dialog_close_x x3 in the guild/tree section; town 1m18s instead of 30s), and MapRedeem hit
  its safety cap on a completed mission ("Mission is already complete!" x3: the claim click
  did not take). Not blocking; to measure on the Windows client.
- Mouse-guard pause pop-up (owner, 2026-09-07): add a third button "Stop the bot" next to
  "Start a new cycle" and "Continue the cycle" (gui/pause_dialog.py; the decision goes
  through app._on_user_input, a stop must set the game's stop_event like the Stop button and
  close the dialog).
- Activity overlay not visible on Windows (owner, 2026-09-07): the log says "overlay ready
  (capture-safe: True)" and the panel hides for clicks under it, so it exists but the owner
  never sees it over the game; to check on the Windows machine (topmost / click-through
  flags, placement over the maximised game window, WDA_EXCLUDEFROMCAPTURE also hiding it
  from a Parsec stream?). Owner uses the machine through Parsec: a window excluded from
  capture is invisible in a remote-desktop stream, which may be the whole explanation.
- Robustness against network / server slowness (mostly done 2026-09-06): `Game.tap(expect=)`,
  `open_screen()` (main-menu recovery), `wait_for` / `wait_gone` and the `DIALOG_CLOSE_X`
  probe cover the shop, character window, map, town, town buildings with the standard close
  button and the guild map; mail, bag, events, battle pass and tavern have their own entry
  probes (orange ring of their close button). Still to do: measure on a slow connection; the
  Windows client of the owner is not checked yet with the fast mode.
- 125 % DPI and 4K (Parsec virtual display) validation runs (plan 4.6).
- macOS follow-ups (port done 2026-09-05, docs/MACOS_PORT.md): mixed-scale multi-monitor
  setups (one Retina factor is applied to every coordinate), `window_tool --client` through
  the Accessibility API is untested. (GUI cycles, CI-built signed `.app`, self-update: done.)
- Linux (plan 4.9) and browser build (plan 4.10 / section 8).
- Global optimisation (mostly done 2026-09-06, "Click timing" fast mode: 150 ms hover,
  screen-change waits, 300 ms toasts, 50 ms wheel notches, guardian screen waited for instead
  of a flat 6.5 s; cycle 5m45s -> about 2m30s on the owner's account; per-section timing
  logged; scarab / arena / crystal loops poll every 250 ms). Still to do: measure on a slow
  connection and on an account with everything unlocked (scarab, arena, crystal loops were
  only exercised through unit tests: the owner's account has them locked).
- Map missions: the missions come at random from a pool, so the list cannot be completed by
  observation (owner, 2026-09-06); the only way is detecting mission icons by colour instead
  of a fixed list.
- Windows checks of the 2026-09-06 work: the activity overlay (click-through, excluded from
  captures by `SetWindowDisplayAffinity`), the taskbar icon after an update (`ie4uinit`), the
  rollback button on a packaged install.
- Map missions detection mode (done 2026-09-06, `MapMode` = detect, features/map_detect.py):
  verified on one capture only (new style, macOS, missions in progress). Still to check: a
  map with missions not started yet (does their label look the same?), the classic style,
  Windows captures, and labels that touch a place name.
- Classic interface style: the hero-upgrade mode reader returned "unknown" three times in a
  row on the owner's Mac (2026-09-06, cycle 4, references resampled from the classic
  reference screens); `hero-mode-miss.png` is now saved next to the settings when it
  happens, to extend the references from a real screen. The main-menu safety cap was also
  reached twice at the start of a cycle without a visible cause (something left open after
  the shop step?).
- Classic style claims (owner, 2026-09-07): the battle pass was fixed on the 4K client
  (red-dot bells tolerant to the display's red, wider entry probe; two rewards claimed live).
  The events could not be exercised: no event bell during the check. Still to verify with a
  bell: the centred-dialog anchors of the events list and page (EVENTS_* in atlas.py) on the
  3840x2022 client, where the battle pass dialog did not follow the HUD anchor model.
- 4K client (3840x2022 window, 2026-09-07): three cycles clean at 1m50-2m34 with the fixes
  above; the new-style button probe (NS_STYLE_PROBE) is not checked at 4K yet (no button in the
  classic layout: its absence now simply means classic); the account is level 46, so the
  level-50+ features (arena, engineer, awakening, crystal) are still unchecked at 4K.
- macOS memory: the Quartz capture leaked 8 MB per grab (fixed 2026-09-07); the process
  still sits at 0.7-1.3 GB at 4K because every capture is a 31 MB full-client image copied
  twice; a smaller capture path (grab only the probe rect, which grab() already does) and
  fewer full-client thumbnails would bring it down.
- Level gating follow-ups: the "not in a guild" case (no banner: today the guild features
  simply run and miss), the digit reader on other resolutions than the owner's Mac (templates
  are size-normalised but only checked at 3024x1709), the level regions in the classic
  interface style (measured in the new-adventure style only).
- Linux: overlay without capture exclusion (top strip only), X11 input shape untested.
