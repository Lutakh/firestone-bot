"""Decorated Heroes event (calendar event, two weeks in odd months; owner request 2026-09-25).

One switch, EventDecoratedHeroes, makes the bot complete the event's eight daily challenges
and claim their stars:
- tavern plays and crystal hits: the daily limits are raised to 12 and 15 (daily.py);
- "Enlighten guardians 3 times": three enlightenments a day at x1 on the guardian screen
  (features/enlighten.py, shared with the enlightenment automation);
- researches, alchemy experiments, guild expeditions, scout missions and time online: done by
  the bot's usual actions;
- the stars of every tier reached are claimed on the event's own page (claim_page), opened
  from the events list by claim_events.

Measured on the owner's game (2026-09-25, 1920x1009): the event page has Challenges /
Medals / Stars exchange / Skins / Market tabs and eight challenge cards, each with a Claim
button that is grey until a tier is reached.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.game import Game
from firestone_bot.vision import atlas

# -- event page: claim the stars ---------------------------------------------------------------

MAX_CLAIMS = 24  # eight challenges, three tiers each
CLAIM_GREEN_MIN = 0.25  # share of a Claim button's middle band that is green when claimable
PAGE_PARK = atlas.Point(960, 250, atlas.ANCHOR_CENTER)  # the stars counter row, nothing to click


def on_page(g: Game) -> bool:
    """The Decorated Heroes page is on screen, on its Challenges tab."""
    return g.found(atlas.DH_CHALLENGES_TAB) and g.found(atlas.DH_MEDALS_TAB)


def is_page(g: Game) -> bool:
    """The Decorated Heroes page is on screen, whichever tab it opened on (the game reopens
    a screen on the tab last viewed): its own X, and its first two tab slots each in the
    selected (yellow) or the idle (blue) colour. Read with the pointer parked: a hovered
    tab is drawn lighter."""
    g.move_to(PAGE_PARK)
    g.sleep(300)
    if not g.found(atlas.DH_PAGE_CLOSE_X):
        return False
    first = g.found(atlas.DH_CHALLENGES_TAB) or g.found(atlas.DH_CHALLENGES_TAB_IDLE)
    second = g.found(atlas.DH_MEDALS_TAB) or g.found(atlas.DH_MEDALS_TAB_SELECTED)
    return first and second


def open_challenges(g: Game) -> bool:
    """On the event page: make sure its Challenges tab is the one shown."""
    if on_page(g):
        return True
    g.tap(atlas.DH_CHALLENGES_TAB_BUTTON, 800)
    g.wait_still()
    g.move_to(PAGE_PARK)  # hovered, the selected tab reads lighter than its probe
    g.sleep(300)
    return on_page(g)


def green_share(img: np.ndarray) -> float:
    """Share of clearly green pixels (a claimable button); the grey Claim button, the card
    background and the white text have none. A share, not a colour: the button's shade is
    not measured yet (no tier was claimable on 2026-09-25)."""
    if img.size == 0:
        return 0.0
    px = img[:, :, :3].astype(np.int16)
    b, gr, r = px[:, :, 0], px[:, :, 1], px[:, :, 2]
    return float(((gr > 110) & (gr - r > 40) & (gr - b > 40)).mean())


def claimable(g: Game) -> list[int]:
    """Indices (0..7) of the challenge cards whose Claim button is green."""
    out = []
    for i, (probe, _) in enumerate(atlas.DH_CLAIMS):
        rect = (probe.x1, probe.y1, probe.x2, probe.y2)
        if green_share(g.region_image(rect, probe.anchor)) >= CLAIM_GREEN_MIN:
            out.append(i)
    return out


def claim_page(g: Game) -> int:
    """The event page is open: claim every green Claim button, one at a time (a claim can
    reveal the next tier's), read again after each. Returns the number of claims."""
    claimed = 0
    for _ in range(MAX_CLAIMS):
        g.move_to(PAGE_PARK)  # a hovered button is drawn lighter
        g.sleep(300)
        ready = claimable(g)
        if not ready:
            break
        g.tap(atlas.DH_CLAIMS[ready[0]][1], 1000)
        g.wait_still()
        claimed += 1
        if not on_page(g):
            # a reward pop-up over the page: one click on the page's neutral row closes it
            g.tap(PAGE_PARK, 1000)
            g.wait_still()
            if not on_page(g):
                g.save_diagnostic("decorated-heroes-claim.png")
                break
    if claimed:
        g.status(f"Decorated Heroes: {claimed} challenge reward(s) claimed")
    return claimed
