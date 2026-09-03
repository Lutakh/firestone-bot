"""Port of Functions/subFunctions/CraftArtifact.ahk."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def craft_artifact(g: Game) -> None:
    if g.found(atlas.CRAFT_ARTIFACT_READY):
        g.move_to(atlas.CRAFT_ARTIFACT)
        g.toast("Craft Artifact", "Crafting an Artifact", 1.5)
        g.click()
        g.sleep(10000)
        big_close(g)
