"""Shop tab row: the selected tab is invisible to the blob search, so it is put back before
any tab is clicked by index (clicking `shop_tabs()[0]` opened the paid Gems tab, 2026-09-09).
"""

import pytest

from firestone_bot.features import shop
from firestone_bot.vision import blobs

PITCH = 138
FIRST = 557
COUNT = 7
ROW = [FIRST + i * PITCH for i in range(COUNT)]


class FakeGame:
    def __init__(self, selected):
        self.selected = selected
        self.taps = []
        self.statuses = []

    def status(self, s):
        self.statuses.append(s)

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append(p.x)
        self.selected = ROW.index(p.x)

    def wait_still(self, max_ms=1500):
        return True

    def save_diagnostic(self, name):
        pass


@pytest.fixture(autouse=True)
def fake_blobs(monkeypatch):
    def find_blobs(g, rect, color, variation, **kw):
        return [
            blobs.Blob(x - 60, 90, x + 60, 150, 7000) for i, x in enumerate(ROW) if i != g.selected
        ]

    monkeypatch.setattr(shop.blobs, "find_blobs", find_blobs)


@pytest.mark.parametrize("selected", range(COUNT))
def test_the_whole_tab_row_is_rebuilt_whichever_tab_is_selected(selected):
    got = [p.x for p in shop.tab_slots(FakeGame(selected))]
    assert got == pytest.approx(ROW, abs=2)


def test_the_first_slot_is_the_first_tab_even_when_it_is_selected():
    g = FakeGame(selected=0)
    assert shop._select_slot(g, shop.tab_slots(g), 0) is True
    assert g.taps == []  # already there: no click, and none on the paid tab next to it


def test_selecting_the_first_tab_from_another_one_clicks_the_first_tab():
    g = FakeGame(selected=1)
    assert shop._select_slot(g, shop.tab_slots(g), 0) is True
    assert g.taps == [FIRST]


def test_the_check_in_tab_is_the_last_one():
    g = FakeGame(selected=0)
    assert shop._select_slot(g, shop.tab_slots(g), -1) is True
    assert g.taps == [ROW[-1]]
