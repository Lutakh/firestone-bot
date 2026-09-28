"""Meteorite research visits (features/meteorite.py) against a fake Meteorite tab.

The fake holds meteorite tree X (the wiki layout of tree 10, the owner's tree on 2026-09-28):
a layer is locked while the node before it has fewer levels than the layout's unlock level
(Tank Specialization 6, Attribute Armor 0 on the owner's screen). A node's popup shows its
research, its cost on a green Research button (grey when locked; with `grey_when_poor`, also
when the meteorites do not cover it). Research takes the cost from the counter and adds a
level; the popup then stays (`popup_stays`) or closes: what the game does was not observed.
The counter is dimmed under a popup: it reads nothing while one is open.

The tab and the popup's pixels are not drawn: read_tab, popup_name and popup_cost return
what the fake holds (the readers are tested on captures in test_meteorite_nodes.py)."""

from __future__ import annotations

import re

import pytest

from firestone_bot import research_data
from firestone_bot.features import meteorite, token_counter
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas
from firestone_bot.vision.meteorite_nodes import Node

LAYOUT = research_data.meteorite_tree("10")
TREE_X_LEVELS = {  # the owner's tree X (captures 2026-09-28): all maxed but two
    "Firestone Effect": 30,
    "Energy Heroes": 20,
    "Damage Specialization": 25,
    "Raining Gold": 30,
    "Attribute Armor": 0,
    "Rage Heroes": 20,
    "Tank Specialization": 6,
    "All Attributes": 30,
    "Attribute Damage": 20,
    "Mana Heroes": 20,
    "Healer Specialization": 25,
    "Firestone Finder": 30,
    "Attribute Health": 20,
}
WATCHED = re.compile(r"\b(no|not|nothing)\b")


def _layout():
    """name -> (max level, cost, parent, level the parent needs)."""
    unlock = dict(LAYOUT["unlock"])
    name, mx, cost = LAYOUT["start"]
    out = {name: (mx, cost, None, 0)}
    for branch in LAYOUT["branches"].values():
        prev = name
        for layer, (n, mx, cost) in enumerate(branch, start=1):
            out[n] = (mx, cost, prev, unlock[layer])
            prev = n
    return out


RESEARCH = _layout()


