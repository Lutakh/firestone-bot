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

## Repository and baseline

- Working checkout: `firestone-camp` (sibling of the earlier `firestone-bot` checkout).
- Active branch: `python-rework`.
- Starting commit: `11718e5`; synchronized to `7574193` (version 0.3.15) during integration.
- The branch advanced 18 commits since the mockup. Current source takes precedence over
  the old 117-option mockup mapping. The current interface maps all 119 editable options,
  plus persisted statistics and mailbox/day markers introduced upstream.
- Earlier separate retro implementation: `codex/retro-interface`, commit `634fccf`.
  Its isolated Tk 9 layout fixes can be reused without reverting current bot features.

## Architecture

- **Camp:** actual session state, latest activity, completed cycle and duration, real daily
  quotas and environment checks. No estimated completion times or fabricated activity.
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
The isolated preview is closed. Implementation work is finished; do not restart or
duplicate it. Any publication retry must push without force and verify the remote commit.
