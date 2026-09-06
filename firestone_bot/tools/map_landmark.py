"""Record the world-map landmark reference (vision/map_landmark.json) from the live game.

Open the map at its default zoom and position (close and reopen it after zooming out and
dragging it back; the bot's mission points must hit their icons), then run:

    python -m firestone_bot.tools.map_landmark [name]

The file holds one reference per client it was recorded on (the title is drawn at a
different size on the Mac and on the Windows clients); `name` defaults to the platform and
client size, an existing reference of that name is replaced.
"""

from __future__ import annotations

import json
import sys

from firestone_bot.features import map_align
from firestone_bot.game import Game
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas


def main() -> None:
    g = Game(Settings.load("settings.ini"))
    g.focus()
    rect = atlas.MAP_LANDMARK_RECT
    scale = atlas.MAP_LANDMARK_SCALE
    gray = map_align._gray_logical(g, rect, scale)
    c = g.window.client
    name = sys.argv[1] if len(sys.argv) > 1 else f"{sys.platform}-{c.w}x{c.h}"
    data = {
        "name": name,
        "rect": list(rect),
        "scale": scale,
        "w": int(gray.shape[1]),
        "h": int(gray.shape[0]),
        "gray": [int(v) for v in gray.round().flatten()],
    }
    try:
        with open(map_align.LANDMARK_PATH, encoding="utf-8") as f:
            old = json.load(f)
        refs = old.get("refs", [{"name": "mac-original", **old}])
    except (OSError, ValueError):
        refs = []
    refs = [r for r in refs if r.get("name") != name] + [data]
    with open(map_align.LANDMARK_PATH, "w", encoding="utf-8") as f:
        json.dump({"refs": refs}, f)
    print(f"landmark {gray.shape[1]}x{gray.shape[0]} '{name}' written ({len(refs)} references)")
    c, dx, dy = map_align.landmark_offset(g)
    print(f"self check: correlation {c:.2f}, offset ({dx}, {dy})")


if __name__ == "__main__":
    main()
