"""Port of Functions/Guardian.ahk: guardian evolve and training (Magic Quarter in town).

AHK colour literal `0x0F40000` (7 digits) is read as 0xF40000; kept as RED_DOT.
"""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.features.guardian_chaos import upgrade_on_guardian_screen
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def guardian(g: Game) -> None:
    g.focus()
    # open Magic Quarter
    g.move_to(atlas.TOWN_MAGIC_QUARTER)
    g.sleep(1000)
    g.click()
    g.sleep(6500)  # the guardian screen comes up slower at times
    # check for evolve
    if g.found(atlas.GUARDIAN_EVOLVE_DOT):
        g.move_to(atlas.GUARDIAN_EVOLVE_TAB)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        g.move_to(atlas.GUARDIAN_EVOLVE_BUTTON)
        g.click()
        g.sleep(10500)
        g.move_to(atlas.GUARDIAN_BACK_TAB)  # "THIS IS THE CHAOS RIFT COORDS" in the AHK comment
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    # check for training
    if g.found(atlas.GUARDIAN_TRAIN_READY):
        g.key_down("left")
        g.sleep(2000)
        g.key_up("left")
        g.sleep(500)
        # GuardianTrain is read from the INI in AHK; the live settings object holds it
        presses = {"2": 1, "3": 2, "4": 3}.get(g.settings.GuardianTrain.strip(), 0)
        for _ in range(presses):
            g.key_down("right")
            g.sleep(100)
            g.key_up("right")
            g.sleep(100)
        g.move_to(atlas.GUARDIAN_TRAIN_BUTTON)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    # Python-only: spend the chaos-rift currency on the third tab when its bell shows
    upgrade_on_guardian_screen(g)
    big_close(g)
