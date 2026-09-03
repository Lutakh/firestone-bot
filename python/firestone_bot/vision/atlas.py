"""The logical 1920x1080 canvas.

Every coordinate, rectangle and colour from the AHK code is kept verbatim here, expressed in the
ORIGINAL screen coordinate system (1920x1080 monitor, 100 % DPI, game maximized, Windows 10
taskbar at the bottom). `REF` is the game client area in that system; the viewport maps it to
the live client rect at runtime.

Feature modules add their own tables to this module as they are ported (plan 4.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from firestone_bot.platform.window import Rect

# Reference frame: client area of the game on the original setup.
# Measured 2026-09-03 on Windows 11 as (0, 23, 1920, 1009); the AHK numbers assume a Windows 10
# machine with a 40 px taskbar, i.e. client top at y=31 (see docs/MEASUREMENTS.md, 4.1).
REF = Rect(0, 31, 1920, 1009)


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Probe:
    """A PixelSearch: rect corners (inclusive, as AHK), colour 0xRRGGBB, per-channel variation."""

    x1: int
    y1: int
    x2: int
    y2: int
    color: int
    variation: int = 3
    name: str = ""

    def normalized(self) -> Probe:
        return Probe(
            min(self.x1, self.x2),
            min(self.y1, self.y2),
            max(self.x1, self.x2),
            max(self.y1, self.y2),
            self.color,
            self.variation,
            self.name,
        )


# Common colours (AHK 0xRRGGBB literals).
GREEN_BUTTON = 0x0AA008  # affordable / claim button
GREEN_BUTTON_2 = 0x16BC15
RED_DOT = 0xF40000  # notification dot
IDLE_TROOP = 0x542710  # brown idle-troop marker on the map
ORANGE_1 = 0xF9AA47
ORANGE_2 = 0xFCAC47

# --- Points and probes used by the 4.1 cross-check ---------------------------------------
BIG_CLOSE = Point(1851, 84)  # Functions/subFunctions/BigClose.ahk:5
MAIL_ICON = Point(56, 777)  # Functions/CheckMail.ahk:8
MAIL_CLAIM_ALL = Probe(1260, 780, 1334, 835, GREEN_BUTTON, 3, "mail_claim_all")  # CheckMail.ahk:13
MAP_TROOP_IDLE = Probe(1175, 996, 1187, 1012, IDLE_TROOP, 10, "map_troop_idle")  # MapStart.ahk:179
