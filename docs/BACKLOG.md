# Backlog (owner requests, not yet done)

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
- Mouse-usage detection (owner spec, 2026-09-04): detect that the USER moves the mouse while
  the bot runs (pynput 1.8 gives an `injected` flag on Windows, so the bot's own SendInput events
  can be told apart from the physical mouse). On detection: abort the current cycle, show a
  pop-up the user can validate or that closes by itself after 30 s, saying that the mouse was
  moved and that the bot will restart a NEW cycle from the beginning after 30 s without any
  mouse activity (each new movement restarts the 30 s countdown). Keyboard input should count
  too. Not active in dry runs.
- Global optimisation (mostly done 2026-09-06, "Click timing" fast mode: 150 ms hover,
  screen-change waits, 300 ms toasts, 50 ms wheel notches, guardian screen waited for instead
  of a flat 6.5 s; cycle 5m45s -> about 2m30s on the owner's account; per-section timing
  logged; scarab / arena / crystal loops poll every 250 ms). Still to do: measure on a slow
  connection and on an account with everything unlocked (scarab, arena, crystal loops were
  only exercised through unit tests: the owner's account has them locked).
- Map alignment: detect that the world map is not centred or is zoomed (zoom slider bottom
  right, drag offset) and re-centre / reset the zoom before clicking the mission points; today a
  moved map silently breaks every fixed mission coordinate.
- Map missions: inventory the mission icons the AHK list does not cover (e.g. the Frostfire
  north-west point added 2026-09-04) by capturing the map at several times of the day, and/or
  detect mission icons by colour instead of a fixed list.
- Windows checks of the 2026-09-06 work: the activity overlay (click-through, excluded from
  captures by `SetWindowDisplayAffinity`), the taskbar icon after an update (`ie4uinit`), the
  rollback button on a packaged install.
- Level gating follow-ups: the "not in a guild" case (no banner: today the guild features
  simply run and miss), the digit reader on other resolutions than the owner's Mac (templates
  are size-normalised but only checked at 3024x1709), the new-adventure interface style.
- Linux: overlay without capture exclusion (top strip only), X11 input shape untested.
