"""Regenerate assets/icon.ico and assets/icon.icns from assets/icon-256.png.

    python -m firestone_bot.tools.make_icons

The PNG is the bot icon chosen by the owner (distinct from the game icon).
Epic install), so the bot shows the same icon as the game on Windows and macOS. Needs Pillow
(`pip install pillow`, not a runtime dependency). The .icns is written by hand with PNG
entries (icp4 .. ic09), which every macOS since 10.7 reads; no iconutil needed.
"""

from __future__ import annotations

import io
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "assets")
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICNS_TYPES = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"icp6", 64),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
)


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is needed: pip install pillow")
        return 1
    src = Image.open(os.path.join(ASSETS, "icon-256.png")).convert("RGBA")
    src.save(os.path.join(ASSETS, "icon.ico"), sizes=[(s, s) for s in ICO_SIZES])
    body = b""
    for typ, size in ICNS_TYPES:
        buf = io.BytesIO()
        src.resize((size, size), Image.LANCZOS).save(buf, "PNG")
        data = buf.getvalue()
        body += typ + struct.pack(">I", 8 + len(data)) + data
    with open(os.path.join(ASSETS, "icon.icns"), "wb") as f:
        f.write(b"icns" + struct.pack(">I", 8 + len(body)) + body)
    print("assets/icon.ico and assets/icon.icns written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
