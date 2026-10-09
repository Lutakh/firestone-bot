# Backlog (owner requests, not yet done)

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
- Chest icons without a reference (new style, `vision/chest_refs.py`): Titan, Platinum,
  Galaxy, Cosmic, Nebula, Solar, the Oracle gift and the Mystery box were not in the
  owner's bag on 2026-09-07; they fall back to the AHK colour search, which proved
  unreliable in this style (see MEASUREMENTS). To record from the bag when the owner owns
  one (tools: capture the Chests tab, `chest_grid.thumbnail` of the 96 px window).
- Liberation / Dungeon missions with something to do (2026-09-09): everything was already
  finished on the owner's account, so only the "nothing to start" path was verified live.
  The click on a card's green button saves `liberation-mission.png` / `dungeon-mission.png`
  in the diagnostics folder: use it to check the wait for the reward (`liberation_in_progress`
  still uses the AHK probes LIB_DONE / LIB_DONE_CLAIM).
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
- macOS memory (2026-09-07): the per-capture leak is fixed and the two full-frame copies
  (bitmap copy, float32 cast for thumbnails) were removed without a Mac at hand; to measure
  on the 4K Mac (expected well under the 0.7-1.3 GB seen before).
- Step recovery (done 2026-09-08, `Runner._step`, `Game.require_screen`): the shop,
  engineer, arena, quests, battle pass and research raise ScreenNotReached; the other town
  buildings still click blind after `tap()` (guardian, tavern, scarab, rituals, exotic
  merchant, alchemist): give each an entry probe. The engineer's new-war-machine animation itself was
  not captured (only its consequence, the arena looping on the garage).
- Level 50+ choosers (done 2026-09-08, verified live on the owner's Mac at level 51): the
  engineer and battles buildings open a centred chooser (engineer 3 cards, battles 2 cards);
  the arena card shows "Unlocks once you acquire at least 2 war machines" and is skipped for
  the game day. Still unverified: the same choosers at 4K and on Windows, the war-machine
  branch of the engineer, the events claim in the classic layout, and the classic bag close
  probe on the built-in 16:10 screen (misses, measurement inconclusive).
- Library research (rewritten 2026-09-08 for the tree of game 9.1.1, verified live on the
  Mac: slot 2 started from page 2): the finished state (a green button in the slot panel)
  has not been seen yet; if the game shows something else when a research completes, the
  slot reads "empty" and the node clicks fail harmlessly (popup closed, diagnostic saved).
  A locked second slot is untested. The Windows node colour (0x0D49DE) is covered by the
  tolerance but unverified there.
- Bottom-bar anchors (done 2026-09-08): Battle pass / Events are centre-anchored. Other HUD
  groups may hide the same error on non-reference aspects; only the 1920x1009 reference and
  16:9 clients have been checked. The events bell with a bell actually present is unverified
  on the Mac (probe moved off the gift's own red).
- Dialog content anchors (2026-09-09): centred dialogs' buttons that sit in the left or
  right third of the reference take an edge anchor from the thirds rule and land 64 px off
  on a 16:9 client (the mailbox delete button clicked beside on the Mac; fixed with
  `ANCHOR_CENTER` on the mail entries). Every atlas point inside a centred dialog with
  x < 640 or x > 1280 and no explicit anchor has the same latent error: audit them (the
  events list, event page, battle pass, character page, chest dialog, alchemist, guardian,
  tavern, arena, engineer, research popup were given centre anchors as they were hit).
- Events bell (2026-09-09): the gift's own red moves between x 595 and 608 and a one-pixel
  probe kept passing for the bell; the rect now sits above the gift and the classic layout
  counts red pixels (`bells.bell_in`, threshold scaled with the client). Still unverified
  with a bell actually present.
- Overlay on macOS (2026-09-09): hiding the click-through panel before a click under it
  brought the bot's own window over the game and the click landed on it (events button,
  mail icon); the panel is no longer hidden on macOS (`GameOverlay.click_through`). Windows
  keeps the hide, where the owner saw the click-through flags fail (2026-09-06).
- Restart noise: a run killed mid-cycle leaves its dialog open; the next start hits the
  main-menu cap once before recovering (choosers and the bag panel are now closed there,
  the town window is not, it gets closed by the first step recovery).
- Level gating follow-ups: the "not in a guild" case (no banner: today the guild features
  simply run and miss), the digit reader on other resolutions than the owner's Mac (templates
  are size-normalised but only checked at 3024x1709), the level regions in the classic
  interface style (measured in the new-adventure style only).
