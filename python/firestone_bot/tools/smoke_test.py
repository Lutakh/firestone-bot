"""Live smoke test for the platform and vision layers (plan 4.3). No clicks.

    python -m firestone_bot.tools.smoke_test --move 56,777 --out captures/smoke.png

Finds the window, prints platform/client/scale, captures, runs every atlas probe, then moves
the mouse to the logical point and saves a capture with a cross drawn at the real cursor
position so the result can be checked visually.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time

from firestone_bot.platform.dpi import set_dpi_aware

DPI_MODE = set_dpi_aware()


def main(argv: list[str] | None = None) -> int:
    from firestone_bot.platform import capture, process
    from firestone_bot.platform import input as inp
    from firestone_bot.platform.window import activate, find_game_window
    from firestone_bot.vision import atlas
    from firestone_bot.vision.atlas import Point, Probe
    from firestone_bot.vision.probes import pixel_search_in
    from firestone_bot.vision.viewport import Viewport

    ap = argparse.ArgumentParser()
    ap.add_argument("--move", help="logical x,y to move the mouse to")
    ap.add_argument("--out", default="captures/smoke.png")
    args = ap.parse_args(argv)

    win = find_game_window()
    vp = Viewport(win.client)
    print(f"dpi={DPI_MODE} platform={process.detect_platform(win.exe)} exe={win.exe}")
    print(f"client={win.client} maximized={win.maximized} fullscreen={win.fullscreen}")
    print(f"canvas scale={vp.scale:.4f} rel_scale={vp.rel_scale:.4f}")

    activate(win)
    time.sleep(0.5)
    t0 = time.perf_counter()
    img = capture.grab(win.client)
    print(f"capture {img.shape} in {1000 * (time.perf_counter() - t0):.1f} ms")

    for name in dir(atlas):
        v = getattr(atlas, name)
        if isinstance(v, Probe):
            rect = vp.probe_rect_screen(v)
            t0 = time.perf_counter()
            hit = pixel_search_in(
                img, win.client, rect, v.color, v.variation + vp.variation_boost()
            )
            dt = 1000 * (time.perf_counter() - t0)
            print(f"probe {name:<16} -> {hit or 'miss'} ({dt:.2f} ms)")
        elif isinstance(v, Point):
            print(f"point {name:<16} -> screen {vp.to_screen(v.x, v.y, v.anchor)}")

    if args.move:
        x, y = (int(v) for v in args.move.split(","))
        sx, sy = vp.to_screen(x, y)
        inp.move(sx, sy)
        time.sleep(0.3)

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        print(f"moved to logical ({x},{y}) -> screen ({sx},{sy}); cursor now at ({pt.x},{pt.y})")
        img = capture.grab(win.client).copy()
        cx, cy = pt.x - win.client.x, pt.y - win.client.y
        img[max(0, cy - 1) : cy + 2, max(0, cx - 25) : cx + 26, :3] = (0, 0, 255)
        img[max(0, cy - 25) : cy + 26, max(0, cx - 1) : cx + 2, :3] = (0, 0, 255)
        capture.save_png(img, args.out)
        print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
