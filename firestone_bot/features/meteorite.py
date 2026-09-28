"""Library, Meteorite tab: meteorites spent on the user's meteorite researches (owner request
2026-09-28; until then the bot did no meteorite research at all).

Measured on the owner's game (2026-09-28, Epic, 1920x1009, new style, meteorite trees I..X):
the tab shows 13 round nodes joined by lines, a start node and three chains of four layers
(a layer needs levels in the one before it); maxed nodes glow. A node's popup shows its icon,
"Level 6/25" and a green "Research" button with the cost in meteorites (750 for Tank
Specialization, 800 for Attribute Armor); research is instant. The counter top right is
dimmed while a popup is open (a "4" scored 0.67), so it is read with none.

A visit (MeteoriteResearch, default off):
1. The library, its Meteorite tab, the pointer parked; the counter (two reads that agree) and
   the tree (vision/meteorite_nodes.py): each node, maxed or not, its level and research.
   The names found give the tree's layout in the wiki data (research_data): the trees whose
   13 names hold every one of them. When those share one name set (the same set can be laid
   out several ways), the nodes are named again within it, each name once: a look-alike pair
   rejected on its own (Weak / Powerless Boss below 1280 px) is then told apart. Parents come
   from the lines on screen; when they do not read as the expected tree, from the layout's
   branches where every matching layout agrees (the wiki had tree V's last layer wrong).
2. Each priority (MeteoritePriority1..5, in order): maxed or absent, the next one. Otherwise
   its popup: the popup's icon must be that research, then the cost is read and the green
   Research button required; the counter minus the cost must stay at or above the reserve
   (MeteoriteReserve, 0 = none). The same priority is bought again while allowed (the tree
   is read again after each purchase: the node may be maxed now). A popup without the green
   button is taken as locked (locked nodes were never seen): the node before it on its chain
   is bought instead, and the one before that when it is locked too. A priority, or the node
   it waits for, that costs more than allowed ends the priorities: nothing cheaper is bought
   in its place, the meteorites are saved for it.
3. Nothing bought by the priorities and MeteoriteAnyOther on: the cheapest other node that
   is not maxed (the layout's costs, a priority first at the same cost), same checks.

A purchase counts only when the counter, read again with the popup closed, dropped by exactly
the popup's cost; anything else ends the visit with a capture. The counter read 1,278 for
1,276 on a capture resized to 1152 px wide: a misread must stop the bot, never let it go on
blind. What the game does right after Research was not observed (the popup may stay with the
next level's cost, or close): a popup still open is closed. At most MAX_PURCHASES a visit;
the Firestone tab is selected again at the end, where the research step expects it. A visit
that bought nothing makes the next one wait an hour: meteorites come slowly. A dry run reads
the counter and the tree and stops at the first node it would open.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from firestone_bot import research_data
from firestone_bot.features import token_counter
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas, meteorite_nodes
from firestone_bot.vision.atlas import Point
from firestone_bot.vision.meteorite_nodes import Node

log = logging.getLogger("firestone_bot")

PREFIX = "Meteorite research:"
PRIORITY_KEYS = tuple(f"MeteoritePriority{i}" for i in range(1, 6))
MAX_PURCHASES = 10  # a visit; the rest waits for the next one
MAX_POPUPS = 40  # popups opened in a visit (a locked priority opens two per purchase)
MAX_CHAIN = 5  # a start node and four layers: no parent chain is longer
# A pressed node wears a gold ring (seen under an open popup) that the cyan ring detector
# misses: the tree and the counter are read with no popup and the pointer off the tree.
PARK_MS = 300
TAB_MS = 1000
POPUP_MS = 800
POPUP_WAIT_MS = 3000  # the popup scales in
CLOSE_MS = 500
RESEARCH_MS = 1000
TAKEN_MS = 5000  # research is instant: the counter drops at once, patience for the server
POLL_MS = 150
PAUSE_S = 3600  # after a visit that bought nothing
PAUSE_KEY = "meteorite_pause_until"  # Game.vars, time.monotonic() seconds
UNKNOWN = object()  # Tab.parent(): the node before this one is not known

monotonic = time.monotonic  # the tests move the clock


# -- settings --------------------------------------------------------------------------------
def priorities(s: Settings) -> list[str]:
    """The user's priorities in order, as the data's names (compared case-insensitively:
    the game writes "Tank specialization"), each once."""
    known = {n.casefold(): n for n in research_data.meteorite_choices()}
    out: list[str] = []
    for key in PRIORITY_KEYS:
        name = known.get(s.get(key).strip().casefold())
        if name and name not in out:
            out.append(name)
    return out


def reserve(s: Settings) -> int:
    """Meteorites never spent (MeteoriteReserve; blank or 0 = none)."""
    raw = s.get("MeteoriteReserve").strip().replace(",", "")
    try:
        return max(0, int(raw or 0))
    except ValueError:
        return 0


def due(g: Game) -> bool:
    """Whether the Meteorite tab should be visited now."""
    return g.settings.flag("MeteoriteResearch") and monotonic() >= g.vars.get(PAUSE_KEY, 0.0)


# -- the tree's layout -----------------------------------------------------------------------
def layouts_for(found: set[str]) -> list[str]:
    """Keys of the data's meteorite trees whose 13 names hold every name in `found`."""
    return [
        k for k in research_data.load()["meteorite"] if found <= research_data.meteorite_names_of(k)
    ]


