"""Quests: every claimable quest claimed in one visit, the page re-checked before each click
(one claim per cycle at a fixed point, and a bell rect that missed the bell, 2026-09-10)."""

import pytest

from firestone_bot.features import quests
from firestone_bot.vision import atlas, blobs

ROW_Y = (307, 484, 662, 843)


class FakeQuestPage:
    def __init__(self, daily, weekly, page_closes_after=None):
        self.claimable = {"daily": daily, "weekly": weekly}
        self.tab = "daily"
        self.taps = []
        self.statuses = []
        self.page_open = True
        self.page_closes_after = page_closes_after
        self.ms = type("MS", (), {"character_close_x": object()})()

    def tap(self, p, settle_ms=1500, expect=None):
        if p is atlas.QUESTS_DAILY_TAB:
            self.tab = "daily"
            return
        if p is atlas.QUESTS_WEEKLY_TAB:
            self.tab = "weekly"
            return
        assert abs(p.x - 1438) < 5 and abs(p.y - ROW_Y[0]) < 5, "not the top Claim button"
        self.taps.append(self.tab)
        self.claimable[self.tab] -= 1  # the list re-sorts: the next claimable one moves up
        if self.page_closes_after is not None and len(self.taps) >= self.page_closes_after:
            self.page_open = False

    def found(self, probe):
        return self.page_open

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
    def find_blobs(g, rect, color=None, variation=0, **kw):
        n = min(g.claimable[g.tab], len(ROW_Y))
        return [blobs.Blob(1320, y - 30, 1556, y + 30, 12000) for y in ROW_Y[:n]]

    monkeypatch.setattr(quests.blobs, "find_blobs", find_blobs)


def test_every_daily_and_weekly_reward_is_claimed_in_one_visit():
    g = FakeQuestPage(daily=6, weekly=2)
    quests._claim_tab(g, "daily", atlas.QUESTS_DAILY_TAB)
    quests._claim_tab(g, "weekly", atlas.QUESTS_WEEKLY_TAB)
    assert g.taps == ["daily"] * 6 + ["weekly"] * 2
    assert g.claimable == {"daily": 0, "weekly": 0}


def test_nothing_claimable_means_no_click():
    g = FakeQuestPage(daily=0, weekly=0)
    assert quests._claim_tab(g, "daily", atlas.QUESTS_DAILY_TAB) == 0
    assert g.taps == []


def test_claims_stop_when_the_page_is_gone():
    g = FakeQuestPage(daily=5, weekly=0, page_closes_after=2)
    assert quests._claim_tab(g, "daily", atlas.QUESTS_DAILY_TAB) == 2
    assert any("page is gone" in s for s in g.statuses)


def test_claims_are_capped():
    g = FakeQuestPage(daily=quests.MAX_CLAIMS_PER_TAB + 10, weekly=0)
    assert quests._claim_tab(g, "daily", atlas.QUESTS_DAILY_TAB) == quests.MAX_CLAIMS_PER_TAB
