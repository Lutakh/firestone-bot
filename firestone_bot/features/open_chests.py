"""Port of Functions/OpenChests.ahk: OpenChests() and OpenBlessChests().

The AHK code is a ladder of labels with `Goto`s that fall through to the end of each rarity
group; here each group is an ordered table and the setting picks the START index. Unknown
setting values fall into the first label exactly as in AHK (e.g. GearChestExclude="Emerald"
opens every gear chest). The "Nebula and Higher" / "Cosmic and Higher" cases both jumped to
Galaxy in the AHK source, which opened every celestial chest; fixed 2026-09-29 (a user kept
losing the Nebula chests they transmute into Cosmic ones).

One look at the bag (a user's suggestion, 2026-10-28): the AHK way looks for every chest
type in turn, 19 searches and 21 s a visit on the owner's account, where 94% of the visits
open nothing (logs of 2026-10-01..28). The visible slots are now read once, by two reads
that must agree (BagLook). A chest with an icon reference is only tried when a slot holds
it, which is what its own search would have found; a chest without one (Titan, Platinum,
Galaxy, Cosmic, Nebula, Solar, the gifts) is still looked for by its colour, a search of a
few ms, and only gets its status line and pause when it is there. Empty slots after the last
chest (the game packs the chests from the top left) mean the whole list is in view: the
wheel cannot bring another chest into it and is not used. Whatever is doubtful goes the old
way: reads that disagree, the bag's X not on screen, a dry run, and the first visit of a run
then one an hour (FULL_CHECK_MS), so a misread cannot keep a chest in the bag for longer.
"""

from __future__ import annotations

import time

from firestone_bot.features.open_chest_type import open_chest_type
from firestone_bot.features.oracles_gift import mystery_box, oracles_gift
from firestone_bot.game import Game
from firestone_bot.vision import atlas, chest_grid
from firestone_bot.vision.atlas import Probe

FULL_CHECK_MS = 60 * 60 * 1000  # every chest type is tried the old way at least this often
# Game.vars: time.monotonic() ms of the last full check (dropped when a run starts, runner.py)
FULL_CHECK_KEY = "bag_full_check_ms"
LOOK_CAPTURE_KEY = "bag_look_capture"  # Game.vars: bag-look.png saved this run
LOOK_PARK_MS = 300  # pointer off the grid (a hovered icon grows), as before a chest search
LOOK_GAP_MS = 300  # between two reads of the grid, which must agree
LOOK_READS = 3  # reads at most before the visit goes the old way


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class BagLook:
    """What the visible slots of the chest grid hold, row by row from the top left: a chest
    name, chest_grid.EMPTY, or None for a slot no reference matched (a chest without an icon
    reference, or a misread)."""

    def __init__(self, slots: list[str | None]) -> None:
        self.slots = list(slots)

    def holds(self, name: str) -> bool:
        return name in self.slots

    @property
    def end_in_view(self) -> bool:
        """The list ends inside the view, so the wheel cannot bring another chest into it: the
        game packs the chests from the top left and draws empty slots after the last one.
        True when the last slot is empty and so is every slot after the first empty one."""
        if chest_grid.EMPTY not in self.slots:
            return False
        first = self.slots.index(chest_grid.EMPTY)
        return all(s == chest_grid.EMPTY for s in self.slots[first:])

    def summary(self) -> str:
        parts = sorted({s for s in self.slots if s is not None and s != chest_grid.EMPTY})
        unknown = self.slots.count(None)
        empty = self.slots.count(chest_grid.EMPTY)
        if unknown:
            parts.append(f"{unknown} unrecognised")
        if empty:
            parts.append(f"{empty} empty slot{'s' if empty > 1 else ''}")
        return ", ".join(parts) + ("" if self.end_in_view else " (more may be below)")


def take_look(g: Game) -> BagLook | None:
    """Read the visible slots until two reads LOOK_GAP_MS apart agree (a panel still sliding
    in or an icon still drawing reads differently). None when LOOK_READS reads never agree,
    or when the bag's X is not on screen (the grid's rows are placed from it). The pointer is
    parked first: after an opening it rests on the bag's X (close_chest_dialog)."""
    g.move_to(atlas.NS_MODE_PARK)
    g.sleep(LOOK_PARK_MS)
    if not g.found(g.ms.bag_close_x):
        return None
    last = chest_grid.read_slots(g)
    for _ in range(LOOK_READS - 1):
        g.sleep(LOOK_GAP_MS)
        now = chest_grid.read_slots(g)
        if now == last:
            return BagLook(now)
        last = now
    return None


class _Visit:
    """One visit of the bag: the current look, read again once something changed the grid (a
    chest clicked, the wheel). `quick` False: the old way, every chest type is tried."""

    def __init__(self, g: Game, quick: bool) -> None:
        self.g = g
        self.quick = quick
        self._look: BagLook | None = None
        self._said = ""

    def look(self) -> BagLook | None:
        if self.quick and self._look is None:
            g = self.g
            self._look = take_look(g)
            if self._look is None:
                self.quick = False
                g.status("Open Chests: the bag could not be read, every chest is tried")
                if not g.vars.get(LOOK_CAPTURE_KEY):
                    g.vars[LOOK_CAPTURE_KEY] = 1
                    g.save_diagnostic("bag-look.png")
            elif self._look.summary() != self._said:  # one line per new content
                self._said = self._look.summary()
                g.status(f"Open Chests: the bag shows {self._said}")
        return self._look if self.quick else None

    def changed(self) -> None:
        self._look = None

    def may_hold(self, name: str, color: int) -> bool:
        """Whether a chest type is worth a try: always the old way; with an icon reference,
        when a slot holds it; without one, when its colour is in the grid (the search
        open_chest_type makes, here without the status line and pause before it)."""
        look = self.look()
        if look is None:
            return True
        if chest_grid.known(name):
            return look.holds(name)
        g = self.g
        return g.found(Probe(*g.ms.chest_grid, color, 1, f"chest_{color:06X}"))


