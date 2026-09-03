"""Port of Functions/subFunctions/PTree.ahk: personal tree upgrades, one block per checked
node (20 identical blocks -> table). The stray top-level BigClose() in the AHK file is dead."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def personal_tree(g: Game) -> None:
    g.move_to(atlas.PTREE_OPEN)
    g.sleep(1000)
    g.click()
    g.sleep(1500)
    for setting, node in atlas.PTREE_NODES:
        if not g.settings.flag(setting):
            continue
        g.move_to(node)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        g.move_to(atlas.PTREE_CONFIRM)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        for _ in range(2):
            g.move_to(atlas.PTREE_UPGRADE)
            g.sleep(1000)
            g.click()
            g.sleep(1000)
    big_close(g)
