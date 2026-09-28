"""Research tree (game 9.1.1): panel states from the bottom strip, claims, the scan of the tree
and the research started (priorities, 2026-09-28).

The fake keeps the panels packed to the left like the game: a claimed panel disappears and
the others move left; a started research goes first ("newest") or after the busy ones
("append"). Both orders are tested: the bot must not depend on which one the game uses.

The fake tree is drawn, and the bot's own blob search and icon identification run on it:
node boxes in the three box colours at the measured places (columns 459.5 px apart from x
225 at the tree's start, five row levels), each with the icon of its recorded reference
painted cell by cell (the bot's thumbnail of it is its reference), on a background whose
brightness varies along the tree (the view shift is read on it). The wheel scrolls it 56
logical px a notch between its start and its end (2478 px, as measured on every tree), and
the view shows it from x 32 to the right-hand tab panel at 1728, so a box is cut at both
edges as in the game. Screen px = logical px (the reference client).
"""

import re

import numpy as np
import pytest

from firestone_bot.features import research
from firestone_bot.platform.window import Rect
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas, blobs, research_icons
from firestone_bot.vision.viewport import Viewport

PX_PER_NOTCH = 56
TREE_END = 2478
VIEW_X1 = 32
PANEL_X = atlas.RS_TAB_PANEL_X
BOX_W, BOX_H = 383, 101
# the box colours the references were recorded with (a box's own colour moves them), BGR
BODY = {state: tuple(reversed(rgb)) for state, rgb in research_icons.REF_BODY.items()}
CANVAS_W = PANEL_X + TREE_END + 64
REFS = research_icons.default_refs()
REAL_FIND = blobs.find_blobs
REF_CLIENT = Rect(0, 31, 1920, 1009)  # the reference: screen px = logical px

# Tree XIII as the owner had it on 2026-09-28: name -> (column, row level, state)
XIII = {
    "Rage Heroes": (1, 2, "available"),
    "Energy Heroes": (2, 1, "available"),
    "Mana Heroes": (2, 3, "available"),
    "Attribute Health": (3, 0, "maxed"),
    "Attribute Armor": (3, 2, "maxed"),
    "Attribute Damage": (3, 4, "running"),
    "Guardian Power": (4, 2, "running"),
    "Expose Weakness": (5, 1, "maxed"),
    "Powerless Boss": (5, 3, "maxed"),
    "Weaklings": (6, 1, "maxed"),
    "Powerless Enemy": (6, 3, "maxed"),
    "Leadership": (7, 1, "maxed"),
    "Team Bonus": (7, 3, "maxed"),
    "Raining Gold": (8, 0, "maxed"),
    "Firestone Effect": (8, 2, "maxed"),
    "All Main Attributes": (8, 4, "maxed"),
}


class Node:
    """A box of the fake tree; state "hidden" = a locked box (never seen live: not drawn)."""

    def __init__(self, col, row, name, state="available", startable=True):
        self.col, self.row, self.name, self.state, self.startable = col, row, name, state, startable

    @property
    def x(self):
        return round(atlas.RS_COLUMN1_X + (self.col - 1) * atlas.RS_COLUMN_PITCH)

    @property
    def y(self):
        return atlas.RS_ROW_TOPS[self.row]


def xiii(locked=(), **states):
    """Tree XIII, `states` by name ("hidden": a locked column's box); `locked`: the names
    whose popup offers no Research button."""
    out = []
    for name, (col, row, state) in XIII.items():
        state = states.get(name, state)
        out.append(Node(col, row, name, state, name not in locked))
    return out


def _texture(x: np.ndarray) -> np.ndarray:
    """A brightness that varies along the tree without repeating (for the view shift)."""
    return 60 + 30 * np.sin(x / 37.0) + 25 * np.sin(x / 11.3 + 1.0)


def _paint(img: np.ndarray, node: Node) -> None:
    x, y = node.x, node.y
    img[y : y + BOX_H, x : x + BOX_W] = BODY[node.state]
    if node.name is None:  # an icon without a reference
        thumb = np.random.default_rng(node.col * 10 + node.row).integers(0, 255, (12, 12, 3))
    else:
        thumb = REFS.stacks[node.state][REFS.names.index(node.name)]
    left, top, right, bottom = research_icons.WINDOW
    ys = np.floor(np.linspace(0, bottom - top, 13)).astype(int) + y + top
    xs = np.floor(np.linspace(0, right - left, 13)).astype(int) + x + left
    for i in range(12):
        for j in range(12):
            img[ys[i] : ys[i + 1], xs[j] : xs[j + 1]] = np.round(thumb[i, j][::-1])


