"""Research tree (game 9.1.1): slot states from the bottom panels, node attempts."""

from firestone_bot.features import research
from firestone_bot.vision import atlas, blobs


class FakeGame:
    def __init__(self, slots, popup_research=True):
        self.slots = list(slots)  # what find_blobs reports per slot zone: "green"/"orange"/None
        self.popup_research = popup_research
        self.taps = []
        self.statuses = []
        self.wheels = []
        self.style = "classic"

    # Game API used by the feature
    def focus(self):
        pass

    def status(self, s):
        self.statuses.append(s)

    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append((p.x, p.y))

    def wait_still(self, max_ms=1500):
        return True

    def move_to(self, p):
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

    _popup_open = False


def _fake_find_blobs(g, nodes):
    def find(game, rect, color=None, variation=0, **kw):
        if rect == atlas.RS_SLOT_STRIP:
            # one button per slot, in the half of the strip that slot occupies
            out = []
            for slot, state in enumerate(g.slots):
                cx = 645 if slot == 0 else 1290
                want = "green" if color in atlas.RS_SLOT_DONE else "orange"
                if state == want:
                    out.append(blobs.Blob(cx - 80, 920, cx + 80, 980, 1))
            return out
        return list(nodes)

    return find


def test_slot_states(monkeypatch):
    g = FakeGame(["orange", None])
    monkeypatch.setattr(blobs, "find_blobs", _fake_find_blobs(g, []))
    assert research.slot_state(g, 0) == "running"
    assert research.slot_state(g, 1) == "empty"
    g.slots[1] = "green"
    assert research.slot_state(g, 1) == "done"


def test_start_research_takes_the_rightmost_node_and_returns_to_page_1(monkeypatch):
    g = FakeGame(["orange", None])
    nodes = [blobs.Blob(200, 300, 600, 400, 1), blobs.Blob(1200, 300, 1600, 400, 1)]
    monkeypatch.setattr(blobs, "find_blobs", _fake_find_blobs(g, nodes))

    def tap(p, settle_ms=1500, expect=None):
        g.taps.append((p.x, p.y))
        if (p.x, p.y) == (1400, 350):
            g._popup_open = True
        elif p is atlas.RS_POPUP_RESEARCH_BUTTON:
            g._popup_open = False
            g.slots[1] = "orange"  # the game started it

    g.tap = tap
    assert research.start_research(g, 1)
    assert g.taps[0] == (1400, 350) and g.taps[1] == (800, 704)
    assert g.wheels == [-35, 35]  # page 2 first, back to page 1 after the start
    assert any("slot 2 started (page 2" in s for s in g.statuses)


def test_start_research_closes_popups_without_a_research_button(monkeypatch):
    g = FakeGame([None, None], popup_research=False)
    nodes = [blobs.Blob(200, 300, 600, 400, 1)]
    monkeypatch.setattr(blobs, "find_blobs", _fake_find_blobs(g, nodes))

    def tap(p, settle_ms=1500, expect=None):
        g.taps.append((p.x, p.y))
        g._popup_open = (p.x, p.y) == (400, 350)

    g.tap = tap
    assert not research.start_research(g, 0)
    # each page: node tapped, then the popup X
    assert g.taps == [(400, 350), (1239, 224), (400, 350), (1239, 224)]
    assert any(s.startswith("diag:research-no-node") for s in g.statuses)


def test_go_research_claims_a_finished_slot_then_starts(monkeypatch):
    g = FakeGame(["green", "orange"])
    monkeypatch.setattr(blobs, "find_blobs", _fake_find_blobs(g, []))
    monkeypatch.setattr(research, "big_close", lambda game: game.statuses.append("big_close"))
    started = []
    monkeypatch.setattr(research, "start_research", lambda game, slot: started.append(slot))

    def tap(p, settle_ms=1500, expect=None):
        g.taps.append((p.x, p.y))
        if p.anchor == research.SLOT_ANCHOR:
            g.slots[0] = None  # claimed: the slot is empty now

    g.tap = tap
    research.go_research(g)
    assert started == [0]
    assert any("slot 1 finished" in s for s in g.statuses)
    assert any("slot 2 in progress" in s for s in g.statuses)
    assert g.statuses[-1] == "big_close"


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