def name_set(keys: list[str]) -> frozenset[str] | None:
    """The trees' one name set, None when there are several (or no tree)."""
    sets = {frozenset(research_data.meteorite_names_of(k)) for k in keys}
    return next(iter(sets)) if len(sets) == 1 else None


def layout_parents(keys: list[str]) -> dict[str, str | None]:
    """Research -> the one before it on its branch (None for the start), where every tree
    of `keys` holding the research agrees."""
    seen: dict[str, set[str | None]] = {}
    for k in keys:
        t = research_data.meteorite_tree(k)
        start = t["start"][0]
        seen.setdefault(start, set()).add(None)
        for branch in t["branches"].values():
            prev = start
            for name, _, _ in branch:
                seen.setdefault(name, set()).add(prev)
                prev = name
    return {n: next(iter(ps)) for n, ps in seen.items() if len(ps) == 1}


def layout_costs(keys: list[str]) -> dict[str, int]:
    """Research -> its cost in the trees of `keys` (the lowest when they differ); used to
    order the other nodes only, the popup's cost is what is paid."""
    out: dict[str, int] = {}
    for k in keys:
        t = research_data.meteorite_tree(k)
        rows = [t["start"]] + [row for branch in t["branches"].values() for row in branch]
        for name, _, cost in rows:
            if cost:
                out[name] = min(cost, out.get(name, cost))
    return out


@dataclass
class Tab:
    """The Meteorite tab as read: nodes (capture px of METEORITE_TREE_RECT at `scale`)."""

    nodes: list[Node]
    scale: float
    graph_read: bool = False  # the parents come from the lines on screen
    names: frozenset[str] | None = None  # the tree's 13 names, when its layout was found
    parents: dict[str, str | None] = field(default_factory=dict)
    costs: dict[str, int] = field(default_factory=dict)

    def node(self, name: str) -> Node | None:
        want = name.casefold()
        return next((n for n in self.nodes if n.name and n.name.casefold() == want), None)

    def parent(self, name: str):
        """The research `name` needs, None for the start node, UNKNOWN when not known."""
        return self.parents.get(name, UNKNOWN)

    def point(self, node: Node) -> Point:
        x1, y1 = atlas.METEORITE_TREE_RECT[:2]
        return Point(
            round(x1 + node.cx / self.scale), round(y1 + node.cy / self.scale), atlas.ANCHOR_CENTER
        )


def analyse(rgb: np.ndarray, scale: float, read=None, refs=None) -> Tab:
    """The tab from an RGB capture of METEORITE_TREE_RECT (`read`: the level reader)."""
    refs = refs or meteorite_nodes.references()
    nodes = meteorite_nodes.detect_nodes(rgb, scale)
    if read is not None:
        meteorite_nodes.read_levels(rgb, nodes, scale, read)
    integral = meteorite_nodes.icon_integral(rgb)
    refs.assign(integral, nodes, scale)
    keys = layouts_for({n.name for n in nodes if n.name})
    names = name_set(keys)
    if names is not None:
        refs.assign(integral, nodes, scale, names)
    tab = Tab(nodes, scale, names=names, costs=layout_costs(keys))
    wiki = layout_parents(keys)
    graph = meteorite_nodes.chains(len(nodes), meteorite_nodes.tree_edges(rgb, nodes, scale))
    if graph is None:
        tab.parents = {n.name: wiki[n.name] for n in nodes if n.name in wiki}
        return tab
    tab.graph_read = True
    for i, p in meteorite_nodes.parents(graph).items():
        name = nodes[i].name
        if name is None:
            continue
        if p is None:
            tab.parents[name] = None
        elif nodes[p].name is not None:
            tab.parents[name] = nodes[p].name
        elif name in wiki:
            tab.parents[name] = wiki[name]
    return tab


