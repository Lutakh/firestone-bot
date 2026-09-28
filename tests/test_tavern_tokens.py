"""Tavern plays: a play counts only when the tavern token counter drops, and no play is made
with the counter at 0.

The fake tavern: a green Play button (green even with no token left, where the game offers
to buy some: the case that counted plays never made), a token counter that shows each play
at once or `lag_ms` later, and each Play taken or ignored as scripted. Time only moves with
the bot's sleeps.
"""

import numpy as np
import pytest

from firestone_bot.features import claim_beer, token_counter
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas

RESET = "20260928100000"


class FakeTavern:
    def __init__(self, tmp_path, tokens, taken=(), max_tokens=12, count=0, readable=True, lag_ms=0):
        self.settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        self.settings.set("Token", 1)
        self.settings.set("MaxTokens", max_tokens)
        self.settings.set("TokenCountDaily", count)
        self.settings.set("LastTokenReset", RESET)
        self.tokens = tokens
        self.shown = tokens  # what the counter shows
        self.show_at = 0.0  # when it shows the last play
        self.taken = list(taken)  # per Play: tokens spent (0 = the game ignored the click)
        self.readable = readable
        self.steady = None  # the counter reads this whatever the game holds (a misplaced rect)
        self.lag_ms = lag_ms
        self.now = 0.0
        self.pointer = None
        self.vars = {}
        self.taps = 0
        self.shop_opens = 0  # Play clicked with no token left
        self.images = 0
        self.lines = []
        self.captures = []
        self.region_changes = []

    # the game
    def read(self, rect):
        assert rect is atlas.TAVERN_TOKEN_DIGITS
        assert self.pointer is atlas.SPEND_PARK, "the counter is read under the pointer"
        if self.now >= self.show_at:
            self.shown = self.tokens
        if not self.readable:
            return None
        return self.steady if self.steady is not None else self.shown

    def found(self, probe):
        assert probe is atlas.TAVERN_USE_TOKEN_READY
        return True

    def tap(self, point, settle_ms=1500, expect=None):
        self.pointer = point
        if point in atlas.TAVERN_CARDS or point is atlas.TAVERN_DISMISS:
            return
        assert point is atlas.TAVERN_USE_TOKEN, point
        self.taps += 1
        if getattr(self, "dry_run", False):
            return  # no input reaches the game: nothing is taken
        if self.tokens == 0:
            self.shop_opens += 1
            return
        spent = self.taken.pop(0) if self.taken else 1
        self.tokens -= spent
        self.show_at = self.now + self.lag_ms

    # Game API
    def move_to(self, point):
        self.pointer = point

    def sleep(self, ms):
        self.now += ms

    def region_image(self, rect, anchor=None):
        self.images += 1
        return np.full((32, 112, 3), self.tokens % 256, dtype=np.uint8)  # the digits drawn

    def wait_region_change(self, rect, before, timeout_ms=15000, anchor=None):
        self.region_changes.append((rect, anchor))
        return not np.array_equal(self.region_image(rect, anchor), before)

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)


@pytest.fixture
def tavern(monkeypatch, tmp_path):
    def make(**kw):
        g = FakeTavern(tmp_path, **kw)
        monkeypatch.setattr(token_counter, "read", lambda game, rect: game.read(rect))
        monkeypatch.setattr(claim_beer.multiplier, "ensure_single", lambda game, screen: True)
        monkeypatch.setattr(claim_beer.multiplier, "read_multiplier", lambda game: 1)
        return g

    return make


def _today(g):
    return int(g.settings.get("TokenCountDaily"))


def test_tavern_counts_only_plays_that_took_a_token(tavern):
    g = tavern(tokens=10, taken=[1, 0, 1], max_tokens=12, count=10)
    assert claim_beer.play_tokens(g) == 2
    assert g.taps == 3
    assert _today(g) == 12
    assert g.tokens == 8
    assert sum("did not go down, not counted" in s for s in g.lines) == 1
    assert "Tavern: play 1 (11 today, 9 tokens left)" in g.lines
    assert g.images == 0  # the pixel fallback is only captured for an unreadable counter


def test_tavern_stops_before_the_limit_when_the_tokens_run_out(tavern):
    """Play stays green with no token left: each click there counted a play, so the 12 plays
    of the day (Decorated Heroes challenge) were reached with fewer real ones."""
    g = tavern(tokens=5, max_tokens=12, count=0)
    assert claim_beer.play_tokens(g) == 5
    assert _today(g) == 5
    assert g.taps == 5
    assert g.shop_opens == 0
    assert "Tavern: no tavern token left, leaving" in g.lines


def test_tavern_counter_at_zero_never_presses_play(tavern):
    g = tavern(tokens=0, max_tokens=12, count=3)
    assert claim_beer.play_tokens(g) == 0
    assert g.taps == 0
    assert _today(g) == 3
    assert "Tavern: no tavern token left, leaving" in g.lines


