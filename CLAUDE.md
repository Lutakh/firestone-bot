# Firestone Bot

Python 3.12 bot for Firestone Idle RPG (Steam / Epic), ported from the original AutoHotkey
v1.1 bot. The AHK sources live in the git history of `main`; this branch holds only the port.

Before working on the code, read `docs/PYTHON_REWORK_PLAN.md` (analysis of the AHK code,
architecture, execution plan, open decisions, conventions). Progress is tracked in
`docs/PARITY.md`, measurements in `docs/MEASUREMENTS.md`.

Everything in the repository is in English: code, comments, GUI text, docs, commit messages.

Layout: `firestone_bot/` (package), `tests/` (pytest), `firestone-bot.spec` (PyInstaller),
`.github/workflows/build.yml` (CI). Dev setup: `python -m venv .venv`,
`.venv\Scripts\pip install -e .[dev]`, `ruff check .`, `pytest -q`.