# -- reading the screen (the tests replace these) -------------------------------------------
def _park(g: Game) -> None:
    g.move_to(atlas.METEORITE_PARK)
    g.sleep(PARK_MS)


def read_counter(g: Game) -> int | None:
    """The meteorite counter, read twice alike with the pointer parked (no popup open)."""
    _park(g)
    return token_counter.read_stable(g, atlas.METEORITE_COUNTER_DIGITS)


def read_tab(g: Game) -> Tab:
    _park(g)
    rect = atlas.METEORITE_TREE_RECT
    img = g.region_image(rect, atlas.ANCHOR_CENTER)
    scale = img.shape[1] / (rect[2] - rect[0])
    return analyse(
        np.ascontiguousarray(img[:, :, ::-1]),
        scale,
        read=lambda crop: token_counter.read_image(g, crop),
    )


def popup_open(g: Game) -> bool:
    return g.found(atlas.METEORITE_POPUP_X) and g.found(atlas.METEORITE_POPUP_X_RING)


def popup_name(g: Game, names: frozenset[str] | None) -> str | None:
    """The research whose icon the open popup shows (within the tree's names when known)."""
    rect = atlas.METEORITE_POPUP_ICON_RECT
    try:
        img = g.region_image(rect, atlas.ANCHOR_CENTER)
    except Exception:  # a capture error: the popup is not trusted
        log.debug("meteorite popup icon not captured", exc_info=True)
        return None
    scale = img.shape[1] / (rect[2] - rect[0])
    cx, cy = (rect[2] - rect[0]) / 2 * scale, (rect[3] - rect[1]) / 2 * scale
    rgb = np.ascontiguousarray(img[:, :, ::-1])
    name, _ = meteorite_nodes.popup_research(
        meteorite_nodes.references(), rgb, cx, cy, scale, names
    )
    return name


def popup_cost(g: Game) -> int | None:
    """The cost on the popup's Research button, when two reads a moment apart agree."""

    def once() -> int | None:
        try:
            img = g.region_image(atlas.METEORITE_POPUP_COST, atlas.ANCHOR_CENTER)
            return token_counter.read_image(g, img)
        except Exception:  # a capture error, missing digit templates: unreadable
            log.debug("meteorite cost unreadable", exc_info=True)
            return None

    first = once()
    for _ in range(2):
        g.sleep(POLL_MS)
        now = once()
        if now is not None and now == first:
            return now
        first = now
    return None


# -- the visit -------------------------------------------------------------------------------
@dataclass
class _Visit:
    wanted: list[str]
    keep: int  # the reserve
    counter: int | None = None  # read with no popup open, or checked by a drop
    tab: Tab | None = None
    bought: list[str] = field(default_factory=list)
    popups: int = 0
    stop: str = ""  # why the visit ends early
    locked: set[str] = field(default_factory=set)  # popups without the Research button
    price: dict[str, int] = field(default_factory=dict)  # costs read (or known) above budget


def visit(g: Game) -> int:
    """Spend meteorites on the Meteorite tab; returns the number of purchases."""
    s = g.settings
    v = _Visit(priorities(s), reserve(s))
    any_other = s.flag("MeteoriteAnyOther")
    if not v.wanted and not any_other:
        g.status(f"{PREFIX} no priority chosen and other nodes are off, nothing to buy")
        g.vars[PAUSE_KEY] = monotonic() + PAUSE_S
        return 0
    g.focus()
    g.status(f"{PREFIX} opening the library")
    g.require_screen(atlas.TOWN_LIBRARY, atlas.DIALOG_CLOSE_X, via_town=True)
    g.tap(atlas.METEORITE_TAB, TAB_MS)
    g.wait_still()
    _spend(g, v, any_other)
    _close_popup(g, v)
    g.tap(atlas.RS_FIRESTONE_TREE, TAB_MS)  # the research step expects its tab
    g.wait_still()
    big_close(g)
    if not v.bought and v.stop != "dry run":  # a dry run leaves the live run its visit
        g.vars[PAUSE_KEY] = monotonic() + PAUSE_S
        g.status(f"{PREFIX} nothing bought this visit, next visit in 1 h")
    return len(v.bought)


