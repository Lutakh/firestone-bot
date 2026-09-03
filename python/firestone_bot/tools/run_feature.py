"""Run one feature module alone against the live game (plan 4.4).

    python -m firestone_bot.tools.run_feature check_mail
    python -m firestone_bot.tools.run_feature check_mail --dry-run --fast
    python -m firestone_bot.tools.run_feature main_menu --settings ../settings.ini

Feature names are module names under firestone_bot.features; the function called is the
module's snake_case function of the same name (or the single public function it defines).
Every action is traced to stdout; `--dry-run` disables input (window/capture still real).
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import logging
import sys
import time

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def resolve(name: str):
    mod = importlib.import_module(f"firestone_bot.features.{name}")
    if hasattr(mod, name):
        return getattr(mod, name)
    funcs = [
        f
        for n, f in inspect.getmembers(mod, inspect.isfunction)
        if f.__module__ == mod.__name__ and not n.startswith("_")
    ]
    if len(funcs) != 1:
        raise SystemExit(
            f"{name}: cannot pick the entry function among {[f.__name__ for f in funcs]}"
        )
    return funcs[0]


def main(argv: list[str] | None = None) -> int:
    from firestone_bot.game import BotStopped, Game
    from firestone_bot.settings import Settings

    ap = argparse.ArgumentParser()
    ap.add_argument("feature")
    ap.add_argument("--settings", default="../settings.ini")
    ap.add_argument("--dry-run", action="store_true", help="no mouse/keyboard input")
    ap.add_argument("--fast", action="store_true", help="sleeps x0.1 (dry-run only)")
    ap.add_argument("--set", action="append", default=[], help="Name=Value override")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.load(args.settings)
    for kv in args.set:
        k, v = kv.split("=", 1)
        settings.set(k, v)
    g = Game(
        settings, dry_run=args.dry_run, time_scale=0.1 if (args.fast and args.dry_run) else 1.0
    )
    fn = resolve(args.feature)
    win = g.refresh_window()
    print(f"window client={win.client} scale={g.vp.rel_scale:.4f} dry_run={args.dry_run}")
    t0 = time.monotonic()
    try:
        fn(g)
    except BotStopped:
        print("stopped")
    print(f"{args.feature} done in {time.monotonic() - t0:.1f} s, {len(g.actions)} actions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
