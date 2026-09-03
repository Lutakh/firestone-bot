"""Entry point. DPI awareness is set before any other import that touches the screen."""

from __future__ import annotations

import sys

from firestone_bot.platform.dpi import set_dpi_aware

set_dpi_aware()


def main() -> int:
    print("Firestone bot (Python port): GUI not implemented yet. See docs/PYTHON_REWORK_PLAN.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
