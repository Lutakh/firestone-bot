"""Save a lossless PNG of the game client area plus a metadata JSON next to it.

python -m firestone_bot.tools.capture_tool --out captures/probe.png
python -m firestone_bot.tools.capture_tool --out captures/screen.png --full-screen
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime

from firestone_bot.platform.dpi import set_dpi_aware

DPI_MODE = set_dpi_aware()  # must run before mss / window code is imported


def main(argv: list[str] | None = None) -> int:
    from firestone_bot.platform import capture
    from firestone_bot.platform.window import Rect, find_game_window, screen_size

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="PNG path")
    ap.add_argument("--full-screen", action="store_true", help="capture the whole primary screen")
    args = ap.parse_args(argv)

    win = find_game_window()
    rect = win.client
    if args.full_screen:
        sw, sh = screen_size()
        rect = Rect(0, 0, sw, sh)
    img = capture.grab(rect)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    capture.save_png(img, args.out)
    meta = {
        "captured_at": datetime.now(UTC).isoformat(),
        "dpi_mode": DPI_MODE,
        "capture_rect": asdict(rect),
        "window": asdict(win),
        "image_shape": list(img.shape),
    }
    with open(os.path.splitext(args.out)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
