"""Decorated Heroes event (calendar event, two weeks in odd months; owner request 2026-09-25).

One switch, EventDecoratedHeroes, makes the bot complete the event's eight daily challenges
and claim their stars:
- tavern plays and crystal hits: the daily limits are raised to 12 and 15 (daily.py);
- "Enlighten guardians 3 times": three enlightenments a day on the guardian screen (below);
- researches, alchemy experiments, guild expeditions, scout missions and time online: done by
  the bot's usual actions;
- the stars of every tier reached are claimed on the event's own page (claim_page), opened
  from the events list by claim_events.

Measured on the owner's game (2026-09-25, 1920x1009): the event page has Challenges /
Medals / Stars exchange / Skins / Market tabs and eight challenge cards, each with a Claim
button that is grey until a tier is reached; the guardian screen's "Enlightenment N" button
sits right of Train (20 strange dust per enlightenment at x1) and follows the screen's own
multiplier (x20 -> x1 -> x5 -> x10 -> x20).
"""

from __future__ import annotations

import numpy as np

from firestone_bot import daily
from firestone_bot.features import multiplier, token_counter
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


# -- guardian screen: enlightenments -----------------------------------------------------------

ENLIGHTEN_TAKEN_MS = 15000  # the counter drops at once (live); patience for a slow server
ENLIGHTEN_X1_MAX_DUST = 40  # one enlightenment at x1 costs 20; x5 would take 100
MULTIPLIER_CYCLE = (20, 1, 5, 10)  # what the label reads after each click, round and round
MAX_MULTIPLIER_STEPS = len(MULTIPLIER_CYCLE)
MAX_UNCONFIRMED = 2  # clicks the dust counter never showed, per game day, before giving up


def train_position(g: Game) -> int:
    """Roster position (1..4) of the guardian the user trains (GuardianTrain; the legacy
    value "Vermilion" is the first guardian)."""
    value = g.settings.get("GuardianTrain").strip()
    return int(value) if value in ("1", "2", "3", "4") else 1


def _multiplier(g: Game) -> int | None:
    g.move_to(atlas.GUARDIAN_MULTIPLIER_PARK)
    g.sleep(300)
    return multiplier.read_multiplier(g, atlas.GUARDIAN_MULTIPLIER_LABEL, None)


def _step_multiplier_to(g: Game, target: int) -> int | None:
    """Click the guardian screen's multiplier until it reads `target`; the value read last,
    None when a read does not follow the known cycle (a label read wrong: "x10" cut to
    "x1" must never pass for x1)."""
    value = _multiplier(g)
    steps = 0
    while value is not None and value != target and steps < MAX_MULTIPLIER_STEPS:
        if value not in MULTIPLIER_CYCLE:
            return None
        expected = MULTIPLIER_CYCLE[(MULTIPLIER_CYCLE.index(value) + 1) % MAX_MULTIPLIER_STEPS]
        g.tap(atlas.GUARDIAN_MULTIPLIER, 600)
        value = _multiplier(g)
        steps += 1
        if value != expected:
            return None
    return value


def _unconfirmed_key(g: Game) -> str:
    return f"enlighten_unconfirmed:{g.settings.get('LastTokenReset')}"


def enlighten(g: Game) -> int:
    """Guardian screen open on its first tab: enlighten the trained guardian until today's
    three are done, one at a time at x1 (20 strange dust each), each counted only when the
    strange dust counter drops. The user's multiplier is put back afterwards. Returns the
    number of enlightenments made."""
    left = daily.enlighten_left(g.settings)
    if not left or g.vars.get(_unconfirmed_key(g), 0) >= MAX_UNCONFIRMED:
        return 0
    g.wait_still()  # the training animation may still be playing
    g.tap(atlas.GUARDIAN_ROSTER[train_position(g) - 1][1])
    g.wait_still()
    before_mult = _multiplier(g)
    if before_mult is None:
        g.status("Decorated Heroes: the guardian multiplier is not readable, no enlightenment")
        g.save_diagnostic("enlighten-multiplier.png")
        return 0
    if _step_multiplier_to(g, 1) != 1:
        g.status("Decorated Heroes: the guardian multiplier did not go back to x1")
        g.save_diagnostic("enlighten-multiplier.png")
        _step_multiplier_to(g, before_mult)
        return 0
    made = 0
    while made < left:
        g.move_to(atlas.GUARDIAN_CHAOS_PARK)  # hovered, the green button reads lighter
        g.sleep(300)
        if not g.found(atlas.GUARDIAN_ENLIGHTEN_READY):
            g.status("Decorated Heroes: the Enlightenment button is not green (strange dust?)")
            break
        dust = token_counter.read_stable(g, atlas.GUARDIAN_DUST_DIGITS)
        g.tap(atlas.GUARDIAN_ENLIGHTEN, 0)
        g.sleep(300)
        g.move_to(atlas.GUARDIAN_CHAOS_PARK)
        spent = 20  # counter unreadable: the click is counted as made
        if dust is not None:
            after = token_counter.wait_drop(g, atlas.GUARDIAN_DUST_DIGITS, dust, ENLIGHTEN_TAKEN_MS)
            if after is None:
                # not counted (another cycle tries again), but a click the counter never
                # shows must not turn into one paid enlightenment per cycle all day long
                key = _unconfirmed_key(g)
                g.vars[key] = g.vars.get(key, 0) + 1
                g.status("Decorated Heroes: the enlightenment spent no strange dust, not counted")
                g.save_diagnostic("enlighten-not-taken.png")
                break
            spent = dust - after
        else:
            g.sleep(1000)
        if spent > ENLIGHTEN_X1_MAX_DUST:
            # the multiplier was not x1 although it read so: the click did several at once
            g.status(
                f"Decorated Heroes: one enlightenment took {spent} strange dust, the multiplier "
                "is not x1: no more enlightenments today"
            )
            g.save_diagnostic("enlighten-multiplier.png")
            for _ in range(daily.enlighten_left(g.settings)):
                daily.note_enlighten(g.settings)
            made += 1
            break
        daily.note_enlighten(g.settings)
        made += 1
        g.status(
            f"Decorated Heroes: guardian {train_position(g)} enlightened "
            f"({g.settings.EnlightenCountDaily}/{daily.EVENT_ENLIGHTENMENTS} today)"
        )
    if before_mult != 1:
        _step_multiplier_to(g, before_mult)  # the user's own choice (the owner uses x20)
    return made
