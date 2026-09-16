"""Spend multiplier of the token screens: x1 and Manual before the bot spends anything.

The tavern game, the scarab game, the arcane crystal and the chaos rift share a blue "x1"
button (a click steps it to x5, x10... and the game remembers it) and a "Manual" / "Auto"
toggle in the bottom-right corner. With x5 left by the player, each click of the bot spent
five tokens: ten hits meant fifty tokens (Tripl, 2026-09-16). Before its first click on such
a screen the bot reads both labels and steps them back to x1 and Manual; when it cannot read
or restore them it spends nothing on that screen.
"""

from __future__ import annotations

import numpy as np

from firestone_bot.game import Game
from firestone_bot.vision import atlas, digits

MAX_STEPS = 8  # clicks on the multiplier to come back round to x1
MIN_LABEL_WIDTH = 20  # logical px: below it there is no label (no button on this screen)


def _label(g: Game, rect) -> np.ndarray:
    return g.region_image(rect, atlas.ANCHOR_BOTTOM_RIGHT)


def _bright_width(g: Game, img_bgr: np.ndarray) -> int:
    cols = np.nonzero(digits.bright_mask(img_bgr).any(axis=0))[0]
    if not len(cols):
        return 0
    return round((cols.max() - cols.min() + 1) / max(g._viewport().rel_scale, 0.1))


def read_multiplier(g: Game) -> int | None:
    """The number of the "xN" label, None when there is no readable label. The "x" is a
    glyph the digit reader cannot name: it is skipped and the digits after it are read."""
    img = _label(g, atlas.SPEND_MULTIPLIER_LABEL)
    if _bright_width(g, img) < MIN_LABEL_WIDTH:
        return None
    reader = g.digit_reader()
    text = ""
    for glyph in digits.digit_glyphs(digits.segment(img)):
        digit, score = reader.classify(glyph.cell)
        if score < digits.MIN_SCORE:
            if text:
                return None  # an unreadable glyph after the digits started: not a number
            continue  # the leading "x"
        text += digit
    return int(text) if text else None


def mode_is_manual(g: Game) -> bool | None:
    """True for "Manual", False for "Auto", None when there is no label."""
    width = _bright_width(g, _label(g, atlas.SPEND_MODE_LABEL))
    if width < MIN_LABEL_WIDTH:
        return None
    return width >= atlas.SPEND_MANUAL_MIN_WIDTH


def ensure_single(g: Game, screen: str) -> bool:
    """Put the screen on x1 / Manual. True when the bot may spend, False when it must not
    (a label it could not bring back to x1 / Manual); a screen without the pair passes."""
    g.move_to(atlas.SPEND_PARK)
    g.sleep(300)
    value = read_multiplier(g)
    if value is None:
        g.status(f"{screen}: no spend multiplier read on this screen, going on as before")
        g.save_diagnostic("spend-multiplier-unread.png")
        return True
    steps = 0
    while value != 1 and steps < MAX_STEPS:
        g.status(f"{screen}: spend multiplier is x{value}, setting it back to x1")
        g.tap(atlas.SPEND_MULTIPLIER, 600)
        g.move_to(atlas.SPEND_PARK)
        g.sleep(400)
        value = read_multiplier(g)
        steps += 1
    if value != 1:
        g.status(f"{screen}: the spend multiplier could not be set back to x1, nothing spent")
        g.save_diagnostic("spend-multiplier-stuck.png")
        return False
    manual = mode_is_manual(g)
    if manual is False:
        g.status(f"{screen}: spend mode is Auto, setting it back to Manual")
        g.tap(atlas.SPEND_MODE, 600)
        g.move_to(atlas.SPEND_PARK)
        g.sleep(400)
        if mode_is_manual(g) is False:
            g.status(f"{screen}: the spend mode stays on Auto, nothing spent")
            g.save_diagnostic("spend-mode-stuck.png")
            return False
    return True
