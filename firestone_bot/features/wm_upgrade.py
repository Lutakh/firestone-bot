"""Port of Functions/subFunctions/WMUpgrade.ahk (+ WMLevelOnly.ahk, WMBlueprintsOnly.ahk).

Thirteen identical label blocks become a table. Semantics kept from the AHK Goto ladder:
- an UpgradeWM value that matches no "Upgrade <name>" falls into the first block (Aegis);
- a WMOptions value that matches nothing returns from no block, so the code falls through to
  the NEXT war machine block (selecting each machine in turn without upgrading);
- a Blueprints value that matches nothing falls into "Upgrade All".
The war machine is selected by clicking the FOUND pixel of its signature colour in the
bottom roster strip.
"""

from __future__ import annotations

from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Probe


def level_only(g: Game) -> None:
    if g.found(atlas.WM_LEVEL_DOT):
        # open anvil tab
        g.tap(atlas.WM_ANVIL_TAB, 1000)
        # click upgrade
        g.tap(atlas.WM_LEVEL_UPGRADE, 1000)


def bp_only(g: Game) -> None:
    # Open Blueprint tab
    g.tap(atlas.WM_BLUEPRINT_TAB, 1000)
    stats = atlas.WM_BLUEPRINT_CHOICES.get(
        g.settings.Blueprints, atlas.WM_BLUEPRINT_CHOICES["Upgrade All"]
    )
    for stat in stats:
        probe, button = atlas.WM_BLUEPRINT_STATS[stat]
        if g.found(probe):
            g.tap(button, 1000)


def wm_upgrade(g: Game) -> None:
    g.focus()  # AHK: ControlFocus,, ahk_exe Firestone.ex (typo, no-op there)
    selected = g.settings.UpgradeWM
    start = 0
    for i, (name, _) in enumerate(atlas.WAR_MACHINES):
        if selected == f"Upgrade {name}":
            g.toast("WMUpgrade", f"Selected war machine: {name}.", 1.5)
            start = i
            break
    options = g.settings.WMOptions
    for _name, color in atlas.WAR_MACHINES[start:]:
        # select war machine
        hit = g.search(Probe(*atlas.WM_ROSTER, color, 3, f"wm_{_name}"))
        if hit is not None:
            g.tap_screen(hit.sx, hit.sy)
        if options == "Level Only":
            level_only(g)
            return
        if options == "Blueprints Only":
            bp_only(g)
            return
        if options == "Level and Blueprints":
            level_only(g)
            bp_only(g)
            return
        # unknown WMOptions: fall through to the next war machine, like the AHK labels