def _open_group(
    g: Game, group: tuple[tuple[str, int], ...], start: int | None, visit: _Visit | None = None
) -> None:
    if start is None:  # "Exclude All"
        return
    for name, color in group[start:]:
        if visit is not None and not visit.may_hold(name, color):
            continue
        g.toast("Open Chests", f"Opening {name} Chests", 1.5)
        open_chest_type(g, color, 1, name)
        if visit is not None:
            visit.changed()


def _open_gifts(g: Game, visit: _Visit, label: str, opener, color: int, variation: int) -> None:
    """Oracle's gifts or mystery boxes, at the end of the list. With the whole list in view
    the wheel is not used and the gift is only opened when its colour is in the grid; else
    the old way (scroll down, search there)."""
    look = visit.look()
    if look is not None and look.end_in_view:
        if not g.found(Probe(*g.ms.chest_grid, color, variation, f"gift_{color:06X}")):
            return
        g.toast("Open Chests", f"Opening {label}", 1.5)
        opener(g, scroll=False)
    else:
        g.toast("Open Chests", f"Opening {label}", 1.5)
        opener(g)
    visit.changed()


def _open_bag_chests_tab(g: Game) -> None:
    # open bag
    g.open_screen(g.ms.bag_icon, g.ms.bag_close_x, 1000)
    # click chests tab
    g.tap(g.ms.bag_chests_tab, 1000)


def _close_bag(g: Game, after_ms: int) -> None:
    g.tap(g.ms.bag_close, 0)
    g.sleep(after_ms)


def bag_plan(s) -> tuple[bool, bool, bool, bool]:
    """(gear and jewel chests, Oracle's gifts, mystery boxes, celestial chests) to open on
    this visit. AHK opened the gifts and boxes only inside OpenChests; the rework opens
    them whenever their own option is on (the free daily mystery box lands in the bag even
    with "Open chests" off, owner's Discord, 2026-09-08). Celestial chests: with Chests on
    when Bless is on, with Chests off when Bless and BlessingChests are on (AHK)."""
    chests = s.flag("Chests")
    bless = s.flag("Bless") and (chests or s.flag("BlessingChests"))
    return chests, s.flag("OracleGifts"), s.flag("MysteryBoxes"), bless


def _full_check_due(g: Game) -> bool:
    """The old way, every chest type tried: in a dry run (nothing is clicked, the bag on
    screen is not the one of the cycle), on the first visit of a run, then once an hour."""
    if g.dry_run:
        return True
    last = g.vars.get(FULL_CHECK_KEY)
    return last is None or _now_ms() - last >= FULL_CHECK_MS


def open_bag(g: Game) -> None:
    """The bag visit of the main loop: nothing to do = the bag is not opened."""
    chests, gifts, boxes, bless = bag_plan(g.settings)
    if not (chests or gifts or boxes or bless):
        return
    _open_bag_chests_tab(g)
    full = _full_check_due(g)
    counted = False  # the full check is done once it saw the bag
    if full and not g.dry_run:
        g.status("Open Chests: full check, every chest is tried (first visit, then hourly)")
        # a visit whose bag never opened (a pop-up took the click) leaves the check due
        counted = g.found(g.ms.bag_close_x)
    visit = _Visit(g, quick=not full)
    if chests:
        # Gear chests: an unknown value starts at Titan (opens all), like the AHK fall-through.
        _open_group(
            g,
            atlas.GEAR_CHESTS,
            atlas.GEAR_CHEST_START.get(g.settings.GearChestExclude, 0),
            visit,
        )
        # JewelChests:
        _open_group(
            g,
            atlas.JEWEL_CHESTS,
            atlas.JEWEL_CHEST_START.get(g.settings.JewelChestExclude, 0),
            visit,
        )
    # Gifts:
    if gifts:
        _open_gifts(g, visit, "Oracle Gifts", oracles_gift, atlas.ORACLE_GIFT_COLOR, 1)
    if boxes:
        _open_gifts(g, visit, "Mystery Boxes", mystery_box, atlas.MYSTERY_BOX_COLOR, 2)
    if bless:
        open_bless_chests(g, visit)  # closes the bag itself
    # AHK returned WITHOUT closing the bag when Bless was off, and closed it a second time
    # when Bless was on (a click on the Town icon in classic, on the settings gear in the new
    # style). Rework: the bag is closed exactly once, whatever the Bless setting.
    else:
        _close_bag(g, 1500)
    if counted:
        g.vars[FULL_CHECK_KEY] = _now_ms()


def open_chests(g: Game) -> None:
    """AHK OpenChests(): kept as a name, the bag visit is open_bag."""
    open_bag(g)


def open_bless_chests(g: Game, visit: _Visit | None = None) -> None:
    """Celestial (blessing) chests, the bag already open on its Chests tab (open_bag)."""
    look = visit.look() if visit is not None else None
    if look is None or not look.end_in_view:
        # OpenBlessChestsNoBag:
        g.move_to(atlas.BAG_SCROLL_HOVER)
        g.toast("Open Chests", "Scrolling to ensure bottom gifts are visible", 1.5)
        g.wheel(-5)
        if visit is not None:
            visit.changed()
    start = atlas.CELESTIAL_CHEST_START.get(g.settings.CelestialChestExclude, 0)
    _open_group(g, atlas.CELESTIAL_CHESTS, start, visit)
    # CloseBag:
    _close_bag(g, 1000)
