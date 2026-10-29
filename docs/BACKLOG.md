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
  (seen running or started; session memory) now goes first. Locked meteorite nodes
  were first seen on 2026-10-09 (tree XI, after tree X was maxed: grey icons, a dark ring,
  dark lines, "0"): the bot finds only the cyan-ringed nodes ("4 nodes"), so a locked
  priority is "not found in this tree" and its unlock path is never walked; the next
  priorities are bought instead. To do: detect the grey nodes and name them by the
  layout, then let a locked priority buy the node before it. The 24 h watch (2026-09-29) counted 25 starts and no error. Icon
  references come from the owner's Windows captures (colour-cast correction for the Mac is
  modelled, not measured). What the meteorite popup does right after Research was handled both
  ways; one live purchase worked. Meteorite names are the wiki's (Weak Boss, All Attributes...);
  the in-game meteorite names are only confirmed for Tank specialization and Attribute armor.
  Trees past firestone XIII and meteorite X were never seen (they reuse the same names).

- Gems spent by the bot (three users, 2026-10-22: "missions finished with gems" since a
  game update). The map's early completion was decided by a brown pixel at variation 0
  (paid) and an orange one (free); the paid button is orange too (the owner's "Refresh
  Now 120" and the research popup's "Complete instantly" carry a purple gem). Fixed: no
  click believed free when a gem shows in the button (vision/gems.py, read twice) for the
  mission speed-up, the map refresh, the mission Start, the guild's free pickaxes, the
  tavern's Play and the daily shop's free box; a gem dialog after a speed-up click is
  never confirmed (free speed-ups off for the run, important heartbeat); a paid map reset
  (MapReset, opt-in) happens once a visit. The mission dialog of today's interface was
  never captured (mission-paid-speed-up.png will show it). Left from the gem audit
  (low): the chaos rift reads its free icon before the paid one (its icons share a rect,
  not measured together), the arena's buy-more popup has one probe, the personal tree
  clicks blind, the map step does not prove the map is open.

- Research never started on game 9.1.3a (report VNHYHL, the first sent with the Send report
  button, 2026-10-22): the popup's Research button and X moved ~67 px lower (MEASUREMENTS
  2026-10-22); "shows no Research button" for every box, then a silent 15 min pause. Fixed:
  both are located; a search where boxes answered "no button" is retried in 3 min with the
  heartbeat at the fourth; a popup left open after a press is closed before the panels are
  read. To check with a 9.1.3a capture: after a press, the slots-occupied window, the
  meteorite popup (measured 2026-10-28, see below). Follow-up from the same report: the
  guild step ran blind when its icon click was lost (0.4% of cycles, owner 0.5%) or a layer
  stayed over the town; the crystal tap then hit the hero mode button. Done 2026-10-28: the
  guild is opened with require_screen (retried once from the main screen, else skipped).

- Mystery boxes / Oracle's gifts not opened on the latest game version (Qualitas's video,
  Steam, classic style, 2026-10-22): the gift dialog's x1 sits ~50 px lower (logical
  850..1068 x 912..982) and the AHK click (914,898) landed above it. Fixed: the green
  buttons are located in GIFT_BUTTON_ROW (both rows), centre-anchored, the rightmost
  clicked; the AHK points stay as the fallback. Not seen yet on the latest version: the
  gift result screen (open more) and, in the new style, the dialog's X (its tap point
  NS_CHEST_DIALOG_CLOSE 1413,86 falls inside the wider new dialog; its X is near
  1585,84). The chest row NS_CHEST_BUTTON_ROW has the same per-corner anchors.