class FakeMeteoriteTab:
    def __init__(
        self,
        settings,
        counter=1242,
        levels=None,
        popup_stays=False,
        drop=None,
        counter_readable=True,
        popup_shows=None,
        cost_readable=True,
        grey_when_poor=False,
        graph=True,
    ):
        self.settings = settings
        self.vars = {}
        self.counter = counter
        self.levels = dict(TREE_X_LEVELS if levels is None else levels)
        self.popup_stays = popup_stays
        self.drop = drop  # meteorites a Research click takes, when not the cost
        self.counter_readable = counter_readable
        self.popup_shows = popup_shows
        self.cost_readable = cost_readable
        self.grey_when_poor = grey_when_poor
        self.graph = graph
        self.popup = None
        self.tab = None
        self.opened = []  # popups opened, in order
        self.bought = []  # Research clicks the game took
        self.taps = []
        self.lines = []
        self.diagnostics = []
        self.closed = 0
        self.library = False
        # node positions: a grid inside the tree rect, logical, centre-anchored
        x1, y1 = atlas.METEORITE_TREE_RECT[:2]
        self.pos = {
            n: (x1 + 100 + 180 * (i % 5), y1 + 100 + 200 * (i // 5)) for i, n in enumerate(RESEARCH)
        }

    # the game
    def locked(self, name):
        _, _, parent, need = RESEARCH[name]
        return parent is not None and self.levels[parent] < need

    def maxed(self, name):
        return self.levels[name] >= RESEARCH[name][0]

    def green(self, name):
        if self.locked(name) or self.maxed(name):
            return False
        return not (self.grey_when_poor and self.counter < RESEARCH[name][1])

    # what the bot reads
    def tab_view(self):
        assert self.tab == "meteorite" and self.popup is None, "the tree read under a popup"
        x1, y1 = atlas.METEORITE_TREE_RECT[:2]
        nodes = []
        for name, (x, y) in self.pos.items():
            if name not in self.levels:
                continue
            m = self.maxed(name)
            nodes.append(Node(x - x1, y - y1, 1.0, m, 190 if m else 55, self.levels[name], name))
        keys = meteorite.layouts_for(set(self.levels))
        tab = meteorite.Tab(
            nodes,
            1.0,
            graph_read=self.graph,
            names=meteorite.name_set(keys),
            costs=meteorite.layout_costs(keys),
        )
        if self.graph:
            tab.parents = {n: RESEARCH[n][2] for n in self.levels}
        else:
            tab.parents = meteorite.layout_parents(keys)
        return tab

    def read_counter(self, rect):
        assert rect == atlas.METEORITE_COUNTER_DIGITS
        if not self.counter_readable or self.popup is not None:
            return None  # dimmed under a popup
        return self.counter

    def popup_name(self):
        assert self.popup is not None
        return self.popup_shows or self.popup

    def popup_cost(self):
        assert self.popup is not None
        return RESEARCH[self.popup][1] if self.cost_readable else None

    def found(self, probe):
        if probe in (atlas.METEORITE_POPUP_X, atlas.METEORITE_POPUP_X_RING):
            return self.popup is not None
        assert probe is atlas.METEORITE_POPUP_RESEARCH, probe
        return self.popup is not None and self.green(self.popup)

    # what the bot does
    def tap(self, p, settle_ms=1500, expect=None):
        self.taps.append(p)
        if p == atlas.METEORITE_TAB:
            assert self.library
            self.tab = "meteorite"
        elif p == atlas.RS_FIRESTONE_TREE:
            assert self.popup is None
            self.tab = "firestone"
        elif p == atlas.METEORITE_POPUP_CLOSE:
            assert self.popup is not None
            self.popup = None
            self.closed += 1
        elif p == atlas.METEORITE_POPUP_RESEARCH_BUTTON:
            assert self.popup is not None and self.green(self.popup), "a click on a grey button"
            name = self.popup
            cost = RESEARCH[name][1]
            assert self.counter >= cost
            self.counter -= cost if self.drop is None else self.drop
            self.levels[name] += 1
            self.bought.append(name)
            if not self.popup_stays or self.maxed(name):
                self.popup = None
        else:
            assert self.tab == "meteorite" and self.popup is None, p
            assert p.anchor == atlas.ANCHOR_CENTER
            name = next(n for n, xy in self.pos.items() if xy == (p.x, p.y))
            self.popup = name
            self.opened.append(name)

    def require_screen(self, p, expect, settle_ms=1500, via_town=False):
        assert p == atlas.TOWN_LIBRARY and expect == atlas.DIALOG_CLOSE_X and via_town
        self.library = True

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.diagnostics.append(name)

    def focus(self):
        pass

    def wait_still(self, max_ms=1500):
        return True

    def move_to(self, p):
        pass

    def sleep(self, ms):
        pass


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def make(monkeypatch, tmp_path):
    clock = Clock()
    monkeypatch.setattr(meteorite, "monotonic", clock)

    def build(priorities=(), reserve="0", any_other=False, **kw):
        s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        s.set("MeteoriteResearch", "1")
        for i, name in enumerate(priorities, start=1):
            s.set(f"MeteoritePriority{i}", name)
        s.set("MeteoriteReserve", reserve)
        s.set("MeteoriteAnyOther", any_other)
        g = FakeMeteoriteTab(s, **kw)
        g.clock = clock
        g.big_closed = []
        monkeypatch.setattr(meteorite, "read_tab", lambda game: game.tab_view())
        monkeypatch.setattr(meteorite, "popup_name", lambda game, names: game.popup_name())
        monkeypatch.setattr(meteorite, "popup_cost", lambda game: game.popup_cost())
        monkeypatch.setattr(token_counter, "read", lambda game, rect: game.read_counter(rect))
        monkeypatch.setattr(meteorite, "big_close", lambda game: game.big_closed.append(game.tab))
        return g

    return build


def _purchases(g):
    """What a log watcher counts: lines with "bought" and none of no / not / nothing."""
    return [x for x in g.lines if "bought" in x and not WATCHED.search(x)]


def _paused(g):
    return g.vars.get(meteorite.PAUSE_KEY, 0) > g.clock.now


# -- priorities ------------------------------------------------------------------------------
def test_a_priority_is_bought_and_counted_by_the_counter(make):
    g = make(["Tank Specialization"])
    assert meteorite.visit(g) == 1
    assert g.bought == ["Tank Specialization"]
    assert _purchases(g) == [
        "Meteorite research: Tank Specialization bought (level 7, 750 meteorites, 492 left)"
    ]
    # 492 left: the second level is not affordable, nothing else is bought
    assert any("saving up" in x for x in g.lines)
    assert g.counter == 492 and not g.diagnostics and not _paused(g)


def test_the_priorities_go_in_order_and_a_maxed_one_is_skipped(make):
    levels = dict(TREE_X_LEVELS, **{"Tank Specialization": 23})
    g = make(
        ["Raining Gold", "Tank Specialization", "Attribute Armor"], counter=5000, levels=levels
    )
    assert meteorite.visit(g) == 6
    assert "Meteorite research: Raining Gold is maxed" in g.lines
    assert "Raining Gold" not in g.opened
    # Tank Specialization to its max (25), then Attribute Armor while 800 are left
    assert g.bought == ["Tank Specialization"] * 2 + ["Attribute Armor"] * 4
    assert g.counter == 5000 - 2 * 750 - 4 * 800
    assert len(_purchases(g)) == 6


def test_the_priority_names_are_compared_case_insensitively(make):
    g = make(["tank specialization"])
    assert meteorite.visit(g) == 1 and g.bought == ["Tank Specialization"]


@pytest.mark.parametrize("counter, bought", [(1242, 0), (1250, 1)])
def test_the_reserve_is_never_spent(make, counter, bought):
    g = make(["Tank Specialization"], reserve="500", counter=counter)
    assert meteorite.visit(g) == bought
    assert g.counter >= 500
    if not bought:
        assert not g.bought and g.opened == ["Tank Specialization"]
        assert any("kept in reserve" in x for x in g.lines)
        assert _paused(g) and not _purchases(g)


def test_a_dear_priority_is_saved_for_and_cheaper_ones_wait(make):
    """Attribute Armor (800) first with 790 meteorites: Tank Specialization (750) is not
    bought in its place."""
    g = make(["Attribute Armor", "Tank Specialization"], counter=790)
    assert meteorite.visit(g) == 0
    assert g.opened == ["Attribute Armor"] and not g.bought
    assert any("Attribute Armor costs 800, 790 meteorites: saving up" in x for x in g.lines)


def test_a_grey_button_for_want_of_meteorites_is_not_a_lock(make):
    g = make(["Tank Specialization"], counter=700, grey_when_poor=True)
    assert meteorite.visit(g) == 0
    assert g.opened == ["Tank Specialization"]  # Rage Heroes, before it, is not tried
    assert not any("locked" in x for x in g.lines)


# -- locked priorities -----------------------------------------------------------------------
def test_a_locked_priority_gets_the_node_before_it(make):
    """Attribute Damage (layer 4) needs 5 levels of All Attributes (at 3): two of those
    first, then Attribute Damage itself, 10 purchases at most."""
    levels = dict(TREE_X_LEVELS, **{"All Attributes": 3, "Attribute Damage": 0})
    g = make(["Attribute Damage"], counter=20000, levels=levels)
    assert meteorite.visit(g) == 10
    assert g.bought == ["All Attributes"] * 2 + ["Attribute Damage"] * 8
    assert (
        "Meteorite research: Attribute Damage is locked, trying All Attributes before it" in g.lines
    )
    assert _purchases(g)[0] == (
        "Meteorite research: All Attributes bought (level 4, 900 meteorites, 19,100 left) "
        "to unlock Attribute Damage"
    )
    assert "Meteorite research: 10 purchases this visit, the rest waits for the next one" in g.lines


def test_a_lock_two_layers_deep_goes_back_along_the_chain(make):
    """All Attributes (layer 3) needs 6 Tank Specialization, Attribute Damage 5 All
    Attributes."""
    levels = dict(
        TREE_X_LEVELS,
        **{"Tank Specialization": 3, "All Attributes": 0, "Attribute Damage": 0},
    )
    g = make(["Attribute Damage"], counter=20000, levels=levels)
    assert meteorite.visit(g) == 10
    assert (
        g.bought == ["Tank Specialization"] * 3 + ["All Attributes"] * 5 + ["Attribute Damage"] * 2
    )
    assert all(x.endswith("to unlock Attribute Damage") for x in _purchases(g)[:8])


def test_a_lock_whose_parent_is_unknown_is_left(make):
    """The lines not read: the four wiki layouts of tree X's names disagree on what
    Attribute Damage needs, so nothing is bought for it; the next priority goes on."""
    levels = dict(TREE_X_LEVELS, **{"All Attributes": 3, "Attribute Damage": 0})
    keys = meteorite.layouts_for(set(TREE_X_LEVELS))
    assert sorted(keys) == ["10", "15", "6", "C"]
    assert "Attribute Damage" not in meteorite.layout_parents(keys)
    g = make(["Attribute Damage", "Tank Specialization"], counter=2000, levels=levels, graph=False)
    assert meteorite.visit(g) == 2
    assert (
        "Meteorite research: Attribute Damage is locked and the research before it is unknown"
        in g.lines
    )
    assert g.bought == ["Tank Specialization"] * 2


# -- the counter -----------------------------------------------------------------------------
@pytest.mark.parametrize("stays", [False, True])
def test_the_popup_is_closed_after_research_whether_it_stays_or_not(make, stays):
    g = make(["Tank Specialization"], counter=2000, popup_stays=stays)
    assert meteorite.visit(g) == 2
    assert g.bought == ["Tank Specialization"] * 2
    assert g.popup is None
    # each popup opened is closed by the bot: after Research when it stays, and the third
    # one (500 left, not affordable) in either case
    assert g.closed == (3 if stays else 1)


def test_a_drop_other_than_the_cost_stops_the_visit_uncounted(make):
    g = make(["Tank Specialization"], counter=5000, drop=700)
    assert meteorite.visit(g) == 0
    assert g.bought == ["Tank Specialization"]  # one click, then nothing more
    assert (
        "Meteorite research: the counter went from 5,000 to 4,300 after the Research click on "
        "Tank Specialization (750 expected), stopping"
    ) in g.lines
    assert g.diagnostics == ["meteorite-counter-drop.png"]
    assert not _purchases(g) and _paused(g)


def test_a_counter_that_never_drops_stops_the_visit(make):
    g = make(["Tank Specialization"], counter=5000, drop=0)
    assert meteorite.visit(g) == 0
    assert len(g.bought) == 1 and g.diagnostics == ["meteorite-not-taken.png"]
    assert not _purchases(g)


def test_an_unreadable_counter_spends_nothing(make):
    g = make(["Tank Specialization"], counter_readable=False, any_other=True)
    assert meteorite.visit(g) == 0
    assert not g.opened and not g.bought
    assert "Meteorite research: the meteorite counter is not readable, nothing spent" in g.lines
    assert g.diagnostics == ["meteorite-counter.png"]
    assert g.tab == "firestone" and g.big_closed == ["firestone"]


def test_a_popup_of_another_research_buys_nothing(make):
    g = make(["Tank Specialization"], popup_shows="Precision")
    assert meteorite.visit(g) == 0
    assert not g.bought and g.popup is None
    assert any("the popup shows Precision instead of Tank Specialization" in x for x in g.lines)


def test_an_unreadable_cost_buys_nothing(make):
    g = make(["Tank Specialization"], cost_readable=False)
    assert meteorite.visit(g) == 0
    assert not g.bought and g.diagnostics == ["meteorite-cost.png"]


# -- other nodes -----------------------------------------------------------------------------
@pytest.mark.parametrize("any_other", [False, True])
def test_other_nodes_only_when_asked_and_the_cheapest_first(make, any_other):
    """The only priority is maxed: with the switch, Tank Specialization (750) before
    Attribute Armor (800), as long as the meteorites allow."""
    g = make(["Raining Gold"], counter=1600, any_other=any_other)
    assert meteorite.visit(g) == (2 if any_other else 0)
    assert g.bought == (["Tank Specialization"] * 2 if any_other else [])
    if any_other:
        assert "Meteorite research: other nodes: none within 100 meteorites" in g.lines


def test_other_nodes_skip_a_locked_one(make):
    """At 750 each, Healer Specialization comes first (by name) but needs 5 Mana Heroes."""
    levels = dict(TREE_X_LEVELS, **{"Mana Heroes": 2, "Healer Specialization": 0})
    g = make([], counter=900, levels=levels, any_other=True)
    assert meteorite.visit(g) == 1
    assert g.opened == ["Healer Specialization", "Mana Heroes"]
    assert g.bought == ["Mana Heroes"]


def test_other_nodes_after_a_dear_priority(make):
    g = make(["Attribute Armor"], counter=790, any_other=True)
    assert meteorite.visit(g) == 1
    assert g.bought == ["Tank Specialization"]


# -- the visit -------------------------------------------------------------------------------
def test_the_visit_ends_on_the_firestone_tab(make):
    g = make(["Tank Specialization"])
    meteorite.visit(g)
    assert g.taps[0] == atlas.METEORITE_TAB
    assert g.taps[-1] == atlas.RS_FIRESTONE_TREE
    assert g.big_closed == ["firestone"]


def test_nothing_to_buy_skips_the_library(make):
    g = make([])
    assert meteorite.visit(g) == 0
    assert not g.library and not g.taps and _paused(g)


def test_a_visit_that_bought_nothing_pauses_the_next_one_an_hour(make):
    g = make(["Raining Gold"])
    assert meteorite.due(g)
    meteorite.visit(g)
    assert "Meteorite research: nothing bought this visit, next visit in 1 h" in g.lines
    assert not meteorite.due(g)
    g.clock.now += meteorite.PAUSE_S - 1
    assert not meteorite.due(g)
    g.clock.now += 1
    assert meteorite.due(g)
    g.settings.set("MeteoriteResearch", "0")
    assert not meteorite.due(g)


def test_a_dry_run_stops_at_the_first_node_and_leaves_no_pause(make):
    g = make(["Tank Specialization"])
    g.dry_run = True
    assert meteorite.visit(g) == 0
    assert g.opened == ["Tank Specialization"] and not g.bought
    assert any("dry run" in x for x in g.lines) and not _purchases(g)
    assert meteorite.due(g) and not g.diagnostics


def test_a_visit_that_bought_does_not_pause(make):
    g = make(["Tank Specialization"])
    meteorite.visit(g)
    assert meteorite.due(g)


def test_status_lines_only_count_real_purchases(make):
    """Every failure line says so plainly: none of them passes for a purchase."""
    for kw in (
        {"drop": 700},
        {"drop": 0},
        {"counter_readable": False},
        {"popup_shows": "Precision"},
        {"cost_readable": False},
        {"counter": 10},
    ):
        g = make(["Tank Specialization"], **kw)
        meteorite.visit(g)
        assert not _purchases(g), kw
