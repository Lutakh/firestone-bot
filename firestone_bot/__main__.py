"""Entry point. DPI awareness is set before any other import that touches the screen."""

from __future__ import annotations

import sys

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def main() -> int:
    from firestone_bot.app import main as app_main

    return app_main()


if __name__ == "__main__":
    sys.exit(main())