class FakeLibrary:
    def __init__(
        self,
        panels,
        tree=None,
        order="newest",
        claim_lag=0,
        offset=0,
        tree_end=TREE_END,
        client=REF_CLIENT,
        **settings,
    ):
        self.panels = list(panels)  # "green" / "orange" / None, left to right
        self.claim_lag = claim_lag  # strip reads before a claim shows
        self.pending_claim = None
        self.reads = 0
        self.order = order
        self.tree = xiii() if tree is None else tree
        self.tree_end = tree_end  # px the tree scrolls from its start to its end
        self.offset = offset  # px scrolled from the start
        self.settings = Settings()
        for k, v in settings.items():
            self.settings.set(k, v)
        self.vars = {}
        self.taps = []
        self.statuses = []
        self.wheels = []
        self.style = "classic"
        self.popup = None  # the node whose popup is open
        self.popups = []  # names of the nodes opened, in order
        self.sparkles = {}  # name -> grabs of its icon still hidden by a sparkle
        # the game's misses (review of 2026-09-29)
        self.dropped = set()  # WheelDowns (1 = the first) the game does not take
        self.stuck_from = None  # from this WheelDown on, the view stays where it is
        self.downs = 0
        self.dropped_ups = 0  # the next wheel ups the game does not take
        self.swallow = 0  # box taps the game takes no notice of
        self.late = 0  # the next box tap's popup opens at this look for its close button
        self.pending = None  # [node, looks left] of a popup still to open
        self.orange_x = False  # the tree shows the close button's orange where it is looked for
        self.vp = Viewport(client)
        self._canvas = None
        self._screen = None
        self._screen_key = None
        self._version = 0

    # the game's reactions
    def _claim(self, i):
        del self.panels[i]
        self.panels.append(None)

    def _start(self, node):
        if None not in self.panels:
            return  # a full queue takes nothing
        node.state = "running"
        self._canvas = None
        self._version += 1
        if self.order == "newest":
            self.panels.insert(0, "orange")
            self.panels.remove(None)
        else:
            self.panels[self.panels.index(None)] = "orange"

    # drawing
    def canvas(self):
        if self._canvas is None:
            t = _texture(np.arange(CANVAS_W, dtype=np.float32))
            img = np.zeros((1080, CANVAS_W, 3), np.uint8)
            img[:, :, 0] = (80 + 0.6 * t).astype(np.uint8)
            img[:, :, 1] = (40 + 0.3 * t).astype(np.uint8)
            img[:, :, 2] = 20
            for node in self.tree:
                if node.state != "hidden":
                    _paint(img, node)
            self._canvas = img
        return self._canvas

    def screen(self):
        """The screen, drawn in logical px then, for another client, resampled to it (the
        nearest logical pixel of every screen pixel)."""
        key = (self.offset, self._version)
        if self._screen_key != key:
            s = np.full((1080, 1920, 3), 50, np.uint8)
            s[:, VIEW_X1:PANEL_X] = self.canvas()[:, VIEW_X1 + self.offset : PANEL_X + self.offset]
            s[:, PANEL_X:] = (120, 110, 100)  # the tab panel
            c = self.vp.client
            if c != REF_CLIENT:
                f = self.vp.ref_scale / self.vp.scale  # logical px per screen px
                lx = 960 + (np.arange(c.w) + 0.5 - c.w / 2) * f
                ly = 31 + 1009 / 2 + (np.arange(c.h) + 0.5 - c.h / 2) * f
                out = np.zeros((c.y + c.h, c.x + c.w, 3), np.uint8)
                out[c.y :, c.x :] = s[ly.astype(int).clip(0, 1079)][:, lx.astype(int).clip(0, 1919)]
                s = out
            self._screen, self._screen_key = s, key
        return self._screen

    def grab(self, r):
        s = self.screen()
        out = np.zeros((r.h, r.w, 3), np.uint8)
        y1, y2 = max(0, r.y), min(s.shape[0], r.y + r.h)
        x1, x2 = max(0, r.x), min(s.shape[1], r.x + r.w)
        out[y1 - r.y : y2 - r.y, x1 - r.x : x2 - r.x] = s[y1:y2, x1:x2]
        return out

    def node_at(self, x, y):
        for node in self.tree:
            vx = node.x - self.offset
            if node.state == "hidden" or not node.y <= y < node.y + BOX_H:
                continue
            if max(vx, VIEW_X1) <= x < min(vx + BOX_W, PANEL_X):
                return node
        return None

    # Game API used by the feature
    def _viewport(self):
        return self.vp

    def region_image(self, rect, anchor=None):
        sx1, sy1 = self.vp.to_screen(rect[0], rect[1], anchor)
        sx2, sy2 = self.vp.to_screen(rect[2], rect[3], anchor)
        img = self.grab(Rect(sx1, sy1, sx2 - sx1, sy2 - sy1)).copy()
        icon = rect[2] - rect[0] == research_icons.PAD + research_icons.RECT_W
        node = self.node_at(rect[0] + 20, rect[1] + 30) if icon else None
        if node is not None and self.sparkles.get(node.name):
            self.sparkles[node.name] -= 1
            img[30:60, 20:110] = 255  # a white streak over the icon
        return img

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
            assert self.popup is not None and self.popup.startable
            self._start(self.popup)
            self.popup = None
        elif p is atlas.RS_POPUP_CLOSE:
            self.popup = None
        elif p is not atlas.RS_FIRESTONE_TREE:
            assert self.popup is None, "a box tapped over an open popup"
            node = self.node_at(p.x, p.y)
            assert node is not None, f"a tap on no box at {p}"
            assert node.state == "available", f"a tap on a {node.state} box"
            if self.swallow:
                self.swallow -= 1
            elif self.late:
                self.pending, self.late = [node, self.late], 0
            else:
                self.popup = node
                self.popups.append(node.name)

    def wait_still(self, max_ms=1500):
        return True

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass

    def wheel(self, n):
        self.wheels.append(n)
        if n < 0:
            self.downs += 1
            if self.downs in self.dropped or (self.stuck_from and self.downs >= self.stuck_from):
                return
        elif self.dropped_ups:
            self.dropped_ups -= 1
            return
        self.offset = max(0, min(self.tree_end, self.offset - n * PX_PER_NOTCH))

    def found(self, probe):
        if probe is atlas.RS_POPUP_RESEARCH:
            return self.popup is not None and self.popup.startable
        if probe is atlas.RS_POPUP_CLOSE_X:
            if self.pending is not None:
                self.pending[1] -= 1
                if not self.pending[1]:
                    self.popup = self.pending[0]
                    self.popups.append(self.popup.name)
                    self.pending = None
            return self.popup is not None or self.orange_x
        return False

    def require_screen(self, p, expect, settle_ms=1500, via_town=False):
        pass

    def save_diagnostic(self, name):
        self.statuses.append(f"diag:{name}")


