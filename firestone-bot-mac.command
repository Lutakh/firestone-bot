#!/bin/bash
# Firestone Bot launcher for macOS (run from source). Double-click in Finder or run it from a
# terminal. Creates .venv on first use (needs python3.12 with Tk: `brew install python@3.12
# python-tk@3.12`), then starts the GUI from this folder (settings.ini lives here).
#
# Permissions: the app that runs this script (Terminal, iTerm...) needs Screen Recording and
# Accessibility in System Settings > Privacy & Security. See README.md, section macOS.
set -e
cd "$(dirname "$0")"
PY=$(command -v python3.12 || command -v /opt/homebrew/bin/python3.12 || true)
if [ -z "$PY" ]; then
  echo "python3.12 not found: brew install python@3.12 python-tk@3.12"; exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "Creating .venv..."
  "$PY" -m venv .venv
  .venv/bin/pip install -q -e .
fi
exec .venv/bin/python -m firestone_bot
