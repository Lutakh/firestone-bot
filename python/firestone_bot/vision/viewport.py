"""Logical (atlas) <-> screen coordinate mapping.

Measured in plan step 4.2 (docs/MEASUREMENTS.md): the game uses a Unity canvas with a
1920x1080 reference, `scale = min(client_w / 1920, client_h / 1080)`, and widgets anchored to
the screen edges. There is NO letterbox: at a non-16:9 client the extra space goes between the
anchored groups.

Atlas numbers are AHK screen coordinates taken on the reference client `REF` (1920x1009, i.e.
canvas scale 1009/1080). Mapping a logical point to the live client therefore needs an anchor:

    canvas_dx = (x - REF.x - ax * REF.w) / s0        s0 = REF canvas scale
    screen_x  = client.x + ax * client.w + canvas_dx * s

with `ax` in {0, 0.5, 1} (left / centre / right) and likewise for y (top / centre / bottom).
When the live client has the same aspect as REF, every anchor gives the same answer, so a
wrong anchor guess only matters at other aspects (fullscreen 16:9, 1280x720 windows).
"""

from __future__ import annotations

from dataclasses import dataclass

from firestone_bot.platform.window import Rect
from firestone_bot.vision.atlas import REF, Anchor, Probe, default_anchor

CANVAS_W = 1920
CANVAS_H = 1080


def canvas_scale(w: int, h: int) -> float:
    return min(w / CANVAS_W, h / CANVAS_H)


@dataclass(frozen=True)
class Viewport:
    client: Rect  # live client rect, physical screen pixels
    ref: Rect = REF

    @property
    def scale(self) -> float:
        """Canvas scale of the live client."""
        return canvas_scale(self.client.w, self.client.h)

    @property
    def ref_scale(self) -> float:
        return canvas_scale(self.ref.w, self.ref.h)

    @property
    def rel_scale(self) -> float:
        """Live scale relative to the reference (1.0 on the original setup)."""
        return self.scale / self.ref_scale

    def variation_boost(self) -> int:
        """Extra colour tolerance when the game is not at reference scale (sprites drift)."""
        return 0 if abs(self.rel_scale - 1.0) < 1e-6 else 2

    def _anchor(self, x: float, y: float, anchor: Anchor | None) -> Anchor:
        if anchor is not None:
            return anchor
        return default_anchor((x - self.ref.x) / self.ref.w, (y - self.ref.y) / self.ref.h)

    def to_screen_f(self, x: float, y: float, anchor: Anchor | None = None) -> tuple[float, float]:
        ax, ay = self._anchor(x, y, anchor)
        s0, s = self.ref_scale, self.scale
        dx = (x - self.ref.x - ax * self.ref.w) / s0
        dy = (y - self.ref.y - ay * self.ref.h) / s0
        return (
            self.client.x + ax * self.client.w + dx * s,
            self.client.y + ay * self.client.h + dy * s,
        )

    def to_screen(self, x: float, y: float, anchor: Anchor | None = None) -> tuple[int, int]:
        sx, sy = self.to_screen_f(x, y, anchor)
        return round(sx), round(sy)

    def to_logical(self, sx: float, sy: float, anchor: Anchor | None = None) -> tuple[int, int]:
        if anchor is None:
            anchor = default_anchor(
                (sx - self.client.x) / self.client.w, (sy - self.client.y) / self.client.h
            )
        ax, ay = anchor
        s0, s = self.ref_scale, self.scale
        dx = (sx - self.client.x - ax * self.client.w) / s
        dy = (sy - self.client.y - ay * self.client.h) / s
        return round(self.ref.x + ax * self.ref.w + dx * s0), round(
            self.ref.y + ay * self.ref.h + dy * s0
        )

    def to_client(self, x: float, y: float, anchor: Anchor | None = None) -> tuple[int, int]:
        """Logical -> pixel position inside a capture of the client rect."""
        sx, sy = self.to_screen(x, y, anchor)
        return sx - self.client.x, sy - self.client.y

    def probe_rect_screen(self, p: Probe, grow: int = 1) -> Rect:
        """Map a probe rectangle to screen pixels, normalised and grown by `grow` logical px.

        AHK corners are inclusive, so the width is x2 - x1 + 1 logical pixels. The whole rect
        uses one anchor (the probe's, or the default for its centre).
        """
        p = p.normalized()
        anchor = self._anchor((p.x1 + p.x2) / 2, (p.y1 + p.y2) / 2, p.anchor)
        x1, y1 = self.to_screen_f(p.x1 - grow, p.y1 - grow, anchor)
        x2, y2 = self.to_screen_f(p.x2 + grow + 1, p.y2 + grow + 1, anchor)
        x1i, y1i = int(x1), int(y1)
        x2i, y2i = -int(-x2), -int(-y2)  # ceil
        return Rect(x1i, y1i, max(1, x2i - x1i), max(1, y2i - y1i))
