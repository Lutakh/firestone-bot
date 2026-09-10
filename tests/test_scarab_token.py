"""Scarab's token: the free daily token is claimed only through a green button inside the
free card, next to a paid pass (2026-09-10)."""

import pytest

from firestone_bot.features import scarab_token as st
from firestone_bot.vision import blobs


class FakeMarket:
    def __init__(self, free=True, sticks=False):
        self.free = free
        self.sticks = sticks  # the click does not claim
        self.taps = []
        self.statuses = []

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append((p.x, p.y))
        if not self.sticks:
            self.free = False

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
        return [blobs.Blob(559, 736, 808, 795, 14000)] if g.free else []

    monkeypatch.setattr(st.blobs, "find_blobs", find_blobs)


def test_the_free_token_is_claimed_on_its_button():
    g = FakeMarket(free=True)
    assert st.claim_free_token(g) is True
    assert g.taps == [(683, 765)]


def test_no_free_button_means_no_click():
    g = FakeMarket(free=False)
    assert st.claim_free_token(g) is False
    assert g.taps == []


def test_a_click_that_did_not_claim_is_reported():
    g = FakeMarket(free=True, sticks=True)
    assert st.claim_free_token(g) is False
    assert g.taps == [(683, 765)]  # one click only, no retry loop
    assert any("still there" in s for s in g.statuses)