@pytest.fixture
def fake(monkeypatch):
    def make(*args, **kw):
        g = FakeLibrary(*args, **kw)

        def find(game, rect, color=None, variation=0, **kw):
            if rect != atlas.RS_SLOT_STRIP:
                return REAL_FIND(game, rect, color, variation, **kw)
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

        monkeypatch.setattr(blobs, "find_blobs", find)
        monkeypatch.setattr(blobs.capture, "grab", g.grab)
        monkeypatch.setattr(research, "big_close", lambda game: game.statuses.append("big_close"))
        return g

    return make


def _claims(g):
    return sum(s.endswith("finished, claiming it") for s in g.statuses)


def _research_clicks(g):
    return g.taps.count((atlas.RS_POPUP_RESEARCH_BUTTON.x, atlas.RS_POPUP_RESEARCH_BUTTON.y))


def _starts(g):
    """The start lines as the owner's log watcher counts them."""
    return [
        s
        for s in g.statuses
        if re.search(r"\bstarted\b", s) and not re.search(r"\b(no|not|nothing)\b", s)
    ]


def _all(state, **states):
    """Tree XIII with every box in `state` (then `states` by name)."""
    return xiii(**{**{n: state for n in XIII}, **states})


# --- panels and claims ------------------------------------------------------------------------


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
    assert g.popups == ["Energy Heroes", "Mana Heroes"]  # the right-most first, as before
    assert not any("did not" in s or "left alone" in s for s in g.statuses)
    assert len(_starts(g)) == 2
    assert g.statuses[-3:] == [
        "Research: slot 1 in progress",
        "Research: slot 2 in progress",
        "big_close",
    ]
    assert g.offset == 0  # the tree left at its start


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
    assert g.offset == 0  # the tree is left at its start


