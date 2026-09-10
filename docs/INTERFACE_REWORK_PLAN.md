# Fieldbook interface implementation

## User-approved scope

Implement the approved interactive Fieldbook mockup in the real native Python bot on
`python-rework`. Keep every supported bot function and setting, and use English throughout
the interface and code. Add a **Skin** dropdown at the end of the header after **Workshop**. Fieldbook,
Retro and Futuristic share the same navigation and behavior. Skin changes are presentation
only and survive application restarts. Finish with a commit on `python-rework` and publish
that branch; do not merge the earlier retro branch wholesale.

The user explicitly approved implementation on 2026-09-08 after reviewing the mockup.
No further design approval is needed for this scope.

The current follow-up keeps Camp as the launcher's default page, regardless of the last
saved page. Make only Camp more compact and remove its Files & application shortcut from
Account & guild. Other pages retain their layout. Skin changes still preserve the current
page, and the explicit `FIRESTONE_GUI_PAGE` development override remains available.

## Repository and baseline

- Working checkout: `firestone-camp` (sibling of the earlier `firestone-bot` checkout).
- Active branch: `python-rework`.
- Starting commit: `11718e5`; synchronized to `7574193` (version 0.3.15) during integration.
  The current Camp follow-up starts from `de72cb0` (version 0.3.16).
- The branch advanced 18 commits since the mockup. Current source takes precedence over
  the old 117-option mockup mapping. The current interface maps all 119 editable options,
  plus persisted statistics and mailbox/day markers introduced upstream.
- Earlier separate retro implementation: `codex/retro-interface`, commit `634fccf`.
  Its isolated Tk 9 layout fixes can be reused without reverting current bot features.

## Architecture

- **Camp:** compact default startup page with actual session state, latest activity,
  completed cycle and duration, real daily quotas and environment checks. No estimated
  completion times or fabricated activity. Files remain accessible through Workshop.
- **Automations:** searchable action library, category filters and one action editor.
  Preserve inverted flags, unknown legacy values, atomic orders/radios and dependencies.
- **Journal:** actual log buffer with follow, copy, clear view and open-log actions.
- **Workshop:** runtime/setup options, files/import, counters, appearance, updates and help.
- Persistent command dock: Dry run, Stop and Start bot use existing application callbacks.
- Skin selection updates presentation without restarting the runner or changing settings.
- Keep the main-thread Tk queue, autosave/deferred-save behavior, shortcuts and diagnostics.

## Work checklist

- [x] Synchronize `python-rework` and record the approved scope.
- [x] Implement semantic skin palettes, typography and shared controls.
- [x] Carry over and verify bounded Tk 9 layout/scrolling fixes.
- [x] Implement Automations using the current setting catalog and real feature gates.
- [x] Implement Workshop and preserve all existing application actions.
- [x] Replace shell with horizontal navigation and Skin dropdown after Workshop.
- [x] Implement Camp and separate Journal with real runtime data.
- [x] Preserve settings, log history and state across skin changes; clean up view callbacks.
- [x] Add focused regression tests for settings, navigation, skin persistence and runtime.
- [x] Run lint, formatting, full tests and native visual checks for all three skins.
- [x] Review the final diff and update user-facing documentation.
- [x] Prepare the validated change for delivery on `python-rework`.

## Coordination and ownership

- Primary agent: shell/MainWindow, Camp, Journal, Binder lifecycle, integration and commit.
- `skins_widgets`: `theme.py`, `widgets.py`, skin-specific tests.
- `automations_page`: automation catalog, Automations page, automation tests.
- `workshop_page`: Workshop page and focused tests/help wording.
- Agents share this checkout; do not overwrite another owner's in-progress files.

## Resume procedure

1. Read this file, `git status --short --branch` and `git diff --stat`.
2. Inspect live agent status if agents remain available; use their completed files rather
   than redoing work. Never discard uncommitted changes.
3. Check the boxes against the implementation and continue from the first incomplete item.
4. Use the current source catalog to verify option coverage and dependencies.
5. Run tests from this checkout. A usable development Python currently exists at
   `../firestone-bot/.venv/bin/python`; set `PYTHONPATH` to this checkout if needed.
   Native Tk checks on this host require execution outside the filesystem sandbox.
6. Do not run the live bot during GUI checks. Use isolated settings and inert callbacks.
7. Update this file before ending a partial session, including blockers and exact next steps.

## Progress notes

Implementation and validation are complete as of 2026-09-10. All 119 current editable
catalog options are represented. Upstream changes through `7574193` are retained,
including map opening/key settings, persistent cycle statistics, daily mailbox tracking
and shop-tab reconstruction. The map-opening `hotkey` choice was corrected to select the
keyboard path on the new layout.

