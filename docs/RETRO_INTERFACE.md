# Retro interface

The native CustomTkinter interface uses warm enamel panels, graphite controls, brass highlights, numbered routine plates and a pixel flame emblem. All interface text and implementation are in English. The UI remains native Python; it does not embed a browser or require generated images or downloaded fonts.

## Navigation

- **Overview → Routines** links directly to Town, Guild & tree, Missions, and Heroes & chests. Counts show enabled configuration switches, not inferred execution progress.
- **Overview → Diagnostics** retains environment checks, account/guild levels, daily counters and limits.
- **Overview → Journal** retains the complete bounded activity log, copy, clear, follow, and open-file actions.
- The **session console** remains visible on every page. It shows the actual activity, last completed cycle, elapsed session time, Start, Simulate, Stop, and the three latest log entries.
- **Settings** contains the existing advanced controls and Light/Dark/System appearance selection. Fresh installations start with the cream Light palette; saved appearance choices remain respected.

Routine controls still use the existing Binder, including inverted legacy flags, validation, automatic saving and changes deferred while running. A simulation remains a dry run with game input disabled. The interface does not invent completion estimates or change the order in which the engine executes features.

## Layout

The default window is 1360 × 860 with a minimum of 1100 × 720 logical pixels. The session rail remains visible while the central pages scroll. Setting descriptions wrap, option controls stack, checkbox groups reflow, and multi-action groups wrap into additional rows in narrower windows. Native pause/update dialogs inherit the same palette; the game overlay uses graphite and brass while retaining its platform behavior.

`theme.py` defines the shared design tokens and native widget defaults. `console.py` provides the persistent session panel and code-drawn emblem. `routines.py` defines the overview shortcuts and configuration counts. No application settings migration is needed.

On macOS with Tk 9, scrollbar and dropdown canvases paint through the normal event loop instead of entering nested idle loops. This prevents long blank-page delays while native controls and wrapped text are being laid out; other Tk platforms retain their existing draw behavior.

## Validation

Run `python -m pytest -q tests` in an environment with a display for the native GUI tests, plus `ruff check firestone_bot tests` and `ruff format --check firestone_bot tests`. GUI checks use temporary settings and inert callbacks; they do not start the game or run bot actions. Tests cover existing settings bindings, worker-state transitions, routine navigation, journal mirroring, and compact-window controls in Light and Dark modes.
