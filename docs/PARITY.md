# Parity checklist

Progress of the Python port against the AHK bot. See docs/PYTHON_REWORK_PLAN.md section 4.

## Plan steps

| Step | Status | Notes |
|---|---|---|
| 4.0 Environment setup | done (2026-09-03) | Python 3.12.10 venv, deps installed, capture self-test OK. See MEASUREMENTS.md |
| 4.1 Reference frame | done (2026-09-03) | REF=(0,31,1920,1009); Win11 client is at y=23, handled by the viewport. Map/mail probes still to confirm |
| 4.2 Scaling behaviour | done (2026-09-03) | Unity canvas 1920x1080, scale=min(w/1920,h/1080), edge anchors, no letterbox. Anchored viewport implemented. Wheel test deferred to `open_chests` port |
| 4.3 Platform + vision layers | done (2026-09-03) | `dpi.py`, `window.py` (win32), `capture.py`, `atlas.py`, `viewport.py`, `probes.py`, `input.py` exist with viewport/probe tests; `process.py`, `smoke_test.py`; 17 unit tests; live smoke test OK (mail icon, gear, map troop probe). INI tests come with 4.5 |
| 4.4 Feature modules | todo | |
| 4.5 Settings, GUI, runner | todo | |
| 4.6 Resolution runs | todo | |
| 4.7 Epic | todo | Epic build is the one currently installed and running |
| 4.8 Packaging and CI | todo | |
| 4.9 Linux | todo | |
| 4.10 Browser | todo | |

## Feature modules

| Module (AHK file) | Ported | Steam | Epic | Notes |
|---|---|---|---|---|
| (none yet) | | | | |