def test_full_queue_opens_no_node(fake):
    g = fake(["orange", "orange"])
    research.go_research(g)
    assert g.wheels == []
    assert g.popups == []


def test_slot_button_is_the_rightmost_blob_of_its_half(monkeypatch):
    """The "Completed" progress bar is green too and sits left of the Claim button."""
    g = FakeLibrary([None, None])

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


# --- the scan -----------------------------------------------------------------------------------


def test_the_scan_sees_every_box_once_and_finds_the_tree(fake):
    g = fake(["orange", None])
    scan = research.scan_tree(g)
    got = {b.name: (b.col, b.row, b.state) for b in scan.boxes}
    assert got == XIII
    assert scan.complete and len(scan.shifts) == 5
    assert abs(scan.shifts[-1] - TREE_END) <= 3  # measured on the view itself
    assert research.summary(scan.boxes, research.matching_layouts(scan.boxes)) == (
        "Research: tree like X/XIII/XVI/XIX/..., 16 boxes (3 available, 2 running, 11 maxed)"
    )


def test_the_tree_left_elsewhere_is_wheeled_back_to_its_start_first(fake):
    """The tree reopens where it was left (a player's scroll)."""
    g = fake(["orange", None], offset=1344)
    scan = research.scan_tree(g)
    assert {b.name: (b.col, b.row, b.state) for b in scan.boxes} == XIII


def test_a_short_tree_ends_where_the_view_stops_moving(fake):
    tree = [n for n in xiii() if n.col <= 4]
    g = fake(["orange", None], tree=tree, tree_end=560)
    scan = research.scan_tree(g)
    assert scan.complete and len(scan.shifts) == 2  # 0 and 560
    assert sorted(b.name for b in scan.boxes) == sorted(n.name for n in tree)


def test_a_smaller_client_is_scanned_and_tapped_the_same(fake):
    """A 1281x673 client, 2/3 of the reference: the boxes, the view's shifts and the taps
    are all in logical px through the Viewport."""
    g = fake(["orange", None], client=Rect(0, 0, 1281, 673), ResearchPriority1="Mana Heroes")
    scan = research.scan_tree(g)
    assert {b.name: (b.col, b.row, b.state) for b in scan.boxes} == XIII
    assert abs(scan.shifts[-1] - TREE_END) <= 6
    research.to_start(g, scan)
    assert research.start_research(g, 1)
    assert g.popups == ["Mana Heroes"] and g.offset == 0


def test_an_icon_hidden_by_a_sparkle_is_grabbed_again(fake):
    g = fake(["orange", None], ResearchPriority1="Mana Heroes")
    g.sparkles["Mana Heroes"] = 1
    assert research.start_research(g, 1)
    assert g.popups == ["Mana Heroes"]
    assert not any("unidentified" in s for s in g.statuses)


def _far_priority(fake):
    """Tree XIII with Expose Weakness (column 5) and Leadership (column 7) available,
    Leadership as priority 1 and Research something else off."""
    tree = xiii(**{"Expose Weakness": "available", "Leadership": "available"})
    return fake(["orange", None], tree=tree, ResearchPriority1="Leadership", ResearchAnyOther="0")


@pytest.mark.parametrize("dropped", [1, 2, 3])
def test_a_wheel_the_game_did_not_take_is_no_end_of_the_tree(fake, dropped):
    """Review of 2026-09-29: one WheelDown the game did not take (a hitch, an overlay) ended
    the scan at column 5, the columns after it were taken for locked ones and Expose
    Weakness started "to unlock" Leadership, available all along. One more wheel tells a
    still view from the tree's end."""
    g = _far_priority(fake)
    g.dropped = {dropped}
    assert research.start_research(g, 1)
    assert g.statuses[0] == (
        "Research: tree like X/XIII/XVI/XIX/..., 16 boxes (5 available, 2 running, 9 maxed)"
    )
    assert g.popups == ["Leadership"]
    assert _starts(g) == ["Research: Leadership started (priority 1)"]


def test_a_dropped_wheel_at_the_start_is_no_start_of_the_tree(fake):
    """The tree left one stop on: a wheel up the game did not take is no start either (the
    columns are numbered from the start)."""
    g = fake(["orange", None], offset=672)
    g.dropped_ups = 1
    scan = research.scan_tree(g)
    assert {b.name: (b.col, b.row, b.state) for b in scan.boxes} == XIII


