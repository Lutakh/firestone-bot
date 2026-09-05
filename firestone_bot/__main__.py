"""Entry point. DPI awareness is set before any other import that touches the screen."""

from __future__ import annotations

import sys

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def main() -> int:
    """`python -m firestone_bot [--start]`: --start presses START as soon as the window is up
    (unattended / login-item use)."""
    from firestone_bot.app import main as app_main

    return app_main(autostart="--start" in sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
