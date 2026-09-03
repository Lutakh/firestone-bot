"""Logical (atlas) <-> screen coordinate mapping. See plan section 3.1."""

from __future__ import annotations

from dataclasses import dataclass

from firestone_bot.platform.window import Rect
from firestone_bot.vision.atlas import REF, Probe


@dataclass(frozen=True)
class Viewport:
    client: Rect  # live client rect, physical screen pixels
    ref: Rect = REF

    @property
    def scale(self) -> float:
        return min(self.client.w / self.ref.w, self.client.h / self.ref.h)

    @property
    def offset(self) -> tuple[float, float]:
        """Letterbox offset of the 16:9 content inside the client area."""
        s = self.scale
        return (self.client.w - self.ref.w * s) / 2, (self.client.h - self.ref.h * s) / 2

    def variation_boost(self) -> int:
        """Extra colour tolerance when the game is not at reference scale (sprites drift)."""
        return 0 if abs(self.scale - 1.0) < 1e-6 else 2

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        s = self.scale
        ox, oy = self.offset
        sx = self.client.x + ox + (x - self.ref.x) * s
        sy = self.client.y + oy + (y - self.ref.y) * s
        return round(sx), round(sy)

    def to_logical(self, sx: float, sy: float) -> tuple[int, int]:
        s = self.scale
        ox, oy = self.offset
        x = (sx - self.client.x - ox) / s + self.ref.x
        y = (sy - self.client.y - oy) / s + self.ref.y
        return round(x), round(y)

    def to_client(self, x: float, y: float) -> tuple[int, int]:
        """Logical -> pixel position inside a capture of the client rect."""
        sx, sy = self.to_screen(x, y)
        return sx - self.client.x, sy - self.client.y

    def probe_rect_screen(self, p: Probe, grow: int = 1) -> Rect:
        """Map a probe rectangle to screen pixels, normalised and grown by `grow` logical px.

        AHK corners are inclusive, so the width is x2 - x1 + 1 in logical pixels.
        """
        p = p.normalized()
        x1, y1 = self.to_screen(p.x1 - grow, p.y1 - grow)
        x2, y2 = self.to_screen(p.x2 + grow + 1, p.y2 + grow + 1)
        return Rect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))