meteorite = visit  # entry point for tools/run_feature.py


def _spend(g: Game, v: _Visit, any_other: bool) -> None:
    v.counter = read_counter(g)
    if v.counter is None:
        g.status(f"{PREFIX} the meteorite counter is not readable, nothing spent")
        g.save_diagnostic("meteorite-counter.png")
        v.stop = "counter"
        return
    if not _rescan(g, v):
        return
    tab = v.tab
    assert tab is not None
    open_ = sum(not n.maxed for n in tab.nodes)
    kept = f", {v.keep:,} kept" if v.keep else ""
    lines = "lines read" if tab.graph_read else "lines unread, wiki layout"
    g.status(
        f"{PREFIX} {v.counter:,} meteorites{kept}; {len(tab.nodes)} nodes, {open_} to research "
        f"({lines})"
    )
    for name in v.wanted:
        if not _priority(g, v, name):
            break
    if not v.bought and any_other and not v.stop:
        _any_other(g, v)


def _rescan(g: Game, v: _Visit) -> bool:
    v.tab = read_tab(g)
    if v.tab.nodes:
        return True
    g.status(f"{PREFIX} no node found on the Meteorite tab, nothing more spent")
    g.save_diagnostic("meteorite-tree.png")
    v.stop = "tree"
    return False


def _capped(g: Game, v: _Visit) -> bool:
    if len(v.bought) < MAX_PURCHASES:
        return False
    g.status(f"{PREFIX} {MAX_PURCHASES} purchases this visit, the rest waits for the next one")
    v.stop = "cap"
    return True


def _priority(g: Game, v: _Visit, name: str) -> bool:
    """Buy priority `name` (or what it waits for) while allowed. False: no more priorities
    this visit (saving up for this one, or the visit ends)."""
    target, depth = name, 0
    while True:
        if v.stop or _capped(g, v):
            return False
        assert v.tab is not None
        node = v.tab.node(target)
        if node is None:
            if target == name:
                g.status(f"{PREFIX} {name} is not found in this tree")
            else:
                g.status(f"{PREFIX} {name} waits for {target}, which is not found on the tab")
            return True
        if node.maxed:
            if target == name:
                g.status(f"{PREFIX} {name} is maxed")
            else:
                g.status(f"{PREFIX} {name} is locked though {target} before it is maxed")
            return True
        outcome = "locked" if target in v.locked else _attempt(g, v, node, name)
        if outcome == "bought":
            target, depth = name, 0
            v.locked.clear()  # what a purchase unlocked is tried again
            continue
        if outcome == "poor":
            _saving(g, v, target, name)
            return False
        if outcome != "locked":
            return False
        v.locked.add(target)
        parent = v.tab.parent(target)
        depth += 1
        if parent is UNKNOWN or parent is None or depth > MAX_CHAIN:
            g.status(f"{PREFIX} {target} is locked and the research before it is unknown")
            return True
        g.status(f"{PREFIX} {target} is locked, trying {parent} before it")
        target = parent


def _saving(g: Game, v: _Visit, target: str, name: str) -> None:
    price = v.price.get(target, 0)
    counter = v.counter or 0
    goal = target if target == name else f"{target} (before {name})"
    if v.keep and counter >= price:
        g.status(
            f"{PREFIX} {goal} costs {price:,}; {counter:,} meteorites and {v.keep:,} are kept "
            "in reserve, saving up"
        )
    else:
        g.status(f"{PREFIX} {goal} costs {price:,}, {counter:,} meteorites: saving up for it")


def _any_other(g: Game, v: _Visit) -> None:
    """The cheapest node that is not maxed, again while allowed."""
    rank = {n: i for i, n in enumerate(v.wanted)}
    while not v.stop and not _capped(g, v):
        assert v.tab is not None and v.counter is not None
        budget = v.counter - v.keep
        choices = []
        for n in v.tab.nodes:
            if not n.name or n.maxed or n.name in v.locked:
                continue
            price = v.price.get(n.name, v.tab.costs.get(n.name))
            if price is not None and price > budget:
                continue
            key = (price if price is not None else 1 << 30, rank.get(n.name, len(rank)), n.name)
            choices.append((key, n))
        if not choices:
            g.status(f"{PREFIX} other nodes: none within {max(budget, 0):,} meteorites")
            return
        node = min(choices, key=lambda c: c[0])[1]
        outcome = _attempt(g, v, node, node.name)
        if outcome == "bought":
            v.locked.clear()
        elif outcome == "locked":
            v.locked.add(node.name)
        elif outcome != "poor":  # poor: dearer than its layout says (kept in v.price)
            return


