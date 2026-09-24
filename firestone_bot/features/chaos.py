"""Chaos rift from the guild screen (Python rework of subFunctions/Chaos.ahk).

The AHK bot switched the rift to Auto, which spends every available token, including the
paid ones (orange medallion, second counter top right). The rework only hits while the icon
shown inside the green "Hit" button is the FREE token (blue moon, first counter, 10 per day,
refilled about an hour after the daily reset), and stops after MaxChaos hits per game day
(ChaosCountDaily, cleared by the daily reset). The Auto/Manual toggle is never touched.

A hit starts a 3-4 minute battle animation during which the button is grey, but leaving the
rift and reopening it resolves the battle at once (measured 2026-09-04), so the loop closes
and reopens the rift between hits instead of waiting.

A hit is counted from the free moonstone counter: only a click that makes it drop counts
(a drop seen after the reopen still counts, late). With MaxChaos at 10 or more, the day
ends with the counter at 0: moonstones the counter still shows at the limit are used too.
"""

from __future__ import annotations

import time

from firestone_bot import daily
from firestone_bot.features import multiplier, token_counter
from firestone_bot.features.big_close import big_close
from firestone_bot.features.chaos_books import buy_books
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def _hit_button_token(g: Game) -> str:
    """'free', 'paid' or 'none' depending on the token icon in the Hit button."""
    if g.found(atlas.CHAOS_HIT_ICON_FREE):
        return "free"
    if g.found(atlas.CHAOS_HIT_ICON_PAID):
        return "paid"
    return "none"


def _wait_hit_ready(g: Game, timeout_ms: int = atlas.CHAOS_HIT_WAIT_MS) -> bool:
    """Wait for the green Hit button: right after a hit it is grey for a few seconds."""
    end = time.monotonic() + timeout_ms / 1000
    while True:
        if g.found(atlas.CHAOS_HIT_READY):
            return True
        if time.monotonic() >= end:
            return False
        g.sleep(500)


HIT_TAKEN_MS = 8000  # the counter drops as soon as the battle starts; patience for a slow server
BUTTON_GREY_MS = 4000  # counter unreadable: the green button greys within a second
HIT_RELEASE_MS = 300  # let Unity take the click before the pointer leaves the button
PARK_SETTLE_MS = 300  # a hovered button is lighter: let it fade back before reading it
MAX_MISSED_CLICKS = 3  # clicks that spent nothing in one visit before leaving
MAX_UNSHOWN_BATTLES = 2  # battles the counter never showed before it is no longer trusted
FREE_PER_DAY = 10  # free moonstones the game gives each day
RECONCILE_READS = 3  # tries to read the counter once the day's limit is reached
COUNTER_OFF = "chaos_counter_off"  # Game.vars: the counter read wrong, fall back for the session
SCREEN = "Chaos rift"


def _free_tokens(g: Game) -> int | None:
    """The free moonstone counter (top bar), None when unreadable or disabled."""
    if g.vars.get(COUNTER_OFF):
        return None
    return token_counter.read_stable(g, atlas.CHAOS_FREE_COUNTER)


def _hit_taken(g: Game, before: int | None) -> tuple[int, bool]:
    """(free moonstones the click spent, whether a battle started).

    With the counter read before the click, the hit counts only once the counter reads
    lower; when it does not, the Hit button (read with the pointer parked) tells whether a
    battle started all the same. Without the counter, a grey button is the hit. The old
    check read the button with the pointer still on it, lighter when hovered, so the probe
    missed at once and every click counted (10 counted with one free moonstone left, users
    on Steam and Epic, 2026-09-24)."""
    g.sleep(HIT_RELEASE_MS)
    g.move_to(atlas.SPEND_PARK)
    if before is not None:
        after = token_counter.wait_drop(g, atlas.CHAOS_FREE_COUNTER, before, HIT_TAKEN_MS)
        if after is not None:
            return before - after, True
        g.sleep(PARK_SETTLE_MS)
        return 0, not g.found(atlas.CHAOS_HIT_READY)
    g.sleep(PARK_SETTLE_MS)
    greyed = g.wait_gone(atlas.CHAOS_HIT_READY, BUTTON_GREY_MS)
    return (1 if greyed else 0), greyed


