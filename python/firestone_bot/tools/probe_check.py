"""Replay atlas probes against a saved capture and report hits (plan 4.1).

The PNG must have been produced by capture_tool (its .json sidecar gives the capture rect).

    python -m firestone_bot.tools.probe_check captures/probe.png
    python -m firestone_bot.tools.probe_check captures/probe.png --probe 1260,780,1334,835,0AA008,3
    python -m firestone_bot.tools.probe_check captures/probe.png --point 1851,84 --point 56,777
    python -m firestone_bot.tools.probe_check captures/probe.png --ref-y 23   # try another REF top

--probe / --point values are LOGICAL (AHK) coordinates. With no --probe/--point, every Probe
and Point defined in atlas.py is replayed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace

import numpy as np

from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Point, Probe
from firestone_bot.vision.probes import pixel_at, pixel_search_in
from firestone_bot.vision.viewport import Viewport


def load_png(path: str) -> np.ndarray:
    """Load a PNG as BGRA (H, W, 4) without extra dependencies (uses tkinter's PhotoImage? no:
    uses a tiny pure-Python PNG reader via zlib)."""
    import struct
    import zlib

    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    pos = 8
    width = height = 0
    idat = b""
    color_type = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, depth, color_type = struct.unpack(">IIBB", chunk[:10])
            assert depth == 8, "only 8-bit PNG supported"
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    channels = {2: 3, 6: 4}[color_type]
    raw = zlib.decompress(idat)
    stride = width * channels
    out = np.zeros((height, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.uint8)
    for y in range(height):
        ft = raw[y * (stride + 1)]
        line = np.frombuffer(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)], dtype=np.uint8)
        line = line.astype(np.int16)
        if ft == 0:
            cur = line
        elif ft == 1:
            cur = line.copy()
            for i in range(channels, stride):
                cur[i] = (cur[i] + cur[i - channels]) & 0xFF
        elif ft == 2:
            cur = (line + prev) & 0xFF
        elif ft == 3:
            cur = line.copy()
            for i in range(stride):
                left = cur[i - channels] if i >= channels else 0
                cur[i] = (cur[i] + ((int(left) + int(prev[i])) >> 1)) & 0xFF
        elif ft == 4:
            cur = line.copy()
            for i in range(stride):
                a = int(cur[i - channels]) if i >= channels else 0
                b = int(prev[i])
                c = int(prev[i - channels]) if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pred) & 0xFF
        else:
            raise ValueError(f"bad filter {ft}")
        out[y] = cur.astype(np.uint8)
        prev = out[y]
    rgb = out.reshape(height, width, channels)
    bgra = np.zeros((height, width, 4), dtype=np.uint8)
    bgra[:, :, 0] = rgb[:, :, 2]
    bgra[:, :, 1] = rgb[:, :, 1]
    bgra[:, :, 2] = rgb[:, :, 0]
    bgra[:, :, 3] = 255
    return bgra


def parse_probe(s: str) -> Probe:
    x1, y1, x2, y2, col, var = s.split(",")
    return Probe(int(x1), int(y1), int(x2), int(y2), int(col, 16), int(var), f"cli:{s}")


def parse_point(s: str) -> Point:
    x, y = s.split(",")
    return Point(int(x), int(y))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--probe", action="append", default=[], help="x1,y1,x2,y2,RRGGBB,var")
    ap.add_argument("--point", action="append", default=[], help="x,y (prints colour there)")
    ap.add_argument("--ref-y", type=int, default=None, help="override REF.y for the mapping")
    ap.add_argument("--grow", type=int, default=1)
    args = ap.parse_args(argv)

    with open(os.path.splitext(args.png)[0] + ".json", encoding="utf-8") as f:
        meta = json.load(f)
    origin = Rect(**meta["capture_rect"])
    client = Rect(**meta["window"]["client"])
    img = load_png(args.png)
    ref = atlas.REF if args.ref_y is None else replace(atlas.REF, y=args.ref_y)
    vp = Viewport(client, ref)
    print(f"capture {origin}  client {client}  ref {ref}  scale {vp.scale:.4f}")

    probes: list[Probe] = [parse_probe(s) for s in args.probe]
    points: list[tuple[str, Point]] = [(s, parse_point(s)) for s in args.point]
    if not probes and not points:
        for name in dir(atlas):
            v = getattr(atlas, name)
            if isinstance(v, Probe):
                probes.append(v if v.name else replace(v, name=name))
            elif isinstance(v, Point):
                points.append((name, v))

    for name, pt in points:
        sx, sy = vp.to_screen(pt.x, pt.y)
        ix, iy = sx - origin.x, sy - origin.y
        if 0 <= ix < img.shape[1] and 0 <= iy < img.shape[0]:
            print(
                f"point {name:<16} logical ({pt.x},{pt.y}) -> screen ({sx},{sy}) colour 0x{pixel_at(img, ix, iy):06X}"
            )
        else:
            print(f"point {name:<16} logical ({pt.x},{pt.y}) -> screen ({sx},{sy}) OUTSIDE capture")

    for p in probes:
        rect = vp.probe_rect_screen(p, grow=args.grow)
        hit = pixel_search_in(img, origin, rect, p.color, p.variation + vp.variation_boost())
        status = f"HIT at screen {hit} logical {vp.to_logical(*hit)}" if hit else "miss"
        print(f"probe {p.name:<16} 0x{p.color:06X}±{p.variation} rect {rect} -> {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
