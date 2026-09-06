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
- Level gating follow-ups: the "not in a guild" case (no banner: today the guild features
  simply run and miss), the digit reader on other resolutions than the owner's Mac (templates
  are size-normalised but only checked at 3024x1709), the level regions in the classic
  interface style (measured in the new-adventure style only).
- Linux: overlay without capture exclusion (top strip only), X11 input shape untested.