def _wants_every_free(g: Game) -> bool:
    """MaxChaos asks for all the free moonstones of the day (or more)."""
    try:
        return int(g.settings.get("MaxChaos")) >= FREE_PER_DAY
    except (KeyError, ValueError):
        return False


def _reconcile(g: Game, last_seen: int | None) -> bool:
    """The daily limit is reached: when MaxChaos asks for every free moonstone and the
    counter still shows some, count down to what the game shows so they are used too. A
    hit counted wrongly, or a moonstone left from the day before and hit before the new
    ones arrived (about an hour after the reset), left one unused every day."""
    if not _wants_every_free(g):
        return False
    free = None
    for attempt in range(RECONCILE_READS):
        free = _free_tokens(g)
        if free is not None or g.vars.get(COUNTER_OFF):
            break
        if attempt + 1 < RECONCILE_READS:
            g.sleep(400)
    if free is not None and last_seen is not None:
        free = min(free, last_seen)  # a reopened rift can show the count before the last hit
    if not free:
        return False
    limit = int(g.settings.get("MaxChaos"))
    g.status(
        f"Chaos rift: {limit} hits counted today but {free} free moonstone(s) left, using them"
    )
    g.settings.set("ChaosCountDaily", max(0, limit - free))
    g.settings.save()
    return True


def _count_hits(g: Game, n: int) -> None:
    for _ in range(n):
        daily.note_chaos_hit(g.settings)


def _multi_spend(g: Game, n: int) -> None:
    g.status(
        f"Chaos rift: one click spent {n} free moonstones, the spend multiplier is not x1: "
        "no more hits until it reads x1"
    )
    g.save_diagnostic("chaos-multiplier.png")
    multiplier.note_multi_spend(g, SCREEN)


def _open_rift(g: Game) -> None:
    g.click_point(atlas.CHAOS_OPEN)  # MouseClick, Left, x, y, 1, 0
    g.sleep(2000)


