"""Port of Functions/MapRedeem.ahk: collect finished map missions, then start new ones
(map_start) and claim the campaign.

The popup a tap on the mission list opens is read by its look (vision/mission_popup.py,
2026-10-31) instead of fixed probes and points: MR_MORE_THAN_3_MIN / MR_FREE_EARLY read one
spot of the Speed up through the thirds rule (250 px off at 21:9, under the button at 16:10
and 4:3), MR_DIALOG_OK was tapped whatever the popup (on a start popup it is the middle
reward), and MapClose tapped beside the popup blind.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.features.claim_campaign import claim_campaign
from firestone_bot.features.map_close import (
    UNREAD,
    Watch,
    close_unread,
    diagnostic_once,
    look,
    map_clear,
    map_close,
    read_after,
    wait_gone,
)
from firestone_bot.features.map_start import map_start
from firestone_bot.game import Game, StepAborted
from firestone_bot.state import MapState
from firestone_bot.vision import atlas, gems
from firestone_bot.vision.mission_popup import IN_PROGRESS, NONE, REWARDS, START, Popup

PAID_OFF = "map_paid_off"  # Game.vars: a gem met after a click believed free: no more this run
GEM_SEEN = "map_gem_seen"  # Game.vars: speed-ups in a row followed by a gem in the dialog
CHECKS_CAP = 12  # completed missions claimed per visit (one per loop; SafetyCap 3 cut it short
# with four missions done at once, owner's cycle 2026-09-07)
TAP_MS = 1000  # after a press on a popup's button: the screen-change wait or the sleep
STUCK = "a mission popup stays open"  # StepAborted: the runner leaves the map
# What a free speed-up came to (_speed_up)
DONE, GEM_MET, LEFT_OPEN = "done", "gem met", "left open"


def _okay(g: Game, p: Popup, before: np.ndarray | None = None) -> bool:
    """Press the Mission Rewards' Okay (found in `p`) and see the dialog go (`before`: the
    centre's look before the tap that opened it); one that stays is closed. False when it
    does not close."""
    assert p.green is not None
    g.focus()
    g.tap_screen(p.green.cx, p.green.cy, TAP_MS)
    gone, left = wait_gone(g, before=before)
    return gone or map_close(g, left, before=before)


def _speed_up(g: Game, p: Popup, before: np.ndarray | None = None) -> str:
    """The free speed-up of a mission under 3 minutes (`p.free`: a grey Cancel and an orange
    button with no gem in two reads and none of the paid layout's brown label; 2026-10-30
    23:06). The Mission Rewards dialog it opens is confirmed by its Okay when its Okay's row
    holds no gem; a gem where a price shows, in a dialog that is not the Mission Rewards, or
    a window the bot cannot read is never confirmed (twice in a row: no more free clicks
    this run), and the visit goes on to the troops (GEM_MET), as it did before 2026-10-31:
    the same button is not pressed again in the same visit. The rewards above the Okay can
    be gem purple (the World domination event's mystery box, the paw mission's medallion and
    crystal chest, 2026-10-29/30: read as a price, the dialog was closed unconfirmed and free
    speed-ups were off for the run, the owner's bot and report G8N62Y). LEFT_OPEN when a
    popup stays open."""
    assert p.orange is not None
    g.toast("Mission Check", "Mission can be completed early for free", 1.5)
    g.focus()
    g.tap_screen(p.orange.cx, p.orange.cy, TAP_MS)
    g.wait_still()
    # the screen after a free speed-up: one a run
    diagnostic_once(g, "mission-after-speed-up.png")
    after = read_after(g, before)
    if after.kind == REWARDS and not after.okay_row_gem:
        g.vars[GEM_SEEN] = 0
        return DONE if _okay(g, after, before) else LEFT_OPEN
    if after.kind == UNREAD:
        _paid_met(g, "a window the bot cannot read opened after a speed-up click")
        closed = close_unread(g, before, "the speed-up click")
        return GEM_MET if closed else LEFT_OPEN
    if after.kind == REWARDS or (after.kind != NONE and after.gem):
        _paid_met(g, "a gem showed after a speed-up click")
        return GEM_MET if map_close(g, after, before=before) else LEFT_OPEN
    g.vars[GEM_SEEN] = 0
    if after.kind == NONE:
        return DONE
    diagnostic_once(g, "mission-dialog-unknown.png")
    return DONE if map_close(g, after, before=before) else LEFT_OPEN


def _checks(g: Game, watch: Watch | None = None) -> bool:
    """The `Checks:` label loop: returns when the AHK code reaches `Troops:`. False when a
    mission popup could not be closed (the map section stops). `watch`: the map's look
    before the last tap on the list, for map_start's first click."""
    watch = watch or Watch()
    cap = max(int(g.settings.get("SafetyCap") or 0), CHECKS_CAP)
    n = 0
    while True:  # Checks:
        g.toast("Mission Check", "Checking Mission Progress", 1.5)
        g.focus()
        if not map_clear(g, watch):
            return False
        # look for no missions
        if g.found(atlas.MR_NO_MISSIONS):
            g.toast("Mission Check", "No active missions found", 1.5)
            g.focus()
            return True  # Goto, Troops
        # check for already completed missions
        done = g.found(atlas.MR_MISSION_DONE)
        if done:
            g.toast("Mission Check", "Mission is already complete!", 1.5)
        before = look(g)
        g.tap(atlas.MR_FIRST_MISSION, 1000)  # hover then click (a bare click can be lost)
        g.wait_still()  # fast timing: the popup has scaled in before it is read
        p = read_after(g, before)
        watch.ref, watch.clicked, watch.outcome = before, None, None
        if p.kind == UNREAD:
            return close_unread(g, before, "the tap on the mission list")  # Goto, Troops
        if p.kind == REWARDS and not p.okay_row_gem:
            if not done:
                g.toast("Mission Check", "Mission is already complete!", 1.5)
            if not _okay(g, p, before):
                return False
            g.sleep(1000)  # the panel re-lays out before the next mission shows its Claim
        elif p.kind == IN_PROGRESS and p.paid:
            g.toast("Mission Check", "Mission has more than 3 minutes remaining", 1.5)
            # the in-progress popup of game 9.1.3a (red Cancel, paid Speed up): one a run
            diagnostic_once(g, "mission-in-progress.png")
            return map_close(g, p, before=before)  # Goto, Troops
        elif p.kind == IN_PROGRESS and g.vars.get(PAID_OFF):
            g.status("Mission Check: the speed-up button costs gems, not clicked")
            diagnostic_once(g, "mission-paid-speed-up.png")
            return map_close(g, p, before=before)  # Goto, Troops
        elif p.kind == IN_PROGRESS and not p.free:
            # no price seen, but the Cancel is the red one of the paid layout: a price the
            # reader misses (a game update changed the paid button once, 2026-10-22)
            g.status("Mission Check: the speed-up shows no price beside a red Cancel, not clicked")
            diagnostic_once(g, "mission-speed-up-unpriced.png")
            return map_close(g, p, before=before)  # Goto, Troops
        elif p.kind == IN_PROGRESS:
            outcome = _speed_up(g, p, before)
            if outcome == LEFT_OPEN:
                return False
            if outcome == GEM_MET:
                return True  # Goto, Troops
        else:
            # check 2nd mission in case of greyed out first mission bug
            if g.found(atlas.MR_SECOND_MISSION_NOT_DONE):
                g.toast("Mission Check", "Second mission is not complete", 1.5)
            if p.kind == NONE:
                return True  # nothing opened (no list: MR_NO_MISSIONS never matches the sea)
            # Python-only: a popup the bot does not know (or a Mission Rewards with a gem in
            # its Okay's row, or a start popup) is closed, never pressed
            if p.kind != START:
                diagnostic_once(g, "mission-dialog-unknown.png")
            return map_close(g, p, before=before)  # Goto, Troops (also the fall-through case)
        n += 1
        if cap and n >= cap:
            g.status(f"MapRedeem: safety cap of {cap} iterations reached")
            return True


def _paid_met(g: Game, what: str) -> None:
    """A gem where a free button was expected: said, captured and not confirmed; the
    second time in a row, the bot's free speed-ups and refreshes are off for the run (an
    important heartbeat says so)."""
    g.save_diagnostic("mission-gem-dialog.png")
    g.vars[GEM_SEEN] = g.vars.get(GEM_SEEN, 0) + 1
    if g.vars[GEM_SEEN] < 2:
        g.status(f"Mission Check: {what}: not confirmed")
        return
    g.status(f"Mission Check: {what}: not confirmed; free speed-ups are off until restart")
    if not g.vars.get(PAID_OFF):
        g.vars[PAID_OFF] = 1
        g.heartbeat(f"Map missions: {what}, nothing confirmed (see the log)", important=True)


def map_redeem(g: Game) -> None:
    g.focus()
    # check if missions can be reset for free
    g.toast("Mission Restart", "Checking if we can reset missions for free", 1.5)
    g.focus()
    if g.found(atlas.MR_FREE_RESET) and (
        g.vars.get(PAID_OFF) or gems.shows_gem(g, atlas.MR_REFRESH_RECT)
    ):
        g.status("Mission Restart: the refresh button costs gems, not clicked")
        diagnostic_once(g, "mission-paid-refresh.png")
    elif g.found(atlas.MR_FREE_RESET):
        g.move_to(atlas.MR_FREE_RESET_BUTTON)
        g.toast("Mission Restart", "WOOHOO! FREE BUTTON!", 1.5)
        g.click()
        g.sleep(1000)
    watch = Watch()
    if not _checks(g, watch):
        # a mission popup stays open: nothing more is clicked on the map, and the runner
        # goes back to the main screen (the next step was run on the map under it)
        raise StepAborted(STUCK)
    reset_done = False  # a paid map reset made this visit (MapReset)
    while True:  # Troops:
        g.toast("Troop Check", "Checking for idle troops.", 1.5)
        g.focus()
        # Check if there are idle troops
        if g.found(atlas.MAP_TROOP_IDLE):
            g.toast("Troop Check", "Idle troops found - starting maps", 1.5)
            g.heartbeat("Map: Free troops found", important=True)
            if not map_start(g, watch):
                raise StepAborted(STUCK)
        else:
            g.toast("Troop Check", "No troops found - leaving maps", 1.5)
        # Reset the memory if we found the reset map mission button
        g.focus()
        g.sleep(500)
        if g.found(atlas.MR_RESET_AVAILABLE):
            MapState.load(g.map_state_path).reset()
            if g.settings.MapReset.strip() == "1" and not reset_done:
                # a popup the last list tap opened late: its reads saw nothing (review of
                # 34146d0); the reset's confirm point is a blind centred one
                if not map_clear(g, watch):
                    raise StepAborted(STUCK)
                g.move_to(atlas.MR_RESET_BUTTON)
                g.toast("Reset mission", "Reset map mission", 1.5)
                g.focus()
                g.sleep(500)
                g.click()
                g.sleep(1500)
                g.move_to(atlas.MR_RESET_CONFIRM)
                g.click()
                g.sleep(500)
                watch.ref = None  # new missions on the map
                # one paid reset a visit whatever SafetyCap (0 = none): the loop spent
                # gems on every pass (gem audit, 2026-10-22); the new missions start
                reset_done = True
                continue  # Goto, Troops
            if reset_done:
                g.status("MapRedeem: one paid map reset this visit")
        break
    if g.settings.flag("Campaign"):
        # the campaign icon's tap would only close a popup left open by a late list tap
        if not map_clear(g, watch):
            raise StepAborted(STUCK)
        claim_campaign(g)
