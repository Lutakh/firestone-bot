"""Coordinates mode: the mission points follow the map's scale (map_align.SCALE_KEY), which
the landmark measures at every alignment."""

from __future__ import annotations

from firestone_bot.features import map_align, map_start
from firestone_bot.platform.window import Rect
from firestone_bot.vision import atlas
from firestone_bot.vision.viewport import Viewport


class G:
    def __init__(self, scale=None):
        self.vars = {} if scale is None else {map_align.SCALE_KEY: scale}
        self.clicks = []
        self.drags = []

    def click_at(self, x, y, anchor=None):
        self.clicks.append((x, y, anchor))

    def drag(self, x1, y1, x2, y2, anchor=None):
        self.drags.append(y2 - y1)

    def sleep(self, ms):
        pass


def test_points_are_clicked_as_measured_on_a_canvas_scaled_map():
    g = G()
    map_start._click_mission(g, 1608, 119)
    assert g.clicks == [(1608, 119, atlas.ANCHOR_CENTER)]
    g = G(1.0)
    map_start._click_mission(g, 384, 1009)
    assert g.clicks == [(384, 1009, atlas.ANCHOR_CENTER)]


def test_points_move_towards_the_centre_on_a_fitted_map():
    """Report ANHNX9's map (1920x1080, the game started fullscreen): the north-east mission
    at (1608, 119) showed its icon at client (1602, 120); it was clicked at (1654, 94)."""
    g = G(map_align.FITTED_SCALE)
    map_start._click_mission(g, 1608, 119)
    ((x, y, anchor),) = g.clicks
    sx, sy = Viewport(Rect(0, 0, 1920, 1080)).to_screen(x, y, anchor)
    assert abs(sx - 1602) <= 8 and abs(sy - 120) <= 8
    # a north-edge point is still revealed by the drag, then clicked moved by it
    g = G(map_align.FITTED_SCALE)
    map_start._click_mission(g, 1300, 26)
    assert g.drags == [atlas.MAP_NORTH_DRAG_DY]
    scaled = round(535.5 + (26 - 535.5) * map_align.FITTED_SCALE)
    assert g.clicks[0][1] == scaled + atlas.MAP_NORTH_DRAG_DY