def hit_chaos(g: Game) -> None:
    # After the day's hits the rift is opened again only when it shows its dot: with
    # MaxChaos asking for every free moonstone, a moonstone still left is then used.
    need_hits = daily.chaos_left(g.settings) != 0 or (
        _wants_every_free(g) and not g.vars.get(COUNTER_OFF)
    )
    # The books are looked at on every visit: the runes come from the hits of the day, so a
    # shop that had nothing at the first cycle has something later (owner, 2026-09-09).
    need_books = g.settings.flag("ChaosBooks")
    if not (need_hits or need_books):
        return  # nothing left for today: the rift is not opened again until the reset
    g.focus()
    # Check for Chaos notification on guild screen
    if not g.found(atlas.CHAOS_DOT):
        return
    _open_rift(g)
    hits = 0
    missed = 0
    reconciled = False
    last_seen: int | None = None  # the counter after the last hit (a reopened rift can lag)
    missed_at: int | None = None  # the counter before a click that spent nothing
    missed_grey = False  # ...and whether that click started a battle all the same
    unshown = 0  # battles started that the counter never showed, even after a reopen
    if need_hits and not multiplier.ensure_single(g, SCREEN):
        need_hits = False
    if need_hits and multiplier.spend_blocked(g, SCREEN):
        need_hits = False
    while need_hits:
        if missed_at is not None:
            # A click spent nothing: the rift was reopened, read the counter again before
            # anything else (the last free moonstone taken late leaves a paid icon in the
            # button, and the checks below would end the visit with that hit uncounted).
            now = _free_tokens(g)
            if now is not None and last_seen is not None:
                now = min(now, last_seen)
            if now is not None and now < missed_at:
                n = missed_at - now
                missed_at, missed_grey, last_seen = None, False, now
                missed = max(0, missed - 1)
                _count_hits(g, n)
                hits += n
                g.status(
                    f"Chaos rift: hit {hits} confirmed late ({g.settings.ChaosCountDaily} today)"
                )
                if n > 1:
                    _multi_spend(g, n)
                    break
                continue
            if missed_grey and now is not None:
                unshown += 1
            missed_at, missed_grey = None, False
            if unshown >= MAX_UNSHOWN_BATTLES:
                # battles start but the counter never moves: this is not the free moonstone
                # counter on this client (another window shape). Those battles were hits.
                g.status(
                    f"Chaos rift: {unshown} hits the free moonstone counter never showed, "
                    "counting them and reading the Hit button from now on"
                )
                g.save_diagnostic("chaos-counter-unshown.png")
                g.vars[COUNTER_OFF] = 1
                _count_hits(g, unshown)
                hits += unshown
                missed = max(0, missed - unshown)
                unshown = 0
                continue  # the limit is checked again before any click
        left = daily.chaos_left(g.settings)
        if left == 0:
            if not reconciled:
                reconciled = True
                if _reconcile(g, last_seen):
                    continue
            g.status(f"Chaos rift: daily limit reached ({g.settings.MaxChaos}), leaving")
            break
        if not _wait_hit_ready(g):
            if _hit_button_token(g) != "free":
                g.status("Chaos rift: Hit button not ready, leaving")
                break
            # A free token is loaded in the button but it never turns green: reopen the rift
            # (which is what resolves a battle) and give it one more wait before blaming the
            # game, so the animation of a hit just made is never taken for the bug.
            g.status("Chaos rift: Hit button still grey, reopening the rift")
            big_close(g)
            _open_rift(g)
            if _wait_hit_ready(g):
                continue
            if _hit_button_token(g) == "free":
                g.status(
                    "Chaos rift: a free token is loaded but the Hit button stays grey; this is "
                    "the game bug that needs a restart"
                )
                g.save_diagnostic("chaos-hit-stuck.png")
                g.vars["restart_requested"] = (
                    "the chaos rift Hit button stayed grey with a free token loaded"
                )
            break
        token = _hit_button_token(g)
        if token != "free":
            g.status(f"Chaos rift: no free token in the Hit button ({token}), leaving")
            break
        before = _free_tokens(g)
        if before is not None and last_seen is not None:
            before = min(before, last_seen)
        if missed >= MAX_MISSED_CLICKS:
            g.status(f"Chaos rift: {missed} clicks on Hit spent nothing, leaving")
            g.save_diagnostic("chaos-hit-not-taken.png")
            break
        if before == 0:
            g.status("Chaos rift: the free moonstone counter reads 0, leaving")
            break
        g.tap(atlas.CHAOS_HIT, 0)
        spent, greyed = _hit_taken(g, before)
        if not spent:
            missed += 1
            missed_at, missed_grey = before, greyed
            g.status("Chaos rift: the click on Hit spent no free moonstone, not counted")
            big_close(g)
            _open_rift(g)  # the next pass reads the counter again: a late drop still counts
            continue
        missed_at, missed_grey = None, False
        last_seen = None if before is None else before - spent
        _count_hits(g, spent)
        hits += spent
        g.status(f"Chaos rift: hit {hits} ({g.settings.ChaosCountDaily} today)")
        if spent > 1:
            _multi_spend(g, spent)
            break
        # leave and come back: the battle resolves and the button is green again
        big_close(g)
        _open_rift(g)
    if need_books and buy_books(g):
        # after the hits: buy what the rift shop offers (checked at every cycle)
        daily.note_books_done(g.settings)
    big_close(g)
    if hits:
        g.vars["chaos_hits"] = g.vars.get("chaos_hits", 0) + hits  # runner: guardian upgrades