Validation: 194 tests passed after the final upstream synchronization; Ruff lint,
formatting and whitespace checks passed. The final review also corrected search-entry
callback cleanup and documentation paths. All 42 focused GUI tests passed after that
correction, covering cleanup, skin switching, current editor, live settings, deferred saves
and session preservation.

Native macOS inspection covered Fieldbook, Retro and Futuristic, the Skin dropdown,
keyboard navigation, Camp, Automations and Workshop. The preview used temporary settings
and inert runner callbacks: no game actions were executed. Windows/Linux visual behavior
has not been inspected on this host.

Delivery target: `python-rework`, with the implementation commit titled
`Implement Fieldbook navigation with switchable interface skins`. Use
`git log --oneline -- docs/INTERFACE_REWORK_PLAN.md` to locate the exact delivery commit.
The isolated preview is closed. The original implementation is finished; do not restart or
duplicate it. Any publication retry must push without force and verify the remote commit.

## Current Camp follow-up

- [x] Open Camp on every launcher startup while retaining saved editor selections.
- [x] Add a startup regression for a saved Workshop page; retain the existing test that
  skin changes keep the active Journal page open.
- [x] Compact Camp and remove Files & application from Account & guild.
- [x] Run GUI regression tests and inspect Camp with isolated callbacks.
- [x] Review the validated follow-up for delivery on `python-rework`, without a release tag.

The follow-up is complete and validated on 2026-09-10. Camp uses a compact session strip,
side-by-side game checks and daily limits, and a final row for account/guild levels and
persistent cycle statistics. All runtime information and other shortcuts remain available.
Spacing changes are local to Camp; the shared command dock and other pages are unchanged.

Validation: 206 tests passed, and Ruff lint/formatting and whitespace checks passed.
Layout regressions cover all three skins at 1220x860 and 980x680, real macOS environment
labels, quotas and level locks, a missing game, crash controls and an update banner.
Native inspection confirmed the compact layout using isolated callbacks, and the preview
is closed. A cleanup regression also verifies that destroying Camp releases its refresh
callback. The explicit development page override in `app.py` is unchanged.

Delivery commit title: `Make Camp the compact startup overview`, published as `a5af192`.
The user subsequently authorized a release tag on 2026-09-10. Release `v0.3.17` includes
the compact Camp and macOS overlay click-through fix since `v0.3.16`; both package version
fields must match the tag. Do not repeat the completed implementation on a later resume.

## Global launcher search and restart-time display

Current user request: show the game's running time in Camp's Game checks using the same
age and fallback clock as the runner's restart decision. Replace the local Automations
search with a global launcher search above Camp Session. Search must find every setting,
page and action (including application updates) and reveal its control without invoking it.
The working branch is synchronized through `c25244e` (0.3.19).

- [x] Read-only runtime snapshot from App/Runner, matching active restart clocks.
- [x] Live game uptime and restart status in Game checks, with unavailable states.
- [x] Complete searchable catalog and exact option/action destinations.
- [x] Global search bar, overlay results, keyboard navigation and cleanup.
- [x] Remove local Automations search and its persisted hidden filter.
- [x] Verify search results, guards, layouts, skins and runtime polling; inspect native UI.
- [x] Update documentation, commit and push the validated changes on python-rework.

Completed on 2026-09-10. App reads process age on a background worker every five seconds,
including during a run. Runner exposes its cached interval and actual fallback timer without
changing restart decisions. Camp shows the game age separately from fallback timing and
labels missing/stale readings. Local Camp spacing and inline totals retain every value at
980x680, including warnings and the update banner, in all three skins.

The global search indexes all 119 options, saved runtime keys, pages, help and actions. It
reveals exact controls (including composite selections and update buttons) without invoking
them. Results overlay the page, support keyboard selection and all matching results, and
release callbacks/bindings when skins change. The old hidden Automations filter is removed.

Validation: the full suite passed 297 tests. After final destination refinements, all 31
focused catalog/native-search tests passed, including seven additional composite/read-only
navigation cases. Ruff lint, formatting and whitespace checks pass. Native macOS inspection
covered compact Camp in all skins, update lookup and navigation, exact INI-key lookup, and
Retro results. The isolated preview is closed; no game actions were executed. Other desktop
platforms were not visually inspected here.

Delivery commit title: `Add launcher-wide search and game restart timing`, on python-rework.
No new release tag is part of this follow-up. Do not repeat the completed implementation
when resuming; inspect Git status and the matching commit if publication needs verification.
