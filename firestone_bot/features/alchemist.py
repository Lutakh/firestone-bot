"""Port of Functions/Alchemist.ahk: collect finished experiments, complete free ones, start
Dragon Blood / Strange Dust (and Exotic Coins when enabled).

The slot's button decides what the bot does with a running experiment: an orange "Speed up"
with the purple gem icon costs gems and is never clicked, the same button without the gem is
free and is completed. The AHK decided on a brown timer pixel instead ("more than 3 minutes
remaining"): when that pixel missed, the start click landed on the running experiment's
button, a paid Speed up included (owner's log, 2026-09-13 16:55: a start click 17 min into
an experiment, then 7 s spent closing what it opened).
"""

from __future__ import annotations

import numpy as np

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas
from firestone_bot.vision.probes import match_mask

FREE, PAID, OTHER = "free", "paid", "other"
CONFIRM_MS = 150  # a second read of a free button: a gem drawn late never passes for free


def button_shares(img: np.ndarray) -> tuple[float, float]:
    """(orange share, gem share) of a slot button crop. The gem is purple: red and blue
    well above green. The first mask (r > 150, b > 150, g < 110) had 7 to 9 levels of margin
    on the measured gem 0x9F009D, less than a colour-managed capture shifts (macOS); the hue
    test keeps about 60, and orange, the blue panel, brown and white all fail it."""
    if img.size == 0:
        return 0.0, 0.0
    px = img[:, :, :3].astype(np.int16)
    orange = float(match_mask(px, atlas.ORANGE_1, 40).mean())
    b, gr, r = px[:, :, 0], px[:, :, 1], px[:, :, 2]
    gem = ((r > 150) & (b > 150) & (gr < 110)) | (
        (r - gr > 60) & (b - gr > 60) & (r > 100) & (b > 100)
    )
    return orange, float(gem.mean())


def button_look(img: np.ndarray) -> str:
    """FREE (orange Speed up, no gem), PAID (with the gem) or OTHER (no Speed up)."""
    orange, gem = button_shares(img)
    if orange < atlas.ALCHEMY_BUTTON_ORANGE_MIN:
        return OTHER
    return PAID if gem > atlas.ALCHEMY_BUTTON_GEM_SHARE_MAX else FREE


def _read(g: Game, slot: atlas.AlchemySlot) -> np.ndarray:
    return g.region_image(slot.button)


def free_to_complete(g: Game, slot: atlas.AlchemySlot) -> bool:
    """A running experiment whose Speed up button is free, read twice. A paid one (gem +
    cost) must never be clicked: its confirmation dialog blocks the visit and a second
    click would spend the gems."""
    if button_look(_read(g, slot)) != FREE:
        return False
    g.sleep(CONFIRM_MS)
    return button_look(_read(g, slot)) == FREE


def _key(slot: atlas.AlchemySlot) -> str:
    return slot.name.split()[0].lower()


def _complete_free(g: Game, slot: atlas.AlchemySlot) -> None:
    saved = f"alchemy_free_saved_{_key(slot)}"
    if not g.vars.get(saved):  # one capture per slot and session: ~18 free clicks a day
        g.vars[saved] = 1
        g.save_diagnostic(f"alchemy-free-{_key(slot)}.png")
    g.move_to(slot.collect)
    g.toast("Alchemy Status", f"{slot.name} experiment is free to complete", 1.5)
    g.click()
    g.sleep(1000)
    g.move_to(atlas.ALCHEMY_PARK)


def alchemist(g: Game) -> None:
    g.focus()
    # open Alchemist (its screen is required: a click by position on a town that is not
    # open lands anywhere, 2026-09-09)
    g.require_screen(atlas.TOWN_ALCHEMIST, atlas.DIALOG_CLOSE_X, via_town=True)
    g.move_to(atlas.ALCHEMY_PARK)  # the reads below are made with the pointer off the slots
    # collect completed experiments (only when the slot is running)
    collect = g.settings.flag("AlchCollect")
    blood, dust, coin = atlas.ALCHEMY_SLOTS
    # Only the slots the user runs are looked at (a user reported the bot "collecting" the
    # dust experiment with Use dust off, 2026-09-08); AHK probed all three.
    wanted = [
        slot
        for slot, on in (
            (blood, not g.settings.flag("DragonBlood")),
            (dust, not g.settings.flag("Dust")),
            (coin, g.settings.flag("Coin")),
        )
        if on
    ]
    for slot in wanted if collect else ():
        if g.found(slot.not_running):
            g.toast("Alchemy Status", f"{slot.name} alchemy is not running", 1.5)
        elif g.found(slot.complete):
            g.move_to(slot.collect)
            g.toast("Alchemy Status", f"{slot.name} experiment is complete", 1.5)
            g.click()
            g.sleep(1000)
            g.move_to(atlas.ALCHEMY_PARK)
    # free to complete
    for slot in wanted if collect else ():
        if free_to_complete(g, slot):
            _complete_free(g, slot)
    # check if don't use Dragon Blood is checked
    if not g.settings.flag("DragonBlood"):
        _start(g, blood, collect)
    # DustSearch:
    if not g.settings.flag("Dust"):
        _start(g, dust, collect)
    # ExoticCheck:
    if g.settings.flag("Coin"):
        _start(g, coin, collect)
    # FinishAlch:
    big_close(g)


def _start(g: Game, slot: atlas.AlchemySlot, collect: bool) -> None:
    """Start the slot's experiment unless one is running. A running one is recognised by
    its Speed up button first (never clicked when it costs gems), by the brown timer pixel
    of the AHK only when the button is not recognised."""
    img = _read(g, slot)
    look = button_look(img)
    orange, gem = button_shares(img)
    shares = f"button orange {orange:.2f}, gem {gem:.3f}"
    if look == PAID:
        g.toast(
            "Alchemy Status",
            f"{slot.name} experiment is running, its speed-up costs gems ({shares})",
            1.5,
        )
        return
    if look == FREE:
        if not collect:
            g.toast(
                "Alchemy Status",
                f"{slot.name} experiment is free to complete, left as is "
                "('Collect finished experiments' is off)",
                1.5,
            )
        elif free_to_complete(g, slot):
            _complete_free(g, slot)  # the free pass read it a moment too early
        else:
            g.toast("Alchemy Status", f"{slot.name} experiment is running ({shares})", 1.5)
        return  # never a start click on a button that was orange a moment ago
    if g.found(slot.in_progress):
        g.toast("Alchemy Status", f"{slot.name} experiment is running ({shares})", 1.5)
        saved = f"alchemy_running_saved_{_key(slot)}"
        if not g.vars.get(saved):  # the button was not recognised: keep one capture
            g.vars[saved] = 1
            g.save_diagnostic(f"alchemy-running-{_key(slot)}.png")
        return
    g.sleep(CONFIRM_MS)
    if button_look(_read(g, slot)) != OTHER:
        return  # a Speed up drawn a moment late: never a start click on it
    g.move_to(slot.start)
    g.toast("Alchemy Status", f"Starting {slot.name} experiment", 1.5)
    g.click()
    g.sleep(1000)
