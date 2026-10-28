"""Port of Functions/MapRedeem.ahk: collect finished map missions, then start new ones
(map_start) and claim the campaign."""

from __future__ import annotations

from firestone_bot.features.claim_campaign import claim_campaign
from firestone_bot.features.map_close import map_close
from firestone_bot.features.map_start import map_start
from firestone_bot.game import Game
from firestone_bot.state import MapState
from firestone_bot.vision import atlas, gems

PAID_OFF = "map_paid_off"  # Game.vars: a gem met after a click believed free: no more this run
GEM_SEEN = "map_gem_seen"  # Game.vars: speed-ups in a row followed by a gem in the dialog
CHECKS_CAP = 12  # completed missions claimed per visit (one per loop; SafetyCap 3 cut it short
# with four missions done at once, owner's cycle 2026-09-07)


def _checks(g: Game) -> None:
    """The `Checks:` label loop: returns when the AHK code reaches `Troops:`."""
    cap = max(int(g.settings.get("SafetyCap") or 0), CHECKS_CAP)
    n = 0
    while True:  # Checks:
        g.toast("Mission Check", "Checking Mission Progress", 1.5)
        g.focus()
        # look for no missions
        if g.found(atlas.MR_NO_MISSIONS):
            g.toast("Mission Check", "No active missions found", 1.5)
            g.focus()
            return  # Goto, Troops
        # check for already completed missions
        if g.found(atlas.MR_MISSION_DONE):
            g.toast("Mission Check", "Mission is already complete!", 1.5)
            g.tap(atlas.MR_FIRST_MISSION, 1000)  # hover then click (a bare click can be lost)
            g.tap(atlas.MR_DIALOG_OK, 1000)
            g.sleep(1000)  # the panel re-lays out before the next mission shows its Claim
        else:
            # look for greater than 3 minutes left
            g.tap(atlas.MR_FIRST_MISSION, 1000)
            g.wait_still()  # fast timing: the popup has scaled in before it is read
            if g.found(atlas.MR_MORE_THAN_3_MIN):
                g.toast("Mission Check", "Mission has more than 3 minutes remaining", 1.5)
                # the in-progress popup of game 9.1.3a (red Cancel, paid Speed up) has no
                # 1:1 capture yet: one a run, for its anchors at other sizes
                _diagnostic_once(g, "mission-in-progress.png")
                map_close(g)
                return  # Goto, Troops
            if g.found(atlas.MR_FREE_EARLY):
                # orange is no proof of free: a paid button carries a gem (three users'
                # missions completed with gems after a game update, 2026-10-22)
                g.wait_still()  # the popup has scaled in: a gem drawn late is read
                if g.vars.get(PAID_OFF) or gems.shows_gem(g, atlas.MR_EARLY_RECT):
                    g.status("Mission Check: the speed-up button costs gems, not clicked")
                    _diagnostic_once(g, "mission-paid-speed-up.png")
                    map_close(g)
                    return  # Goto, Troops
                g.move_to(atlas.MR_FREE_EARLY_BUTTON)
                g.toast("Mission Check", "Mission can be completed early for free", 1.5)
                g.click()
                g.sleep(1000)
                g.wait_still()
                # the screen after a free speed-up was never captured: one a run
                _diagnostic_once(g, "mission-after-speed-up.png")
                if gems.shows_gem(g, atlas.MR_GEM_DIALOG_RECT, atlas.ANCHOR_CENTER):
                    # a gem confirmation: never confirmed blind; twice in a row, no more
                    # speed-ups this run (a purple mission icon of the map could make one)
                    _paid_met(g, "a gem showed after a speed-up click")
                    map_close(g)
                    return  # Goto, Troops
                g.vars[GEM_SEEN] = 0
                g.tap(atlas.MR_DIALOG_OK, 1000)
            else:
                # check 2nd mission in case of greyed out first mission bug
                if g.found(atlas.MR_SECOND_MISSION_NOT_DONE):
                    g.toast("Mission Check", "Second mission is not complete", 1.5)
                # Python-only: a popup neither brown nor orange (another layout, another
                # aspect) was left open, and the map points clicked next could land on
                # its paid Speed up or its Cancel (new game version, 2026-10-22)
                _diagnostic_once(g, "mission-dialog-unknown.png")
                map_close(g)
                return  # Goto, Troops (also the fall-through case)
        n += 1
        if cap and n >= cap:
            g.status(f"MapRedeem: safety cap of {cap} iterations reached")
            return


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


def _diagnostic_once(g: Game, name: str) -> None:
    """One capture of a kind a session: the paid buttons of today's interface."""
    key = f"map_diag:{name}"
    if not g.vars.get(key):
        g.vars[key] = 1
        g.save_diagnostic(name)


def map_redeem(g: Game) -> None:
    g.focus()
    # check if missions can be reset for free
    g.toast("Mission Restart", "Checking if we can reset missions for free", 1.5)
    g.focus()
    if g.found(atlas.MR_FREE_RESET) and (
        g.vars.get(PAID_OFF) or gems.shows_gem(g, atlas.MR_REFRESH_RECT)
    ):
        g.status("Mission Restart: the refresh button costs gems, not clicked")
        _diagnostic_once(g, "mission-paid-refresh.png")
    elif g.found(atlas.MR_FREE_RESET):
        g.move_to(atlas.MR_FREE_RESET_BUTTON)
        g.toast("Mission Restart", "WOOHOO! FREE BUTTON!", 1.5)
        g.click()
        g.sleep(1000)
    _checks(g)
    reset_done = False  # a paid map reset made this visit (MapReset)
    while True:  # Troops:
        g.toast("Troop Check", "Checking for idle troops.", 1.5)
        g.focus()
        # Check if there are idle troops
        if g.found(atlas.MAP_TROOP_IDLE):
            g.toast("Troop Check", "Idle troops found - starting maps", 1.5)
            g.heartbeat("Map: Free troops found", important=True)
            map_start(g)
        else:
            g.toast("Troop Check", "No troops found - leaving maps", 1.5)
        # Reset the memory if we found the reset map mission button
        g.focus()
        g.sleep(500)
        if g.found(atlas.MR_RESET_AVAILABLE):
            MapState.load(g.map_state_path).reset()
            if g.settings.MapReset.strip() == "1" and not reset_done:
                g.move_to(atlas.MR_RESET_BUTTON)
                g.toast("Reset mission", "Reset map mission", 1.5)
                g.focus()
                g.sleep(500)
                g.click()
                g.sleep(1500)
                g.move_to(atlas.MR_RESET_CONFIRM)
                g.click()
                g.sleep(500)
                # one paid reset a visit whatever SafetyCap (0 = none): the loop spent
                # gems on every pass (gem audit, 2026-10-22); the new missions start
                reset_done = True
                continue  # Goto, Troops
            if reset_done:
                g.status("MapRedeem: one paid map reset this visit")
        break
    if g.settings.flag("Campaign"):
        claim_campaign(g)
