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
    import ctypes

    from firestone_bot.platform.window import find_game_window, screen_size
    from firestone_bot.vision.atlas import REF
    from firestone_bot.vision.viewport import Viewport

    win = find_game_window()
    vp = Viewport(win.client)
    sw, sh = screen_size()
    user32 = ctypes.windll.user32
    dpi = user32.GetDpiForWindow(win.handle) if hasattr(user32, "GetDpiForWindow") else None
    out = {
        "dpi_mode": DPI_MODE,
        "screen": [sw, sh],
        "window_dpi": dpi,
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