def _popup_shown(g: Game) -> bool:
    waited = 0
    while True:
        if popup_open(g):
            return True
        if waited >= POPUP_WAIT_MS:
            return False
        g.sleep(250)
        waited += 250


def _close_popup(g: Game, v: _Visit) -> bool:
    """Close the popup when one is open; False (the visit ends) when it stays."""
    if not popup_open(g):
        return True
    g.tap(atlas.METEORITE_POPUP_CLOSE, CLOSE_MS)
    g.wait_still()
    if not popup_open(g):
        return True
    g.status(f"{PREFIX} the research popup did not close, stopping")
    g.save_diagnostic("meteorite-popup-close.png")
    v.stop = v.stop or "popup"
    return False


def _attempt(g: Game, v: _Visit, node: Node, goal: str) -> str:
    """Open `node`'s popup and buy one level when every check passes: "bought", "locked"
    (no green Research button), "poor" (above the budget; the price is kept) or "fail" (the
    visit ends, v.stop says why)."""
    name = node.name or "?"
    assert v.tab is not None and v.counter is not None
    v.popups += 1
    if v.popups > MAX_POPUPS:
        g.status(f"{PREFIX} {MAX_POPUPS} popups opened this visit, stopping")
        v.stop = "popups"
        return "fail"
    g.tap(v.tab.point(node), POPUP_MS)
    if getattr(g, "dry_run", False):
        # no input was sent: there is no popup to check, and nothing is bought
        g.status(f"{PREFIX} dry run, {name}'s popup would be checked here, stopping")
        v.stop = "dry run"
        return "fail"
    g.wait_still()
    if not _popup_shown(g):
        g.status(f"{PREFIX} the popup of {name} did not open, nothing more spent")
        g.save_diagnostic("meteorite-popup.png")
        v.stop = "popup"
        return "fail"
    shown = popup_name(g, v.tab.names)
    if shown != name:
        g.sleep(300)  # still scaling in
        shown = popup_name(g, v.tab.names)
    if shown != name:
        g.status(
            f"{PREFIX} the popup shows {shown or 'an unknown research'} instead of {name}, "
            "nothing more spent"
        )
        g.save_diagnostic("meteorite-popup-name.png")
        v.stop = "popup"
        _close_popup(g, v)
        return "fail"
    green = g.found(atlas.METEORITE_POPUP_RESEARCH)
    cost = popup_cost(g)
    if not green:
        price = cost if cost is not None else v.tab.costs.get(name)
        if not _close_popup(g, v):
            return "fail"
        if price is not None and price > v.counter:
            v.price[name] = price  # a grey button for want of meteorites, not a lock
            return "poor"
        return "locked"
    if cost is None:
        g.status(f"{PREFIX} the cost of {name} is not readable, nothing more spent")
        g.save_diagnostic("meteorite-cost.png")
        v.stop = "cost"
        _close_popup(g, v)
        return "fail"
    if v.counter - cost < v.keep:
        v.price[name] = cost
        return "poor" if _close_popup(g, v) else "fail"
    before = v.counter
    g.tap(atlas.METEORITE_POPUP_RESEARCH_BUTTON, RESEARCH_MS)
    g.wait_still()
    if not _close_popup(g, v):
        return "fail"
    _park(g)
    after = token_counter.wait_drop(g, atlas.METEORITE_COUNTER_DIGITS, before, TAKEN_MS)
    if after is None:
        g.status(f"{PREFIX} the counter did not drop after the Research click on {name}, stopping")
        g.save_diagnostic("meteorite-not-taken.png")
        v.stop = "unconfirmed"
        return "fail"
    if before - after != cost:
        g.status(
            f"{PREFIX} the counter went from {before:,} to {after:,} after the Research click "
            f"on {name} ({cost:,} expected), stopping"
        )
        g.save_diagnostic("meteorite-counter-drop.png")
        v.stop = "drop"
        return "fail"
    v.counter = after
    v.bought.append(name)
    level = f"level {node.level + 1}, " if node.level is not None else ""
    why = f" to unlock {goal}" if goal != name else ""
    g.status(f"{PREFIX} {name} bought ({level}{cost:,} meteorites, {after:,} left){why}")
    _rescan(g, v)
    return "bought"