def test_tavern_leaves_after_repeated_ignored_plays(tavern):
    g = tavern(tokens=10, taken=[0, 0, 0], max_tokens=12, count=4)
    assert claim_beer.play_tokens(g) == 0
    assert g.taps == claim_beer.TAVERN_RETRIES + 1
    assert _today(g) == 4
    assert g.captures == ["tavern-play-not-taken.png"]
    assert any("did not go down again, leaving" in s for s in g.lines)


def test_tavern_play_shown_late_is_confirmed_not_played_again(tavern):
    g = tavern(tokens=10, max_tokens=12, count=10, lag_ms=claim_beer.TAVERN_TAKEN_MS + 1500)
    assert claim_beer.play_tokens(g) == 2
    assert g.taps == 2  # each late play confirmed before the next, never a second click
    assert _today(g) == 12
    assert g.tokens == 8
    assert sum("confirmed late" in s for s in g.lines) == 2
    assert g.vars.get(claim_beer._unconfirmed_key(g), 0) == 0


def test_tavern_multi_spend_stops_and_blocks_until_x1(tavern, monkeypatch):
    g = tavern(tokens=20, taken=[5], max_tokens=12, count=0)
    assert claim_beer.play_tokens(g) == 5
    assert g.taps == 1 and _today(g) == 5
    assert any("the spend multiplier is not x1" in s for s in g.lines)
    assert g.captures == ["tavern-multiplier.png"]
    monkeypatch.setattr(claim_beer.multiplier, "read_multiplier", lambda game: None)
    claim_beer.play_tokens(g)  # the label is still unreadable: no play at x5 again
    assert g.taps == 1
    monkeypatch.setattr(claim_beer.multiplier, "read_multiplier", lambda game: 1)
    claim_beer.play_tokens(g)  # the label reads x1 now
    assert g.taps == 8 and _today(g) == 12


def test_tavern_counter_unreadable_falls_back_to_the_digits_pixels(tavern):
    g = tavern(tokens=10, max_tokens=12, count=10, readable=False)
    assert claim_beer.play_tokens(g) == 2
    assert _today(g) == 12
    assert g.region_changes == [(atlas.TAVERN_TOKEN_DIGITS, atlas.ANCHOR_TOP_RIGHT)] * 2
    assert g.captures == ["tavern-counter-unread.png"]  # once per visit


def test_tavern_unconfirmed_plays_are_capped_per_game_day(tavern):
    """A rect reading a steady wrong number: every real play looks ignored. Each visit
    leaves after a few, and the day stops at MAX_UNCONFIRMED uncounted plays."""
    g = tavern(tokens=40, max_tokens=0, count=0)
    g.steady = 93
    claim_beer.play_tokens(g)
    assert g.taps == claim_beer.TAVERN_RETRIES + 1
    claim_beer.play_tokens(g)
    assert g.taps == claim_beer.MAX_UNCONFIRMED
    assert g.captures == ["tavern-play-not-taken.png"] * 2
    claim_beer.play_tokens(g)  # the rest of the game day: no more plays
    assert g.taps == claim_beer.MAX_UNCONFIRMED
    assert "no more plays until the next game day" in g.lines[-1]
    assert _today(g) == 0 and g.tokens == 40 - claim_beer.MAX_UNCONFIRMED
    g.settings.set("LastTokenReset", "20260929100000")  # a new game day
    claim_beer.play_tokens(g)
    assert g.taps == claim_beer.MAX_UNCONFIRMED + claim_beer.TAVERN_RETRIES + 1


def test_tavern_dry_run_leaves_nothing_for_the_live_run(tavern):
    """A dry run's Play sends no input, so the counter never drops. Counted as ignored, two
    dry-run cycles reached MAX_UNCONFIRMED and the live run started next on the same Game
    made no tavern play until the next game day (review 2026-09-28). The fakes of the other
    tests have no dry_run attribute: the bot reads it with a default."""
    g = tavern(tokens=10, max_tokens=12, count=10)
    g.dry_run = True
    for visit in range(1, claim_beer.MAX_UNCONFIRMED + 1):
        start = g.now
        assert claim_beer.play_tokens(g) == 0
        assert g.taps == visit  # one Play shown per visit, no retry
        assert g.now - start < claim_beer.TAVERN_TAKEN_MS  # no wait for a drop that cannot come
    assert not any(key.startswith("tavern_unconfirmed:") for key in g.vars)
    assert g.captures == [] and _today(g) == 10 and g.tokens == 10
    assert g.lines[-1] == "Tavern: dry run, the play is not checked on the token counter, leaving"
    g.dry_run = False  # Start after the dry run: the same Game, its vars kept
    assert claim_beer.play_tokens(g) == 2
    assert g.taps == claim_beer.MAX_UNCONFIRMED + 2
    assert _today(g) == 12 and g.tokens == 8