def test_a_view_that_stops_following_the_wheel_leaves_the_far_columns_alone(fake):
    """Every WheelDown from the second on is lost: the view stays one stop on. The end came
    before the tree's last column, so the scan is incomplete, and the columns it never saw
    are unknown, not locked: nothing is started to unlock Leadership."""
    g = _far_priority(fake)
    g.stuck_from = 2
    assert not research.start_research(g, 1)
    assert g.popups == [] and _research_clicks(g) == 0
    assert g.statuses[0].endswith(", the end of the tree was out of reach")
    assert g.statuses[-1] == (
        "Research: slot left free (priorities: Leadership unseen beyond the scan's reach; "
        "Research something else is off), next search in 15 min"
    )
    assert not any("to unlock" in s for s in g.statuses)
    assert g.offset == 0


def test_the_scans_reach_is_the_last_column_seen_whole(fake):
    g = _far_priority(fake)
    assert research.scan_tree(g).reach_col >= 8
    g = _far_priority(fake)
    g.stuck_from = 2  # the view stays at 672 px: columns 1 to 5 whole (column 5 at x 2063)
    scan = research.scan_tree(g)
    assert scan.complete and scan.reach_col == 5  # the end is only ruled out by the layouts
    assert max(b.col for b in scan.boxes) == 5


# --- which research ---------------------------------------------------------------------------


def test_a_priority_is_started_wherever_it_is(fake):
    g = fake(["orange", None], ResearchPriority1="Guardian Power", ResearchPriority2="Mana Heroes")
    research.go_research(g)
    assert g.popups == ["Mana Heroes"]
    assert _starts(g) == ["Research: Mana Heroes started (priority 2)"]
    assert g.offset == 0


def test_a_priority_at_the_trees_end(fake):
    tree = xiii(**{"Firestone Effect": "available"})
    g = fake(["orange", None], tree=tree, ResearchPriority1="Firestone Effect")
    assert research.start_research(g, 1)
    assert g.popups == ["Firestone Effect"]
    assert _starts(g) == ["Research: Firestone Effect started (priority 1)"]


def test_a_box_seen_only_in_the_middle_of_the_tree_is_started(fake):
    """Qualitas, Tree II: the only startable box sits under the right-hand panel at the
    start and past the left edge at the end."""
    tree = _all("maxed", **{"Expose Weakness": "available"})
    g = fake(["orange", None], tree=tree)
    assert research.start_research(g, 1)
    assert g.popups == ["Expose Weakness"]
    assert g.panels == ["orange", "orange"]
    assert g.offset == 0


def test_a_locked_priority_gets_what_unlocks_it(fake):
    """Columns 4 to 8 locked (not drawn): Leadership (column 7) is reached through column 3,
    the nearest column seen before it; its top box first."""
    later = {n: "hidden" for n, (col, _, _) in XIII.items() if col >= 4}
    col3 = {n: "available" for n, (col, _, _) in XIII.items() if col == 3}
    g = fake(["orange", None], tree=xiii(**later, **col3), ResearchPriority1="Leadership")
    research.go_research(g)
    assert g.popups == ["Attribute Health"]
    assert _starts(g) == ["Research: Attribute Health started to unlock Leadership (priority 1)"]


def test_a_priority_whose_popup_offers_no_research_button(fake):
    tree = xiii(locked=("Energy Heroes",))
    g = fake(["orange", None], tree=tree, ResearchPriority1="Energy Heroes")
    assert research.start_research(g, 1)
    assert g.popups == ["Energy Heroes", "Rage Heroes"]
    assert _starts(g) == ["Research: Rage Heroes started to unlock Energy Heroes (priority 1)"]


def test_every_available_box_is_tried_right_most_first(fake):
    tree = xiii(locked=("Energy Heroes", "Mana Heroes"))
    g = fake(["orange", None], tree=tree)
    assert research.start_research(g, 1)
    assert g.popups == ["Energy Heroes", "Mana Heroes", "Rage Heroes"]
    assert _starts(g) == [
        "Research: Rage Heroes started (any research, the priority list is empty)"
    ]


