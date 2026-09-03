"""Port of Functions/Research.ahk and its sub-functions (ResearchSlotTest.ahk,
ResearchStart.ahk, ResearchClicks.ahk, ResearchAfterStartTest.ahk).

The AHK globals Slot1InProcess / Slot2InProcess live in `g.vars`. ResearchAfterStartTest
(`RAST`) is not included by any AHK file; ported for completeness, unused by the main loop.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Probe

S1 = "Slot1InProcess"
S2 = "Slot2InProcess"


def research_slot_test(g: Game) -> None:
    v = g.vars
    # make sure slot 2 is purchased
    g.toast("Slot 2 Status", "Checking status of slot 2...", 1.5)
    if g.found(atlas.RS_SLOT2_LOCKED):
        g.toast("Slot 2 Status", "Slot 2 not purchased - setting to in progress", 1.5)
        v[S2] = 1
    elif g.found(atlas.RS_SLOT2_IN_PROGRESS):
        g.toast("Slot 2 Status", "Slot 2 is in progress.", 1.5)
        v[S2] = 1
    elif g.found(atlas.RS_SLOT2_FREE):
        g.move_to(atlas.RS_SLOT2_CLAIM)
        g.toast("Slot 2 Status", "Slot 2 is able to be completed for free.", 1.5)
        g.click()
        g.sleep(1000)
        v[S2] = 0
    elif g.found(atlas.RS_SLOT2_DONE):
        g.toast("Slot 2 Status", "Slot 2 is completed and ready to claim.", 1.5)
        g.move_to(atlas.RS_SLOT2_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        v[S2] = 0
    else:
        g.toast("Slot 2 Status", "Slot 2 is not in progress.", 1.5)
        v[S2] = 0
    # Slot1Check:
    g.toast("Slot 1 Status", "Checking status of slot 1... ", 1.5)
    if g.found(atlas.RS_SLOT1_IN_PROGRESS):
        g.toast("Slot 1 Status", "Slot 1 is in progress.", 1.5)
        v[S1] = 1
        return
    if g.found(atlas.RS_SLOT1_FREE):
        g.move_to(atlas.RS_SLOT1_CLAIM)
        g.toast("Slot 1 Status", "Slot 1 is able to be completed for free.", 1.5)
        g.click()
        g.sleep(1000)
        v[S1] = 0
        if v.get(S2) == 1:
            v[S1], v[S2] = 1, 0
            g.toast(
                "Changing Slot Status",
                "Changing Slot 1 to In Process and Slot 2 to Not in Process",
                2,
            )
            return
    if g.found(atlas.RS_SLOT1_DONE):
        g.toast("Slot 1 Status", "Slot 1 is completed and ready to claim.", 1.5)
        g.move_to(atlas.RS_SLOT1_CLAIM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        v[S1] = 0
        if v.get(S2) == 1:
            v[S1], v[S2] = 1, 0
            g.toast(
                "Changing Slot Status",
                "Changing Slot 1 to In Process and Slot 2 to Not in Process",
                2,
            )
        return
    g.toast("Slot 1 Status", "Slot 1 is not in progress.", 1.5)
    v[S1] = 0


def research_clicks(g: Game) -> None:
    # start or safely click away from spend gems
    g.move_to(atlas.RS_START_OR_DISMISS)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    research_slot_test(g)


def _scan_page(g: Game, width: int) -> bool:
    """Scan columns from x=1700 down to 0 for an available node. True = slot 2 became busy."""
    i = 0
    while True:
        i += 1
        xcheck = 1700 - (i - 1) * 100
        probe = Probe(xcheck, 300, xcheck + width, 750, atlas.RS_NODE_AVAILABLE, 0, "rs_node")
        hit = g.search(probe)
        if hit is not None:
            g.click_screen(hit.sx, hit.sy)  # MouseClick, Left, X, Y, 1, 0
            g.sleep(500)
            research_clicks(g)
        if g.vars.get(S2) == 1:
            return True
        if xcheck < 100:
            return False


def research_start(g: Game) -> None:
    g.move_to(atlas.RS_TREE_HOVER)
    g.toast("Setup", "Scrolling to ensure tree setup", 1.5)
    if g.vars.get(S2) == 1:
        return
    # Page 2
    g.wheel(-35)
    if _scan_page(g, 100):
        return
    g.wheel(35)
    # look for available research - Page 1
    if _scan_page(g, 50):
        return


def go_research(g: Game) -> None:
    g.focus()
    # open Library
    g.move_to(atlas.TOWN_LIBRARY)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # select Firestone tree
    g.move_to(atlas.RS_FIRESTONE_TREE)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    research_slot_test(g)
    if g.vars.get(S1, 0) == 0:
        research_start(g)
    if g.vars.get(S2, 0) == 0:
        research_start(g)
    big_close(g)


research = go_research  # entry point for tools/run_feature.py


def research_after_start_test(g: Game) -> None:
    """ResearchAfterStartTest.ahk `RAST()`; not reachable from the AHK main loop."""
    v = g.vars
    g.toast("Slot 2 Status", "Checking status of slot 2...", 1.5)
    g.move_to(atlas.RAST_SLOT2)
    g.sleep(1000)
    g.click()
    g.sleep(500)
    if g.found(atlas.RAST_IN_PROGRESS):
        g.toast("Slot 2 Status", "Slot 2 is in progress.", 1.5)
        v[S2] = 1
        big_close(g)
    else:
        g.toast("Slot 2 Status", "Slot 2 is not in progress.", 1.5)
        v[S2] = 0
    if v.get(S1) == 1:
        g.toast("Slot 1 Status", "Slot 1 is in Progress - skipping test", 1.5)
        return
    g.toast("Slot 1 Status", "Checking status of slot 1... ", 1.5)
    g.move_to(atlas.RAST_SLOT1)
    g.sleep(1000)
    g.click()
    g.sleep(500)
    if g.found(atlas.RAST_IN_PROGRESS):
        g.toast("Slot 1 Status", "Slot 1 is in progress.", 1.5)
        v[S1] = 1
        big_close(g)
    else:
        g.toast("Slot 1 Status", "Slot 1 is not in progress.", 1.5)
        v[S1] = 0
