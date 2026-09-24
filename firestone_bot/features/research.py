"""Library: keep the two firestone research slots busy (rewritten 2026-09-08 for the
research tree of game 9.1.1; the AHK Research.ahk flow and its slot probes no longer match
anything on screen and its "free completion" click landed on the gem "Speed up" button).

Flow: open the library (entry probe), select the Firestone tab, read the two slot panels at
the bottom (green button = finished, claim it; orange "Speed up" = running; neither =
empty), then while a panel is empty try the tree's node boxes from the right (deeper nodes
first, page 2 then page 1, like the AHK): a node whose popup offers the green "Research"
button is started; any other popup is closed. The gem buttons ("Complete instantly",
"Speed up") are never clicked.

The panels are read again before every claim and start, and a start is confirmed by the
number of busy panels: the game keeps the panels packed to the left with the newest research
first, so a slot followed by its index changed under the bot. With both researches finished
between two visits, the second one was left unclaimed for a whole cycle and the free slot was
reported as not started ("not seeing available research", Qualitas, 2026-09-24).
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, blobs
from firestone_bot.vision.atlas import Point

MAX_NODES_PER_PAGE = 8
SLOT_ANCHOR = (atlas.LEFT, atlas.BOTTOM)


def _strip_blobs(g: Game, colour: int, variation: int) -> list[blobs.Blob]:
    return blobs.find_blobs(
        g,
        atlas.RS_SLOT_STRIP,
        colour,
        variation,
        anchor=SLOT_ANCHOR,
        min_w=atlas.RS_BUTTON_MIN_W,
        min_h=atlas.RS_BUTTON_MIN_H,
    )


def slot_buttons(g: Game) -> dict[int, tuple[str, Point]]:
    """State and button of each busy slot, read from the strip covering both panels.

    A green button ('done', to claim) wins over the orange "Speed up" ('running'); a slot with
    neither is empty. The rightmost blob of a slot is its button: the "Completed" progress bar
    is green too and sits left of the Claim button.
    """
    out: dict[int, tuple[str, Point]] = {}
    found: list[tuple[str, blobs.Blob]] = []
    for colour in atlas.RS_SLOT_DONE:
        found += [("done", b) for b in _strip_blobs(g, colour, atlas.RS_SLOT_DONE_VAR)]
    found += [
        ("running", b) for b in _strip_blobs(g, atlas.RS_SLOT_RUNNING, atlas.RS_SLOT_RUNNING_VAR)
    ]
    for slot in range(atlas.RS_SLOT_COUNT):
        here = [(kind, b) for kind, b in found if (b.cx < atlas.RS_SLOT_SPLIT) == (slot == 0)]
        for kind in ("done", "running"):
            same = [b for k, b in here if k == kind]
            if same:
                b = max(same, key=lambda b: b.cx)
                out[slot] = (kind, Point(b.cx, b.cy, SLOT_ANCHOR))
                break
    return out


def slot_state(g: Game, slot: int) -> str:
    """'done' (green button), 'running' (orange Speed up), or 'empty'."""
    return slot_buttons(g).get(slot, ("empty", None))[0]


PARK_MS = 300  # a hovered button is lighter: let it fade before the strip is read
START_CONFIRM_MS = 3000  # the new research can reach its panel after a server round trip
MAX_ACTIONS = 6  # claims and starts in one visit (two slots: four is the most needed)
LABELS = {"running": "in progress", "done": "finished, not claimed", "empty": "free"}


def panels(g: Game) -> list[tuple[str, Point | None]]:
    """State and button of each panel, left to right, read with the pointer parked."""
    g.move_to(atlas.RS_PARK)
    g.sleep(PARK_MS)
    found = slot_buttons(g)
    return [found.get(i, ("empty", None)) for i in range(atlas.RS_SLOT_COUNT)]


def busy_count(states: list[tuple[str, Point | None]]) -> int:
    return sum(kind != "empty" for kind, _ in states)


def tree_nodes(g: Game) -> list[blobs.Blob]:
    """Node boxes on the visible tree page, rightmost first."""
    found = blobs.find_blobs(
        g,
        atlas.RS_TREE_AREA,
        atlas.RS_NODE_BOX,
        atlas.RS_NODE_VAR,
        anchor=atlas.ANCHOR_CENTER,
        min_w=atlas.RS_NODE_MIN_W,
        min_h=atlas.RS_NODE_MIN_H,
    )
    return sorted(found, key=lambda b: -b.cx)


def _started(g: Game, busy: int) -> bool:
    """A research was started: more panels are busy than before the click. The panels are
    counted, not looked up by index: the game shows the newest research in the first panel
    and moves the others right, so "slot 2 did not start" was logged for a research that
    had started in slot 1 (owner's log: 9 visits, then 3 more Research clicks on a full
    queue)."""
    waited = 0
    while True:
        if busy_count(panels(g)) > busy:
            return True
        if waited >= START_CONFIRM_MS:
            return False
        g.sleep(500)
        waited += 500 + PARK_MS


def _claimed(g: Game, done: int) -> bool:
    """The claim was taken: fewer panels show a green button than before the click. Until
    then the panels are not trusted: a read taken before the game answered still shows the
    claimed panel, and a second click at that spot could land on the orange gem "Speed up"
    of the research that slides into it."""
    waited = 0
    while True:
        states = panels(g)
        if sum(kind == "done" for kind, _ in states) < done:
            return True
        if waited >= START_CONFIRM_MS:
            return False
        g.sleep(500)
        waited += 500 + PARK_MS


def _try_node(g: Game, node: blobs.Blob, busy: int) -> bool:
    g.tap(Point(node.cx, node.cy, atlas.ANCHOR_CENTER), 800)
    g.wait_still()
    if g.found(atlas.RS_POPUP_RESEARCH):
        g.tap(atlas.RS_POPUP_RESEARCH_BUTTON, 1000)
        g.wait_still()
        if _started(g, busy):
            return True
        g.status("Research: the Research button did not start a research")
    if g.found(atlas.RS_POPUP_CLOSE_X):
        g.tap(atlas.RS_POPUP_CLOSE, 500)
        g.wait_still()
    return False


def start_research(g: Game, busy: int) -> bool:
    """Start a research while `busy` panels are in use; True when one more is busy
    afterwards. Leaves the tree on page 1."""
    g.move_to(atlas.RS_TREE_HOVER)
    for page, notches in ((2, -atlas.RS_PAGE_NOTCHES), (1, atlas.RS_PAGE_NOTCHES)):
        g.move_to(atlas.RS_TREE_HOVER)
        g.wheel(notches)
        g.wait_still()
        nodes = tree_nodes(g)
        g.status(f"Research: {len(nodes)} node(s) on page {page}")
        for node in nodes[:MAX_NODES_PER_PAGE]:
            if _try_node(g, node, busy):
                g.status(f"Research: research started (page {page}, node at x={node.cx})")
                if page == 2:
                    g.move_to(atlas.RS_TREE_HOVER)
                    g.wheel(atlas.RS_PAGE_NOTCHES)
                return True
    g.status("Research: a slot is free but no node could be started")
    g.save_diagnostic("research-no-node.png")
    return False


def go_research(g: Game) -> None:
    g.focus()
    g.status("Research: opening the library")
    g.require_screen(atlas.TOWN_LIBRARY, atlas.DIALOG_CLOSE_X, via_town=True)
    g.tap(atlas.RS_FIRESTONE_TREE, 1000)
    g.wait_still()
    claiming = True
    for _ in range(MAX_ACTIONS):
        states = panels(g)
        kinds = [kind for kind, _ in states]
        if "done" in kinds and claiming:
            # both finished between two visits: each claim moves the other panel left, so
            # the panels are read again before every action
            i = max(j for j, kind in enumerate(kinds) if kind == "done")
            g.status(f"Research: slot {i + 1} finished, claiming it")
            g.tap(states[i][1], 1500)
            g.wait_still()
            if not _claimed(g, kinds.count("done")):
                g.status("Research: the claim did not show, no more claims this visit")
                g.save_diagnostic("research-claim.png")
                claiming = False
            continue
        if "empty" not in kinds:
            break
        g.status("Research: a slot is free, looking for a node to start")
        if not start_research(g, busy_count(states)):
            break
    for i, (kind, _) in enumerate(panels(g)):
        g.status(f"Research: slot {i + 1} {LABELS[kind]}")
    big_close(g)


research = go_research  # entry point for tools/run_feature.py
