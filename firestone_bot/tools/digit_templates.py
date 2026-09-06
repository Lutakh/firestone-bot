"""Build (or extend) vision/digit_templates.json from numbers visible on screen.

    python -m firestone_bot.tools.digit_templates --region "100,146,135,175=36" ...

Each --region is a LOGICAL rect (x1,y1,x2,y2 in the atlas frame, top-left anchored) followed
by the label: one
character per glyph found left to right, '_' for a glyph to skip (a slash, a colon). The game
must show the numbers; --npy reads a saved client capture instead of the screen. With
--append the new cells are added to the existing templates (several samples per digit are
kept, from different font sizes, and matched independently).
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from firestone_bot.platform import capture
from firestone_bot.platform.window import find_game_window
from firestone_bot.vision import digits
from firestone_bot.vision.viewport import Viewport

TOP_LEFT = (0.0, 0.0)  # rects are given top-left anchored (the tool's own convention)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", action="append", required=True, help='"x1,y1,x2,y2=label"')
    ap.add_argument("--npy", help="client capture saved with numpy instead of the live screen")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--out", default=digits.TEMPLATES_PATH)
    args = ap.parse_args()

    win = find_game_window()
    vp = Viewport(win.client)
    if args.npy:
        img = np.load(args.npy)
    else:
        img = capture.grab(win.client)[:, :, :3].copy()
    templates: dict[str, list[np.ndarray]] = {}
    if args.append and os.path.exists(args.out):
        templates = digits.load_templates(args.out)
    for spec in args.region:
        rect, label = spec.split("=")
        x1, y1, x2, y2 = (int(v) for v in rect.split(","))
        cx1, cy1 = vp.to_client(x1, y1, TOP_LEFT)
        cx2, cy2 = vp.to_client(x2, y2, TOP_LEFT)
        glyphs = digits.digit_glyphs(digits.segment(img[cy1:cy2, cx1:cx2]))
        if len(glyphs) != len(label):
            print(f"{spec}: {len(glyphs)} glyphs found for {len(label)} labels, skipped")
            for g in glyphs:
                print("  glyph", g.x1 - g.x0, "x", g.height)
            continue
        for g, ch in zip(glyphs, label, strict=True):
            if ch == "_":
                continue
            templates.setdefault(ch, []).append(g.cell)
            print(f"{ch}: {g.x1 - g.x0}x{g.height} px")
    missing = [d for d in "0123456789" if d not in templates]
    digits.save_templates(templates, args.out)
    print(f"saved {sum(len(v) for v in templates.values())} cells to {args.out}")
    if missing:
        print("still missing:", " ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
