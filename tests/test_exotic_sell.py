"""Exotic merchant sell page: buttons found by colour and named from the end of the list
the view is scrolled to (the fixed AHK points missed every button at 3024x1675, 2026-09-10)."""

import numpy as np
import pytest

from firestone_bot.features import exotic_merchant as em
from firestone_bot.vision import atlas, blobs

COLS = (955, 1278, 1600)
PITCH = 318
TOP_VIEW = (0, 1)  # rows fully shown with the list at the top
BOTTOM_VIEW = (2, 3, 4)


class FakeMerchant:
    def __init__(self, stock, bottom_view=BOTTOM_VIEW):
        self.stock = dict(stock)
        self.view = "middle"
        self.bottom_view = bottom_view
        self.taps = []
        self.statuses = []

    def rows(self):
        return TOP_VIEW if self.view == "top" else self.bottom_view if self.view == "bottom" else ()

    def buttons(self):
        for k, r in enumerate(self.rows()):
            for c, name in enumerate(atlas.EXOTIC_GRID[r]):
                yield name, COLS[c], 600 + k * PITCH

    # Game API used by the feature
    def wheel(self, n):
        self.view = "top" if n > 0 else "bottom"

    def region_image(self, rect):
        return np.full((4, 4, 3), {"top": 10, "bottom": 20}.get(self.view, 0), np.uint8)

    def tap(self, p, settle_ms=1500, expect=None):
        for name, x, y in self.buttons():
            if abs(p.x - x) < 5 and abs(p.y - y) < 5:
                self.taps.append(name)
                self.stock[name] -= 1
                return
        raise AssertionError(f"click on no button at {(p.x, p.y)}")

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def wait_still(self, max_ms=1500):
        return True

    def status(self, s):
        self.statuses.append(s)

    def save_diagnostic(self, name):
        pass


@pytest.fixture(autouse=True)
def fake_blobs(monkeypatch):
    def find_blobs(g, rect, color=None, variation=0, *, mask_fn=None, **kw):
        out = []
        for name, x, y in g.buttons():
            if mask_fn is not None or g.stock.get(name, 0) > 0:
                out.append(blobs.Blob(x - 130, y - 51, x + 130, y + 52, 20000))
        return out

    monkeypatch.setattr(em.blobs, "find_blobs", find_blobs)


def test_scrolls_only_sells_every_scroll_and_nothing_else():
    g = FakeMerchant({"scroll_speed": 2, "scroll_health": 1, "midas": 3, "drums": 4})
    em.sell(g, set(atlas.EXOTIC_SCROLLS))
    assert sorted(g.taps) == ["scroll_health", "scroll_speed", "scroll_speed"]
    assert g.stock["midas"] == 3 and g.stock["drums"] == 4


def test_no_gold_never_sells_gold():
    stock = {n: 2 for row in atlas.EXOTIC_GRID for n in row}
    g = FakeMerchant(stock)
    em.sell(g, set(atlas.EXOTIC_SCROLLS | atlas.EXOTIC_ITEMS))
    assert not set(g.taps) & atlas.EXOTIC_GOLD
    assert all(g.stock[n] == 0 for n in atlas.EXOTIC_ITEMS | atlas.EXOTIC_SCROLLS)


def test_sell_all_empties_the_whole_list():
    stock = {n: 1 for row in atlas.EXOTIC_GRID for n in row}
    g = FakeMerchant(stock)
    em.sell(g, set(atlas.EXOTIC_SCROLLS | atlas.EXOTIC_GOLD | atlas.EXOTIC_ITEMS))
    assert all(v == 0 for v in g.stock.values())


def test_a_bottom_view_that_is_not_the_list_end_is_not_clicked():
    # the last row seen has three buttons: the list did not reach its single-button end row
    g = FakeMerchant({"drums": 3, "totem_annihilation": 3}, bottom_view=(1, 2, 3))
    em.sell(g, set(atlas.EXOTIC_ITEMS))
    assert g.taps == []
    assert any("does not look as expected" in s for s in g.statuses)


def test_per_item_cap():
    g = FakeMerchant({"scroll_speed": em.MAX_SELLS_PER_ITEM + 5})
    em.sell(g, set(atlas.EXOTIC_SCROLLS))
    assert g.taps.count("scroll_speed") == em.MAX_SELLS_PER_ITEM
