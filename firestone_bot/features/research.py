"""Library: keep the two firestone research slots busy (rewritten 2026-09-08 for the
research tree of game 9.1.1; the AHK Research.ahk flow and its slot probes no longer match
anything on screen and its "free completion" click landed on the gem "Speed up" button).

Flow: open the library (entry probe), select the Firestone tab, read the two slot panels at
the bottom (green button = finished, claim it; orange "Speed up" = running; neither =
empty), then for each empty slot try the tree's node boxes from the right (deeper nodes
first, page 2 then page 1, like the AHK): a node whose popup offers the green "Research"
button is started; any other popup is closed. The gem buttons ("Complete instantly",
"Speed up") are never clicked.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, blobs
from firestone_bot.vision.atlas import Point

MAX_NODES_PER_PAGE = 8
SLOT_ANCHOR = (atlas.LEFT, atlas.BOTTOM)


def slot_state(g: Game, slot: int) -> str:
    """'done' (green button), 'running' (orange Speed up), or 'empty'."""
    zone = atlas.RS_SLOT_BUTTONS[slot]
    for colour in atlas.RS_SLOT_DONE:
        if blobs.find_blobs(
            g, zone, colour, atlas.RS_SLOT_DONE_VAR, anchor=SLOT_ANCHOR, min_w=atlas.RS_BUTTON_MIN_W
        ):
            return "done"
    if blobs.find_blobs(
        g,
        zone,
        atlas.RS_SLOT_RUNNING,
        atlas.RS_SLOT_RUNNING_VAR,
        anchor=SLOT_ANCHOR,
        min_w=atlas.RS_BUTTON_MIN_W,
    ):
        return "running"
    return "empty"


def _slot_button(slot: int) -> Point:
    x1, y1, x2, y2 = atlas.RS_SLOT_BUTTONS[slot]
    return Point((x1 + x2) // 2, (y1 + y2) // 2, SLOT_ANCHOR)


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


def _try_node(g: Game, node: blobs.Blob, slot: int) -> bool:
    g.tap(Point(node.cx, node.cy, atlas.ANCHOR_CENTER), 800)
    g.wait_still()
    if g.found(atlas.RS_POPUP_RESEARCH):
        g.tap(atlas.RS_POPUP_RESEARCH_BUTTON, 1000)
        g.wait_still()
        if slot_state(g, slot) == "running":
            return True
        g.status(f"Research: the Research button did not start slot {slot + 1}")
    if g.found(atlas.RS_POPUP_CLOSE_X):
        g.tap(atlas.RS_POPUP_CLOSE, 500)
        g.wait_still()
    return False


def start_research(g: Game, slot: int) -> bool:
    """Start a research in an empty slot; True when the slot is running afterwards.
    Leaves the tree on page 1."""
    g.move_to(atlas.RS_TREE_HOVER)
    for page, notches in ((2, -atlas.RS_PAGE_NOTCHES), (1, atlas.RS_PAGE_NOTCHES)):
        g.wheel(notches)
        g.wait_still()
        nodes = tree_nodes(g)
        g.status(f"Research: {len(nodes)} node(s) on page {page}")
        for node in nodes[:MAX_NODES_PER_PAGE]:
            if _try_node(g, node, slot):
                g.status(f"Research: slot {slot + 1} started (page {page}, node at x={node.cx})")
                if page == 2:
                    g.move_to(atlas.RS_TREE_HOVER)
                    g.wheel(atlas.RS_PAGE_NOTCHES)
                return True
    g.status(f"Research: slot {slot + 1} is free but no node could be started")
    g.save_diagnostic("research-no-node.png")
    return False


def go_research(g: Game) -> None:
    g.focus()
    g.status("Research: opening the library")
    g.require_screen(atlas.TOWN_LIBRARY, atlas.DIALOG_CLOSE_X, via_town=True)
    g.tap(atlas.RS_FIRESTONE_TREE, 1000)
    g.wait_still()
    for slot in range(len(atlas.RS_SLOT_BUTTONS)):
        state = slot_state(g, slot)
        if state == "done":
            g.status(f"Research: slot {slot + 1} finished, claiming it")
            g.tap(_slot_button(slot), 1500)
            g.wait_still()
            state = slot_state(g, slot)
        if state == "running":
            g.status(f"Research: slot {slot + 1} in progress")
        elif state == "empty":
            g.status(f"Research: slot {slot + 1} is free, looking for a node to start")
            start_research(g, slot)
        else:
            g.status(f"Research: slot {slot + 1} still shows a green button, left alone")
    big_close(g)


research = go_research  # entry point for tools/run_feature.py
