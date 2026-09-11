"""Entry point. DPI awareness is set before any other import that touches the screen."""

from __future__ import annotations

import sys

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def main() -> int:
    """`python -m firestone_bot [--start]`: --start presses START as soon as the window is up
    (unattended / login-item use). The Windows exe started with --start first re-creates
    itself outside the job of whatever launched it (platform/detach.py), so closing or
    updating that program does not end the run."""
    import os

    from firestone_bot.platform import detach

    args = sys.argv[1:]
    frozen = bool(getattr(sys, "frozen", False))
    if detach.should_detach(args, frozen, sys.platform) and detach.relaunch_detached(
        sys.executable, args, os.path.dirname(sys.executable)
    ):
        return 0  # the detached instance takes over
    from firestone_bot.app import main as app_main

    return app_main(autostart="--start" in args)


if __name__ == "__main__":
    sys.exit(main())
