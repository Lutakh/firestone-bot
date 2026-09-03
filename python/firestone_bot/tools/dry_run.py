"""Run one full cycle with input disabled and sleeps shortened; log every click/probe.

    python -m firestone_bot.tools.dry_run
    python -m firestone_bot.tools.dry_run --settings ../settings.ini --time-scale 0.02

The window and captures are real, so probes report what the live screen shows; only the mouse
and keyboard are inert. Loops that wait for a screen change (arena, liberation) would never
end in a dry run, so SafetyCap is forced to 3 unless already set.
"""

from __future__ import annotations

import argparse
import logging
import sys

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def main(argv: list[str] | None = None) -> int:
    from firestone_bot.game import BotStopped, Game
    from firestone_bot.runner import Runner
    from firestone_bot.settings import Settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default="../settings.ini")
    ap.add_argument("--time-scale", type=float, default=0.05)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.load(args.settings)
    if not int(settings.get("SafetyCap") or 0):
        settings.set("SafetyCap", 3)
    settings.set("Delay", "0")
    g = Game(settings, dry_run=True, time_scale=args.time_scale)
    runner = Runner(settings, g)
    runner.max_cycles = 1
    try:
        runner.main_script()
    except BotStopped:
        pass
    print(f"dry run finished: {len(g.actions)} actions, cycles={runner.cycles}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
