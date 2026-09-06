"""Record the world-map landmark reference (vision/map_landmark.json) from the live game.

Open the map at its default zoom and position (close and reopen it after zooming out and
dragging it back; the bot's mission points must hit their icons), then run:

    python -m firestone_bot.tools.map_landmark
"""

from __future__ import annotations

import json

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
    data = {
        "rect": list(rect),
        "scale": scale,
        "w": int(gray.shape[1]),
        "h": int(gray.shape[0]),
        "gray": [int(v) for v in gray.round().flatten()],
    }
    with open(map_align.LANDMARK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"landmark {gray.shape[1]}x{gray.shape[0]} written to {map_align.LANDMARK_PATH}")
    c, dx, dy = map_align.landmark_offset(g)
    print(f"self check: correlation {c:.2f}, offset ({dx}, {dy})")


if __name__ == "__main__":
    main()