- New mission dialogs (Steam has the game update, Epic not yet; the owner's crops,
  2026-10-22). In progress: a red Cancel left of an orange Speed up with a gem and a price
  (paid with 1:17:16 left), so the AHK rule "orange = free" picked the paid button; the
  v0.3.31 gem guard catches its gem at every aspect checked (margin 1.6x at 5:4, 3.4x at
  1920x1009). Start: Start mission, then Complete instantly (gem) to its right, as before.
  Fixed now (the owner's setup unchanged): a popup neither brown nor orange is captured
  (mission-dialog-unknown.png) and closed instead of left open under the next map clicks;
  a start popup still showing after Start is closed, and when it stays, the map search
  stops (mission-start-stuck.png); the in-progress popup is read once it has scaled in.
  To do with one uncropped 1:1 Steam capture of the new in-progress, start and free
  dialogs: centre anchors for the MR_* / MS_* dialog entries (thirds-rule right/bottom
  anchors put them 63 px off at 16:9, worse at 21:9, 4:3, 5:4), MR_MORE_THAN_3_MIN at
  variation 2 (the exact brown covers ~6 of 41 band rows), the free state's look.
  2026-10-28: 16:9 works as is (report ANHNX9 at 1920x1080: 29 in-progress reads, 11 free
  speed-ups, 21 starts, no gem spent); the in-progress and start popups are now captured
  once a run (mission-in-progress.png, mission-start-popup.png) for the anchors at 16:10,
  4:3 and 21:9, where they are 60-250 px off.

- Meteorite research dead on game 9.1.3a (the owner's Epic game since 2026-10-23 15:26:
  111 hourly "the popup shows an unknown research", 20,581 meteorites unspent; report
  ANHNX9, Steam, 2026-10-25: "not recognising Raining Gold"): the popup draws the icon
  bigger and higher (MEASUREMENTS 2026-10-28). Fixed: both places read, a loose match
  guarded by the runner-up for icons whose light shows on the panel; the line names the
  closest research and its distance; "no icon at all" is a runner-up of the loose match
  (a few specks on an empty panel read Mana Heroes in trees without Damage Specialization).
  Not seen on 9.1.3a yet: the tree right after a purchase (the pressed node turns into a
  full gold disc on the captures; if it stays gold, the visit ends after that purchase and
  captures meteorite-after-purchase.png once a run, and a counter drop smaller than the
  cost cannot be confirmed by the node's level: 6 h pause), the 26 other popup icons. The
  owner's Raining Gold is grey-locked in tree XI (the locked-nodes follow-up above).

- Arena of Kings never run on a 1920x1080 client (report ANHNX9, 2 of 2 tries "did not
  show"): its X probe was edge-anchored on a centred dialog. Fixed: every arena entry is
  centre-anchored (same points at 1920x1009). Taller clients (16:10) are unverified: the
  battle result screen was never seen there; a claim button that never shows now ends the
  arena after SafetyCap x 20 s (180 s at most, also with SafetyCap 0) with
  arena-battle-miss.png, instead of waiting forever or tapping on blind.

- World map at 16:9 (reports ANHNX9 and PPJMWR, 2026-10-25..28; PPJMWR: "the bot doesn't
  work properly in the map", Epic fullscreen 1920x1080, coordinates mode, no capture: the
  bot ran from WinRAR's temp folder). A game started at 16:9 draws the map fitted to the
  width, 1009/1080 of the size the mission points were measured at (MEASUREMENTS
  2026-10-28). Fixed: the landmark measures the map's scale at every alignment (kept when
  no reference wins clearly, measured also once the alignment is off) and the coordinates
  are scaled around the centre; an offset too short to drag (under 10 px) no
  longer turns the alignment off for the run; detection mode maps a label through the
  centre anchor (it was up to 45 px off at 1080); a label whose digits are cut in two
  ("15:55") is found. Left: MR_NO_MISSIONS never matches (the empty map is tapped twice and
  saves mission-dialog-unknown.png; proposed: a probe on the panel's navy band,
  MR_PANEL (60,220)-(240,240) 0x163059); the gem guard after a free speed-up fires on a
  purple mission's Rewards (owner, 8 times since 2026-10-22, no gem spent; proposed: no
  gem in the Okay band = rewards); the zoom knob row is right-anchored on a bottom-centre
  slider (reads the home value at 1080 by chance). PPJMWR's case is unproven until a
  report from a real folder.

- Game window not in front (owner, 2026-10-28: "do something for this case instead of
  clicking in the void"): on 2026-10-25 17:18..00:34 the game could not be brought to the
  foreground (5,605 warnings) while the bot sent some 3,000 clicks and 2,000 T presses to
  whatever window was in front. Done, not verified live: on Windows every click, key and
  wheel notch is checked first (foreground.py); when three activations fail nothing is
  sent, one line names what is in front by its exe and window class (never its title), one
  coarse capture (game-not-in-front.png, about 240 px wide, no readable text) and, after
  30 s, one important heartbeat; the bot tries again every 5 s and goes on by itself. A due
  restart (scheduled or asked for) is done meanwhile only when the game itself is in the way
  (hung, or a dialog of the game), else once the game is in front, also when the cycle that
  finds it due starts behind the other window; a relaunch whose start screen waits behind
  another program's window is waited for, not killed as a failed launch (review
  2026-10-28). What held the front on 2026-10-25 is unknown: a dark layer at 27 % over a
  live game that outlived three relaunches (the Xbox Game Bar, a GPU overlay?); the next
  "Paused:" line will name it. Left: a window Windows will not let the bot replace (an
  elevated one) now pauses the bot where a click on the game used to take the front back (a
  click on the game's title bar, hit-tested, would); a "new cycle" of the mouse guard during
  the start-button wait of a restart abandons the restart and leaves the game on its start
  screen, which main_menu does not handle (older than the guard); macOS and Linux
  unchanged.

- Antivirus (several players, 2026-10-28: Microsoft Defender quarantines FirestoneBot.exe as
  Trojan:Win32/Bearfoos.B!ml, a machine-learning verdict; microsoft/apm#487 has the same):
  the exe carries a version resource (Lutakh, Firestone Bot, the version, the license's
  copyright line), PyInstaller is pinned (6.22.3) and the Windows CI job compiles its
  bootloader from source (the stock one stays when that fails, a warning says which one was
  used), a smoke test runs the built exe, a `virustotal` job that nothing waits for gives the
  exe to VirusTotal (tools/virustotal.py, secret VT_API_KEY, set by the owner 2026-10-28) and
  puts the verdict in the run summary and, on a tag, the report link in the release notes,
  SHA256SUMS lists the exe too, and the README tells players how to check, restore and report
  it. This branch is MIT since 2026-10-28 (LICENSE; Deaeth85 and GeSpot1, authors of the AHK
  bot, agreed; main, the AHK bot, has no license). Not done: optimize=2 (the exe 17.6 % smaller, its
  effect unknown, needs a live run), append_pkg=False (every installed updater would leave
  the new FirestoneBot.pkg behind). The owner's levers: report each release's exe to
  Microsoft (WDSI, as a software developer; 0.3.34 prepared in dist/wdsi-0.3.34, owner's
  machine) when Defender or VirusTotal flags it (the owner's Defender has cloud protection
  off and cannot reproduce the players' verdict); code signing by SignPath Foundation
  (docs/CODE_SIGNING.md: the application;
  then the README section and the CI step). First release with the compiled bootloader: run
  the CI artifact on the owner's PC before the tag. SignPath prerequisites done 2026-10-29
  (the privacy policy in the top banner until closed once, in Workshop > Help and linked from
  the heartbeat card and the report dialog; the AutoUpdateCheck switch; python-rework
  default branch; the owner's 2FA, already on): the application is the owner's
  (docs/CODE_SIGNING.md). Not done: an imported gui_state.json is overwritten by the
  running window's state at the first exit (MainWindow read it before the start-up import
  copied it; older than this), so its layout and the privacy notice's closed mark are
  lost. Third-party
  notices: the archives carry LICENSE, numpy's license files (its dist-info, collected by
  PyInstaller) and Tk's license.terms, but not the other notices: the Python runtime (PSF-2.0,
  which asks that its license agreement be kept; the Windows Python's LICENSE.txt also covers
  the OpenSSL, libffi and MSVC runtime DLLs it brings), psutil, customtkinter, mss,
  darkdetect, six, packaging and, in the macOS archive, pyobjc (BSD/MIT, which ask for their
  notice in binary copies); certifi is MPL-2.0, which also asks that users are told where its
  source is; pynput (LGPL-3.0) and, in the Linux tarball, python-xlib (LGPL-2.1+) also ask
  that users can swap them, hard inside the PYZ. Build the notice set from what PyInstaller
  collects on each platform, not by hand; not done.

- Other findings of the 2026-10-28 log review (owner, ANHNX9), not done: an empty mailbox
  opened every cycle for hours while its bell stays lit (512 visits in 17 h); ANHNX9's
  Scarab game waits 23 s for a Play button that never turns green, every cycle (no token?);
  after the 10th scarab play the screen is left open (the next step recovers); a fresh
  install opens the shop every cycle until the first daily reset is seen; the routine
  liberation / dungeon captures fill the 50 MB diagnostics budget in two days; a bot run
  from a temp folder (WinRAR) loses its settings, logs and updates (proposed: a warning at
  start-up).

- Send report (owner request, 2026-10-22): a button of the bottom bar uploads a zip of the
  logs, the newest captures, the settings without DiscordID/ClientID and the last logged
  environment to fs-bot-logs.lutak.ovh/api/report (docs/REPORT_API.md); the player gets an
  ID for Discord, or saves the zip when the upload fails. The environment is logged as an
  `Environment:` line by the environment check and at every cycle when it changed.

- Heartbeat slowing the bot (owner, 2026-10-22; why it is off by default): every message
  was sent by the bot's own thread, which waited for fs-bot-logs.lutak.ovh (up to 10 s a
  message, unbounded while a DNS lookup hung), about 35 places a cycle. Fixed: messages
  go to a queue of 32 sent by a background thread (5 s timeout); a full queue drops them,
  and after a failed send none is tried for 5 min. The exit message gets 2 s at most.

- Research popups whose close button does not read (three users' logs, 2026-10-22: "the
  popup of <box> did not open", then every other box "lost from view"): a popup is now
  told by its close button, its green Research button or the dim over the library's
  close button, and closed by a tap beside it. Why their close button does not read is
  unknown (a research-popup.png of theirs would show).

- Chaos rift restarts with game restarts off (a user, 2026-10-22): asked-for restarts obey
  RestartGame; the stuck Hit button waits for a new game process; a relaunched game is
  maximized again when it was (Windows). Wish: switch the chaos hit amount to the most
  (like the hero upgrade's next milestone), and the same for the exotic merchant.

- Research idle for whole nights (several users, 2026-10-21; Qualitas's video: Tree III left
  at its end, both slots free, the paused visits saying only "slot 1 free / slot 2 free").
  Found live: a Research press with no free slot (a finished research not claimed counts as
  busy) opens "Your current research slots are occupied" over a dimmed screen; the bot did
  not know it, closed nothing, and every tap and wheel after it went to that window. Fixed:
  the window is closed and the search stops, any other window ends the search with a
  capture, every box tried is listed in the "no research could start" line, failed searches
  are retried in 3 min (three times) with an important heartbeat at the fourth, paused visits
  say why. Why the users' bots took a busy slot for a free one is still unknown: their
  `Research:` log lines and `research-*.png` captures will tell.

- Meteorite purchases (fixed 2026-10-09): 2026-10-04 00:10, "810" read when the tab opened,
  an 800 level bought, 29 left (the node's level up by one): the exact-drop check called it
  unconfirmed and meteorite research stayed off for five days. A drop other than the cost is
  confirmed by the node's level when it is smaller than the cost (never when larger); an
  unconfirmed click pauses 6 h (Discord heartbeat), the third in a row turns it off.

- Battle pass Claim buttons under a labelled tile ("100%", "5%") sit 22 px lower (Qualitas,
  2026-10-09, Windows 1080p): fixed (bands widened, click in the button's middle, a claim counts
  once the button is gone), awaiting Qualitas's confirmation.

- Chest step (a user's suggestion, 2026-10-28: check whether the bag is empty instead of
  going through the whole list): done, not verified live. The visible slots are read once
  (two reads that agree) and a chest with an icon reference is tried only when a slot holds
  it; chests without one are still searched by colour; no wheel when the list ends in view.
  Reads that disagree, the bag's X not seen, a dry run, the first visit of a run and one an
  hour go the old way (a full check counts once it saw the bag's X). Expected 21.3 s -> about 6 s a visit on the owner's account
  (MEASUREMENTS 2026-10-28). To check live: the "the bag shows ..." line against the bag, a
  run with a chest to open, bag-look.png if it ever shows. Left: opening the bag takes 3.6 s,
  probably 2.5 s of it in waits that run out (wait_still on the animated battlefield, the
  click on a Chests tab that is already open; not traced); a grid read is 0.2 s of Python
  loops (an integral image would make it a few ms).

- Celestial chests (fixed 2026-09-29, a user's report; verified live 2026-10-01): "Nebula and
  Higher" / "Cosmic and Higher" opened every celestial chest (AHK ladder). On the owner's game
  "Nebula and Higher" opened Solar x30, Lunar x30 and Comet x27 and kept Nebula x4 (the owner's
  setting is back to "Don't Exclude Any"). Solar and Nebula keep the colour search (it hit the
  right slots, docs/MEASUREMENTS.md 2026-10-01); icon references for them are not added: the
  chest grid slides its window by 4 px, and 2 px off that grid Solar reads 11 levels away (the
  limit is 10). Comet matched at 9.1 that day: a finer slide (2 px) would make every chest icon
  sturdier. Galaxy and Cosmic were never in the owner's bag.
