"""Record the world-map landmark reference (vision/map_landmark.json) from the live game.

Open the map at its default zoom and position: the zoom slider's knob at its left end, the
map not dragged (a dragged map keeps its offset across closing and reopening it: on a client
where the bot's alignment works, let it align the map first). Then run:

    python -m firestone_bot.tools.map_landmark [name]

Before writing, the landmark is looked for with the references already in the file: one
that matches (correlation at least map_align.MIN_CORRELATION) with an offset beyond
map_align.TOLERANCE means the map is not at its default place for a client like this one,
and a warning says so (a reference recorded on a moved map would make every later alignment
drag a well-placed map off by as much). For a new kind of client that no reference matches
there is no automatic check: only the knob and your eye.

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


def _check_position(g: Game) -> None:
    """The map's place against the references already recorded (printed, never blocking:
    the operator may be replacing a reference that is off for this client)."""
    try:
        c, dx, dy = map_align.landmark_offset(g, map_align.load_landmark())
    except (OSError, ValueError, KeyError):
        print("position check: no reference recorded yet, nothing to compare with")
        return
    if c < map_align.MIN_CORRELATION:
        print(
            f"position check: no existing reference matches (correlation {c:.2f}); "
            "check the map's place by eye"
        )
    elif abs(dx) > map_align.TOLERANCE or abs(dy) > map_align.TOLERANCE:
        print(
            f"WARNING: the landmark sits ({dx}, {dy}) px from an existing reference "
            f"(correlation {c:.2f}): the map is probably not at its default place"
        )
    else:
        print(f"position check: at the existing reference's place (correlation {c:.2f})")


def main() -> None:
    g = Game(Settings.load("settings.ini"))
    g.focus()
    _check_position(g)
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
    # the new reference matches the screen it was taken from: this checks the capture only,
    # not the map's place
    c, dx, dy = map_align.landmark_offset(g)
    print(f"capture sanity check: correlation {c:.2f}, offset ({dx}, {dy})")


if __name__ == "__main__":
    main()