- Linux: overlay without capture exclusion (top strip only), X11 input shape untested.
- 1440p sweep (2026-09-09, client 2560x1302, aspect 1.97 against the reference 1.90): the
  layout was read as "new" on a classic account (the centred bottom bar's blue Fellowship
  shield entered the edge-anchored style probe; the mode button's label is read now), the
  events card bells missed at variation 3, the quests Claim rect sat past the button and the
  research slot zones landed on the neighbouring widgets (the running slot's "Speed up" gem
  button was clicked). All fixed and verified live. Still to check at this aspect: the map,
  the guild, the arena, the awakening and the hero upgrade screens.
- Blind clicks (2026-09-09): the shop check-in clicked two fixed points without any probe;
  at 2560x1302 the tab click missed and those two clicks opened the Steam checkout of a
  $4.99 bundle (nothing bought). The shop now finds its tabs and its Check In button as
  colour blobs. Every other `g.click()` that follows a bare `move_to` deserves the same
  audit, starting with the ones inside dialogs that also hold paid offers.
- Shop tab row (2026-09-09): the row is centred and its length depends on the account, so
  the tabs can only be addressed by rank (leftmost = bundles, rightmost = check-in) and the
  selected tab is not tan, i.e. not in the blob list. Reading the selected tab (a purple
  fill that no blob search matched yet) would make the order of the two steps free again.
- Town entry (2026-09-09, fixed): `open_town` returned nothing, so a cycle whose T never
  opened the town (a new war machine animation was playing, then the settings window was
  open) ran the whole town section by position on the main screen and clicked "Patch notes"
  while announcing the tavern and the scarab. `open_town` now returns whether the town is
  really there, never clicks the battlefield's neutral spot while a dialog is up, and the
  runner re-checks `town_is_open` before every town step (one recovery, then the step is
  skipped). The town features that opened a building with a plain `tap(..., expect=...)`
  now use `require_screen`. The same audit is worth doing on the map section, whose steps
  also click by position (`map_redeem`, `map_start`).

- Shop: read the tab icons rather than rebuilding the row from the pitch, so a future layout
  with uneven tabs cannot shift the indices again (2026-09-09).

- main_menu (done 2026-09-10): the "rate the game" pop-up is only closed through an X seen
  next to its brown title bar, and SafetyCap counts closes that change nothing. Still to do:
  capture a real rate pop-up (diagnostic `rate-popup-no-x.png`) to replace the brown-bar
  trigger, which also matches ordinary screens.

- Decorated Heroes auto switch-off (done 2026-09-28, `features/event_watch.py`): to verify at
  the event's end (~2026-10-02 10:00): does the card leave the active part of the list at
  once (a claim period that keeps it active would keep the switch on), and does the first
  cycle after the reset log two looks and "switch turned off" (`decorated-heroes-gone.png`)?
  `EVENTS_PAGE_CLOSE_X` (basic event page) was measured on diagnostics only and now decides
  that a page is another event's: if it misses live, a basic event active after the end keeps
  the switch on (no verdict). The wheel back to the list's top (`TOP_NOTCHES`) is not measured
  (the list held 3 cards and did not scroll); only 4 list slots are modelled (a 5th active
  event gives no verdict).
- Guardian enlightenment automation (done 2026-09-28): `GUARDIAN_ENLIGHTEN_COST` and the
  multiplier reads were measured on the owner's 1920x1009 client only (an unreadable cost only
  loses the x5/x10/x20 tiers). Unknown: an enlightenment cap per guardian (the button would go
  grey), and whether the event's challenge counts clicks or enlightenments (its 3 stay x1).
- Tavern plays on the counter and guild expedition logs (done 2026-09-28): whether Play stays
  green at 0 tokens is not measured (the bot now leaves at 0); `TAVERN_TOKEN_DIGITS` is unproven
  on other aspects (unreadable = the digits' pixels). Claimed vs started expeditions are not
  told apart (no probe on the expeditions dialog).
- Scarab game plays are still counted on any pixel change of the free-coin counter
  (`scarab._wait_counter_change`), the weakness the crystal and the tavern had: read the number
  like `token_counter` does.

- Game launch held by the store (done 2026-09-29, a35aea8): the Epic launcher is closed and
  reopened when a launch does not start the game, and a failed launch is retried every 10 min
  instead of stopping the bot. Not seen live yet: the next Firestone update installed at a
  scheduled restart shows whether a fresh launcher clears the "Application is busy" window
  (closing Epic during a long download interrupts it; Epic is expected to resume it).

- Research priorities and meteorite research (done 2026-09-29): locked firestone boxes were
  first seen on 2026-10-09 (tree XIV, grey boxes reading "Locked", not counted by the scan; their
  popup: "Research is locked / Requires:" each research of the column before at the unlock
  level, no Research button). The right-most-then-top choice never started the third box of
  column 1 and column 2 stayed locked for 31 h: within a column the research busy longest ago
  (seen running or started; session memory) now goes first. Locked meteorite
  nodes were never seen. The 24 h watch (2026-09-29) counted 25 starts and no error. Icon
  references come from the owner's Windows captures (colour-cast correction for the Mac is
  modelled, not measured). What the meteorite popup does right after Research was handled both
  ways; one live purchase worked. Meteorite names are the wiki's (Weak Boss, All Attributes...);
  the in-game meteorite names are only confirmed for Tank specialization and Attribute armor.
  Trees past firestone XIII and meteorite X were never seen (they reuse the same names).

- Meteorite purchases (fixed 2026-10-09): 2026-10-04 00:10, "810" read when the tab opened,
  an 800 level bought, 29 left (the node's level up by one): the exact-drop check called it
  unconfirmed and meteorite research stayed off for five days. A drop other than the cost is
  confirmed by the node's level when it is smaller than the cost (never when larger); an
  unconfirmed click pauses 6 h (Discord heartbeat), the third in a row turns it off.

- Battle pass Claim buttons under a labelled tile ("100%", "5%") sit 22 px lower (Qualitas,
  2026-10-09, Windows 1080p): fixed (bands widened, click in the button's middle, a claim counts
  once the button is gone), awaiting Qualitas's confirmation.

- Celestial chests (fixed 2026-09-29, a user's report; verified live 2026-10-01): "Nebula and
  Higher" / "Cosmic and Higher" opened every celestial chest (AHK ladder). On the owner's game
  "Nebula and Higher" opened Solar x30, Lunar x30 and Comet x27 and kept Nebula x4 (the owner's
  setting is back to "Don't Exclude Any"). Solar and Nebula keep the colour search (it hit the
  right slots, docs/MEASUREMENTS.md 2026-10-01); icon references for them are not added: the
  chest grid slides its window by 4 px, and 2 px off that grid Solar reads 11 levels away (the
  limit is 10). Comet matched at 9.1 that day: a finer slide (2 px) would make every chest icon
  sturdier. Galaxy and Cosmic were never in the owner's bag.
