"""Port of Functions/MapRedeem.ahk: collect finished map missions, then start new ones
(map_start) and claim the campaign."""

from __future__ import annotations

from firestone_bot.features.claim_campaign import claim_campaign
from firestone_bot.features.map_close import map_close
from firestone_bot.features.map_start import map_start
from firestone_bot.game import Game
from firestone_bot.state import MapState
from firestone_bot.vision import atlas


def _checks(g: Game) -> None:
    """The `Checks:` label loop: returns when the AHK code reaches `Troops:`."""
    cap = int(g.settings.get("SafetyCap") or 0)
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
            g.move_to(atlas.MR_FIRST_MISSION)
            g.toast("Mission Check", "Mission is already complete!", 1.5)
            g.click()
            g.sleep(1000)
            g.move_to(atlas.MR_DIALOG_OK)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
        else:
            # look for greater than 3 minutes left
            g.move_to(atlas.MR_FIRST_MISSION)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
            if g.found(atlas.MR_MORE_THAN_3_MIN):
                g.toast("Mission Check", "Mission has more than 3 minutes reamining", 1.5)
                map_close(g)
                return  # Goto, Troops
            if g.found(atlas.MR_FREE_EARLY):
                g.move_to(atlas.MR_FREE_EARLY_BUTTON)
                g.toast("Mission Check", "Mission can be completed early for free", 1.5)
                g.click()
                g.sleep(1000)
                g.move_to(atlas.MR_DIALOG_OK)
                g.sleep(1000)
                g.click()
                g.sleep(1000)
            else:
                # check 2nd mission in case of greyed out first mission bug
                if g.found(atlas.MR_SECOND_MISSION_NOT_DONE):
                    g.toast("Mission Check", "Second mission is not complete", 1.5)
                return  # Goto, Troops (also the fall-through case)
        n += 1
        if cap and n >= cap:
            g.status(f"MapRedeem: safety cap of {cap} iterations reached")
            return


def map_redeem(g: Game) -> None:
    g.focus()
    # check if missions can be reset for free
    g.toast("Mission Restart", "Checking if we can reset missions for free", 1.5)
    g.focus()
    if g.found(atlas.MR_FREE_RESET):
        g.move_to(atlas.MR_FREE_RESET_BUTTON)
        g.toast("Mission Restart", "WOOHOO! FREE BUTTON!", 1.5)
        g.click()
        g.sleep(1000)
    _checks(g)
    cap = int(g.settings.get("SafetyCap") or 0)
    n = 0
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
            if g.settings.MapReset.strip() == "1":
                g.move_to(atlas.MR_RESET_BUTTON)
                g.toast("Reset mission", "Reset map mission", 1.5)
                g.focus()
                g.sleep(500)
                g.click()
                g.sleep(1500)
                g.move_to(atlas.MR_RESET_CONFIRM)
                g.click()
                g.sleep(500)
                n += 1
                if cap and n >= cap:
                    g.status(f"MapRedeem: safety cap of {cap} iterations reached")
                    break
                continue  # Goto, Troops
        break
    claim_campaign(g)
