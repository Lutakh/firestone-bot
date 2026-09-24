"""Research tree (game 9.1.1): panel states from the bottom strip, claims, node attempts.

The fake keeps the panels packed to the left like the game: a claimed panel disappears and
the others move left; a started research goes first ("newest") or after the busy ones
("append"). Both orders are tested: the bot must not depend on which one the game uses.
"""

import pytest

from firestone_bot.features import research
from firestone_bot.vision import atlas, blobs

NODE_TAP = (1400, 350)


class FakeGame:
    def __init__(self, panels, order="newest", popup_research=True, nodes=True, claim_lag=0):
        self.panels = list(panels)  # "green" / "orange" / None, left to right
        self.claim_lag = claim_lag  # strip reads before a claim shows
        self.pending_claim = None
        self.reads = 0
        self.order = order
        self.popup_research = popup_research
        self.nodes = [blobs.Blob(1200, 300, 1600, 400, 1)] if nodes else []
        self.taps = []
        self.statuses = []
        self.wheels = []
        self.style = "classic"
        self._popup_open = False

    # the game's reactions
    def _claim(self, i):
        del self.panels[i]
        self.panels.append(None)

    def _start(self):
        if None not in self.panels:
            return  # a full queue takes nothing
        if self.order == "newest":
            self.panels.insert(0, "orange")
            self.panels.remove(None)
        else:
            self.panels[self.panels.index(None)] = "orange"

    # Game API used by the feature
    def focus(self):
        pass

    def status(self, s):
        self.statuses.append(s)

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append((p.x, p.y))
        if p.anchor == research.SLOT_ANCHOR:
            i = 0 if p.x < atlas.RS_SLOT_SPLIT else 1
            assert self.panels[i] == "green", f"a click on a {self.panels[i]} panel"
            if self.claim_lag:
                self.pending_claim, self.reads = i, 0
            else:
                self._claim(i)
        elif (p.x, p.y) == NODE_TAP:
            self._popup_open = True
        elif p is atlas.RS_POPUP_RESEARCH_BUTTON:
            self._popup_open = False
            self._start()
        elif p is atlas.RS_POPUP_CLOSE:
            self._popup_open = False

    def wait_still(self, max_ms=1500):
        return True

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def wheel(self, n):
        self.wheels.append(n)

    def found(self, probe):
        if probe is atlas.RS_POPUP_RESEARCH:
            return self.popup_research and self._popup_open
        if probe is atlas.RS_POPUP_CLOSE_X:
            return self._popup_open
        return False

    def require_screen(self, p, expect, settle_ms=1500, via_town=False):
        pass

    def save_diagnostic(self, name):
        self.statuses.append(f"diag:{name}")


@pytest.fixture
def fake(monkeypatch):
    def make(*args, **kw):
        g = FakeGame(*args, **kw)

        def find(game, rect, color=None, variation=0, **kw):
            if rect == atlas.RS_SLOT_STRIP:
                if g.pending_claim is not None and color in atlas.RS_SLOT_DONE:
                    g.reads += 1
                    if g.reads > g.claim_lag:
                        g._claim(g.pending_claim)
                        g.pending_claim = None
                want = "green" if color in atlas.RS_SLOT_DONE else "orange"
                return [
                    blobs.Blob(cx - 80, 920, cx + 80, 980, 1)
                    for cx, state in zip((645, 1290), g.panels)
                    if state == want
                ]
            return list(g.nodes)

        monkeypatch.setattr(blobs, "find_blobs", find)
        monkeypatch.setattr(research, "big_close", lambda game: game.statuses.append("big_close"))
        return g

    return make


def _claims(g):
    return sum(s.endswith("finished, claiming it") for s in g.statuses)


def _research_clicks(g):
    return g.taps.count((atlas.RS_POPUP_RESEARCH_BUTTON.x, atlas.RS_POPUP_RESEARCH_BUTTON.y))


def test_slot_states(fake):
    g = fake(["orange", None])
    assert research.slot_state(g, 0) == "running"
    assert research.slot_state(g, 1) == "empty"
    g.panels[1] = "green"
    assert research.slot_state(g, 1) == "done"


@pytest.mark.parametrize("order", ["newest", "append"])
def test_both_finished_are_claimed_then_both_slots_started(fake, order):
    """Both researches finished between two visits: the old loop claimed one, left the
    other for a cycle and reported a started research as 'did not start'."""
    g = fake(["green", "green"], order=order)
    research.go_research(g)
    assert _claims(g) == 2
    assert _research_clicks(g) == 2
    assert g.panels == ["orange", "orange"]
    assert not any("did not" in s or "left alone" in s for s in g.statuses)
    assert g.statuses[-3:] == [
        "Research: slot 1 in progress",
        "Research: slot 2 in progress",
        "big_close",
    ]


@pytest.mark.parametrize("order", ["newest", "append"])
def test_one_finished_one_running(fake, order):
    g = fake(["orange", "green"], order=order)
    research.go_research(g)
    assert _claims(g) == 1
    assert _research_clicks(g) == 1
    assert g.panels == ["orange", "orange"]


@pytest.mark.parametrize("order", ["newest", "append"])
def test_a_start_shown_in_the_first_panel_counts_as_started(fake, order):
    g = fake(["orange", None], order=order)
    assert research.start_research(g, 1)
    assert _research_clicks(g) == 1
    assert g.wheels == [-35, 35]  # page 2 first, back to page 1 after the start


def test_full_queue_opens_no_node(fake):
    g = fake(["orange", "orange"])
    research.go_research(g)
    assert g.wheels == []
    assert NODE_TAP not in g.taps


def test_popups_without_a_research_button_are_closed(fake):
    g = fake([None, None], popup_research=False)
    research.go_research(g)
    # each page: node tapped, then the popup X; then the visit ends (no node to start)
    close = (atlas.RS_POPUP_CLOSE.x, atlas.RS_POPUP_CLOSE.y)
    tab = (atlas.RS_FIRESTONE_TREE.x, atlas.RS_FIRESTONE_TREE.y)
    assert g.taps == [tab, NODE_TAP, close, NODE_TAP, close]
    assert any(s.startswith("diag:research-no-node") for s in g.statuses)


def test_slot_button_is_the_rightmost_blob_of_its_half(monkeypatch):
    """The "Completed" progress bar is green too and sits left of the Claim button."""
    g = FakeGame([None, None])

    def find(game, rect, color=None, variation=0, **kw):
        if rect == atlas.RS_SLOT_STRIP and color in atlas.RS_SLOT_DONE:
            return [blobs.Blob(1000, 920, 1180, 980, 1), blobs.Blob(1210, 920, 1370, 980, 1)]
        return []

    monkeypatch.setattr(blobs, "find_blobs", find)
    state, button = research.slot_buttons(g)[1]
    assert state == "done"
    assert button.x == 1290 and button.anchor == research.SLOT_ANCHOR


@pytest.mark.parametrize("order", ["newest", "append"])
def test_a_slow_claim_is_waited_for_and_never_clicked_twice(fake, order):
    """The claim shows a few reads after the click: the panel is not clicked again (the
    running research sliding into it would put its gem Speed up under the pointer)."""
    g = fake(["green", "orange"], order=order, claim_lag=3)
    research.go_research(g)
    assert _claims(g) == 1
    assert g.panels == ["orange", "orange"]


def test_a_claim_that_never_shows_stops_the_claims(fake):
    g = fake(["green", "orange"], claim_lag=10_000)
    research.go_research(g)
    assert _claims(g) == 1
    assert any("no more claims this visit" in s for s in g.statuses)