def test_with_research_something_else_off_the_slot_stays_free(fake):
    g = fake(["orange", None], ResearchPriority1="Guardian Power", ResearchAnyOther="0")
    research.go_research(g)
    assert g.popups == [] and _research_clicks(g) == 0
    assert (
        "Research: slot left free (the priorities are maxed or running; Research something "
        "else is off), next search in 15 min"
    ) in g.statuses
    assert not any(s.startswith("diag:") for s in g.statuses)
    assert g.vars[research.NO_NODE_UNTIL] > 0 and g.offset == 0


# --- popups -----------------------------------------------------------------------------------


def test_a_tap_that_opens_no_popup_is_no_locked_box(fake):
    """Review of 2026-09-29: a box tap the game swallowed was read as a popup without a
    Research button, and Rage Heroes started "to unlock" Mana Heroes, available all along."""
    g = fake(["orange", None], ResearchPriority1="Mana Heroes", ResearchAnyOther="0")
    g.swallow = 1
    assert not research.start_research(g, 1)
    assert g.popups == [] and _research_clicks(g) == 0
    assert "Research: the popup of Mana Heroes did not open, skipped" in g.statuses
    assert "diag:research-popup.png" in g.statuses
    assert not any("to unlock" in s for s in g.statuses)
    assert g.statuses[-1] == (
        "Research: slot left free (priorities: Mana Heroes lost; Research something else is "
        "off), next search in 15 min"
    )


def test_a_late_popup_is_closed_before_the_next_tap(fake):
    """The popup opens after the bot stopped waiting for it: it is closed before the next
    box is tapped (the fake refuses a tap over an open popup)."""
    g = fake(["orange", None], ResearchPriority1="Mana Heroes")
    g.late = research.POPUP_WAIT_MS // research.POPUP_POLL_MS + 2  # the first look after
    assert research.start_research(g, 1)
    assert g.popups == ["Mana Heroes", "Energy Heroes"]
    assert _starts(g) == [
        "Research: Energy Heroes started (other research, priorities: Mana Heroes lost)"
    ]
    close = (atlas.RS_POPUP_CLOSE.x, atlas.RS_POPUP_CLOSE.y)
    assert close in g.taps and _research_clicks(g) == 1


def test_a_late_popup_is_closed_before_the_tree_is_left(fake):
    g = fake(["orange", None], ResearchPriority1="Mana Heroes", ResearchAnyOther="0")
    g.late = research.POPUP_WAIT_MS // research.POPUP_POLL_MS + 2
    assert not research.start_research(g, 1)
    assert g.popups == ["Mana Heroes"] and g.popup is None
    assert _research_clicks(g) == 0 and g.offset == 0


def test_a_close_button_seen_before_the_tap_leaves_the_box_alone(fake):
    """The tree shows the close button's orange where it is looked for (a top-row icon):
    it could not tell the popup, so the box is not tapped."""
    g = fake(["orange", None], ResearchPriority1="Mana Heroes", ResearchAnyOther="0")
    g.orange_x = True
    assert not research.start_research(g, 1)
    assert g.popups == [] and _research_clicks(g) == 0
    assert (
        "Research: the popup's close button shows before Mana Heroes is tapped, skipped"
        in g.statuses
    )
    assert not any("to unlock" in s for s in g.statuses)


# --- nothing to start -------------------------------------------------------------------------


def test_popups_without_a_research_button_are_closed(fake):
    g = fake([None, None], tree=xiii(locked=("Rage Heroes", "Energy Heroes", "Mana Heroes")))
    research.go_research(g)
    close = (atlas.RS_POPUP_CLOSE.x, atlas.RS_POPUP_CLOSE.y)
    tab = (atlas.RS_FIRESTONE_TREE.x, atlas.RS_FIRESTONE_TREE.y)
    assert g.taps[0] == tab
    assert g.popups == ["Energy Heroes", "Mana Heroes", "Rage Heroes"]  # each once
    assert g.taps[-1] == close
    assert any(s.startswith("diag:research-no-node") for s in g.statuses)
    assert "Research: a slot is free but no research could start, next search in 15 min" in (
        g.statuses
    )
    assert _starts(g) == [] and g.offset == 0


def test_no_new_search_for_a_while_after_one_that_found_nothing(fake):
    g = fake([None, None], tree=xiii(locked=("Rage Heroes", "Energy Heroes", "Mana Heroes")))
    research.go_research(g)
    wheels = len(g.wheels)
    research.go_research(g)  # the next cycle
    assert len(g.wheels) == wheels
    g.vars[research.NO_NODE_UNTIL] = 0  # 15 min later
    research.go_research(g)
    assert len(g.wheels) > wheels
