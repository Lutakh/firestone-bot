"""Print the game window geometry (plan 4.1).

python -m firestone_bot.tools.measure_reference
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from firestone_bot.platform.dpi import set_dpi_aware

DPI_MODE = set_dpi_aware()


def main() -> int:
    from firestone_bot.platform.window import find_game_window, pixels_per_point, screen_size
    from firestone_bot.vision.atlas import REF
    from firestone_bot.vision.viewport import Viewport

    win = find_game_window()
    vp = Viewport(win.client)
    sw, sh = screen_size()
    dpi = None
    if sys.platform == "win32":
        from firestone_bot.platform.win.window import window_dpi

        dpi = window_dpi(win)
    out = {
        "dpi_mode": DPI_MODE,
        "screen": [sw, sh],
        "window_dpi": dpi,
        "pixels_per_point": pixels_per_point(),
        "window": asdict(win),
        "ref": asdict(REF),
        "canvas_scale": vp.scale,
        "rel_scale": vp.rel_scale,
        "client_top_delta_vs_ref": win.client.y - REF.y,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
