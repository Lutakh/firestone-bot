"""Research tree (game 9.1.1): panel states from the bottom strip, claims, node attempts.

The fake keeps the panels packed to the left like the game: a claimed panel disappears and
the others move left; a started research goes first ("newest") or after the busy ones
("append"). Both orders are tested: the bot must not depend on which one the game uses.

The fake tree has nodes at fixed places along a strip that the wheel scrolls (56 logical px
a notch, as measured, stopped at both ends); a node is seen when its box is whole inside the
tree area, as the blob size limit makes it on the game.
"""

import numpy as np
import pytest

from firestone_bot.features import research
from firestone_bot.vision import atlas, blobs

PX_PER_NOTCH = 56
NODE_W = 410
NODE_Y = 350
AREA_X1, AREA_X2 = atlas.RS_TREE_AREA[0], atlas.RS_TREE_AREA[2]
BAND_X1, BAND_X2 = atlas.RS_TREE_BAND[0], atlas.RS_TREE_BAND[2]


def _texture(x: np.ndarray) -> np.ndarray:
    """A brightness that varies along the tree without repeating (for the view shift)."""
    return 120 + 60 * np.sin(x / 37.0) + 40 * np.sin(x / 11.3 + 1.0)


class FakeGame:
    def __init__(
        self,
        panels,
        order="newest",
        popup_research=True,
        nodes=True,
        claim_lag=0,
        tree=None,
        tree_end=1400,
    ):
        self.panels = list(panels)  # "green" / "orange" / None, left to right
        self.claim_lag = claim_lag  # strip reads before a claim shows
        self.pending_claim = None
        self.reads = 0
        self.order = order
        # tree nodes: (x of the box centre at the tree's start, startable)
        if tree is None:
            tree = [(1400, popup_research)] if nodes else []
        self.tree = list(tree)
        self.tree_end = tree_end  # px the tree scrolls from its start to its end
        self.offset = 0  # px scrolled from the start
        self.taps = []
        self.statuses = []
        self.wheels = []
        self.style = "classic"
        self.popup = None  # index of the node whose popup is open
        self.popups = []

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

    def visible_nodes(self):
        out = []
        for i, (x, _) in enumerate(self.tree):
            cx = x - self.offset
            if AREA_X1 <= cx - NODE_W // 2 and cx + NODE_W // 2 <= AREA_X2:
                out.append((i, cx))
        return out

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
        elif p is atlas.RS_POPUP_RESEARCH_BUTTON:
            assert self.popup is not None and self.tree[self.popup][1]
            self.popup = None
            self._start()
        elif p is atlas.RS_POPUP_CLOSE:
            self.popup = None
        elif p.y == NODE_Y:
            for i, cx in self.visible_nodes():
                if abs(cx - p.x) < 5:
                    self.popup = i
                    self.popups.append(i)

    def wait_still(self, max_ms=1500):
        return True

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def wheel(self, n):
        self.wheels.append(n)
        self.offset = max(0, min(self.tree_end, self.offset - n * PX_PER_NOTCH))

    def found(self, probe):
        if probe is atlas.RS_POPUP_RESEARCH:
            return self.popup is not None and self.tree[self.popup][1]
        if probe is atlas.RS_POPUP_CLOSE_X:
            return self.popup is not None
        return False

    def region_image(self, rect, anchor=None):
        assert rect == atlas.RS_TREE_BAND
        xs = np.arange(BAND_X1, BAND_X2) + self.offset
        row = _texture(xs.astype(np.float32))
        return np.repeat(np.repeat(row[None, :, None], 20, axis=0), 3, axis=2).astype(np.uint8)

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
            assert rect == atlas.RS_TREE_AREA
            return [
                blobs.Blob(cx - NODE_W // 2, NODE_Y - 50, cx + NODE_W // 2, NODE_Y + 50, 1)
                for _, cx in g.visible_nodes()
            ]

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
    assert sum(g.wheels) == 0 and g.offset == 0  # the tree is left at its start


def test_a_node_seen_only_in_the_middle_of_the_tree_is_started(fake):
    """Qualitas, Tree II: the only startable node sits under the right-hand panel at the
    start and past the left edge at the end; the old search looked at the two ends only."""
    g = fake(["orange", None], tree=[(1850, True)], tree_end=1900)
    assert not any(i == 0 for i, _ in g.visible_nodes())  # hidden at the start
    g.offset = 1900
    assert not g.visible_nodes()  # and at the end
    g.offset = 0
    assert research.start_research(g, 1)
    assert g.panels == ["orange", "orange"]
    assert g.offset == 0


def test_a_node_seen_at_two_stops_is_opened_once(fake):
    g = fake(["orange", None], tree=[(1100, False), (2100, False)], tree_end=1300)
    assert not research.start_research(g, 1)
    assert sorted(g.popups) == [0, 1]


def test_popups_are_capped(fake):
    tree = [(300 + 450 * i, False) for i in range(12)]
    g = fake(["orange", None], tree=tree, tree_end=1960)
    assert not research.start_research(g, 1)
    assert len(g.popups) <= research.MAX_POPUPS


def test_view_shift_on_a_short_tree_that_stops_at_its_start(fake):
    """A tree shorter than the scan: the last stops do not move it, and are not scanned."""
    g = fake(["orange", None], tree=[(900, False)], tree_end=500)
    assert not research.start_research(g, 1)
    assert g.popups == [0]


def test_full_queue_opens_no_node(fake):
    g = fake(["orange", "orange"])
    research.go_research(g)
    assert g.wheels == []
    assert g.popups == []


def test_popups_without_a_research_button_are_closed(fake):
    g = fake([None, None], popup_research=False)
    research.go_research(g)
    # the node is tapped once (the same node at the next stops is skipped), then its X
    close = (atlas.RS_POPUP_CLOSE.x, atlas.RS_POPUP_CLOSE.y)
    tab = (atlas.RS_FIRESTONE_TREE.x, atlas.RS_FIRESTONE_TREE.y)
    assert g.taps[0] == tab
    assert g.popups == [0]
    assert g.taps[-1] == close
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
