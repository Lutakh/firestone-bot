"""Map missions: a button the bot believes free is never clicked when it shows a gem (three
users' missions completed with gems after a game update, 2026-10-22)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from firestone_bot.features import map_redeem
from firestone_bot.vision import atlas, buttons, gems

# The owner's "Refresh Now" button (2026-10-22): orange, a gem and "120", BGR
PAID_REFRESH = np.load(Path(__file__).parent / "fixtures" / "map-refresh-paid.npy")
GEM = (0x9D, 0x00, 0x9F)  # the measured gem purple 0x9F009D, BGR
ORANGE = (0x10, 0x8C, 0xF5)


def _button(rect, gem: bool) -> np.ndarray:
    x1, y1, x2, y2 = rect
    img = np.zeros((y2 - y1, x2 - x1, 3), np.uint8)
    img[:, :] = ORANGE
    if gem:
        img[20:50, 30:60] = GEM
    return img


class FakeMap:
    """The mission panel with one mission in progress whose speed-up shows orange."""

    def __init__(self, early_gem=False, free_reset=False, refresh=None, dialog_gem=False):
        self.early_gem = early_gem
        self.dialog_gem = dialog_gem  # a gem shows in the dialog after the speed-up click
        self.beats = []
        self.free_reset = free_reset
        self.refresh = refresh
        self.clicks = []
        self.pointer = None
        self.lines = []
        self.diagnostics = []
        self.vars = {}
        self.settings = self
        self.MapReset = "0"

    def get(self, key):
        return "0"

    def flag(self, key):
        return False

    def found(self, probe):
        if probe is atlas.MR_FREE_RESET:
            return self.free_reset
        return probe is atlas.MR_FREE_EARLY  # an orange speed-up, free or paid

    def region_image(self, rect, anchor=None):
        if rect == atlas.MR_REFRESH_RECT and self.refresh is not None:
            return self.refresh
        if rect == atlas.MR_EARLY_RECT:
            return _button(rect, self.early_gem)
        if rect == atlas.MR_GEM_DIALOG_RECT:
            return _button(rect, self.dialog_gem and EARLY in self.clicks)
        return _button(rect, False)

    def move_to(self, p):
        self.pointer = (p.x, p.y)

    def tap(self, p, settle_ms=1500, expect=None):
        self.pointer = (p.x, p.y)
        self.clicks.append(self.pointer)

    def click(self):
        self.clicks.append(self.pointer)

    def status(self, text):
        self.lines.append(text)

    def toast(self, title, text, seconds):
        self.lines.append(f"{title}: {text}")

    def save_diagnostic(self, name):
        self.diagnostics.append(name)

    def heartbeat(self, msg, is_stop=False, important=False):
        self.beats.append((msg, important))

    def wait_still(self, max_ms=1500):
        return True

    def focus(self):
        pass

    def sleep(self, ms):
        pass


EARLY = (atlas.MR_FREE_EARLY_BUTTON.x, atlas.MR_FREE_EARLY_BUTTON.y)
RESET = (atlas.MR_FREE_RESET_BUTTON.x, atlas.MR_FREE_RESET_BUTTON.y)


def test_the_real_refresh_button_shows_its_gem():
    assert gems.gem_share(PAID_REFRESH) > 10 * gems.GEM_SHARE_MAX


def test_a_paid_speed_up_is_never_clicked():
    g = FakeMap(early_gem=True)
    map_redeem._checks(g)
    assert EARLY not in g.clicks
    assert "Mission Check: the speed-up button costs gems, not clicked" in g.lines
    assert g.diagnostics == ["mission-paid-speed-up.png"]


def test_a_free_speed_up_is_still_clicked():
    g = FakeMap(early_gem=False)
    map_redeem._checks(g)
    assert EARLY in g.clicks
    assert not any("costs gems" in x for x in g.lines)


def test_a_paid_refresh_is_never_clicked():
    g = FakeMap(early_gem=True, free_reset=True, refresh=PAID_REFRESH)
    map_redeem.map_redeem(g)
    assert RESET not in g.clicks
    assert "Mission Restart: the refresh button costs gems, not clicked" in g.lines
    assert "mission-paid-refresh.png" in g.diagnostics


def test_a_free_refresh_is_still_clicked():
    g = FakeMap(early_gem=True, free_reset=True, refresh=_button(atlas.MR_REFRESH_RECT, False))
    map_redeem.map_redeem(g)
    assert RESET in g.clicks


def test_a_gem_dialog_after_a_speed_up_is_never_confirmed():
    """Second line of defence: a gem in the dialog that follows the click means the click was
    not free. OK is not tapped, free speed-ups and refreshes stop for the run, and an
    important heartbeat says so."""
    g = FakeMap(dialog_gem=True)
    map_redeem._checks(g)
    ok = (atlas.MR_DIALOG_OK.x, atlas.MR_DIALOG_OK.y)
    assert g.clicks.count(EARLY) == 1 and ok not in g.clicks
    assert not g.vars.get(map_redeem.PAID_OFF) and not g.beats  # once could be the map's purple
    assert "Mission Check: a gem showed after a speed-up click: not confirmed" in g.lines
    map_redeem._checks(g)  # the second time in a row: off for the run
    assert g.clicks.count(EARLY) == 2 and ok not in g.clicks
    assert g.vars[map_redeem.PAID_OFF] == 1
    beat = "Map missions: a gem showed after a speed-up click, nothing confirmed (see the log)"
    assert g.beats == [(beat, True)]
    assert "mission-gem-dialog.png" in g.diagnostics
    assert "mission-after-speed-up.png" in g.diagnostics  # the screen, once a run
    g.dialog_gem = False
    map_redeem._checks(g)  # the next visit of the run: no speed-up click at all
    assert g.clicks.count(EARLY) == 2


# The Mission Rewards dialog after the free speed-up of a World domination mission (owner,
# 2026-10-30 22:56, client 1920x1009, game 9.1.3a): client x 740..1180, y 380..650 at half
# size (game.coarse_image(crop, 2)). Rewards: laurel x2, shield x10, a purple mystery box x2,
# then the green Okay (client 804..1116 x 566..640).
REWARDS = np.load(Path(__file__).parent / "fixtures" / "mission-rewards-mystery-box-913a-half.npy")
PARCHMENT = (127, 163, 202)  # BGR, the dialog's panel


GREEN = (8, 160, 10)  # GREEN_BUTTON, BGR


def _rewards_band(dy=0, rewards_purple=True):
    """MR_GEM_DIALOG_RECT at 1 px per logical px (the reference client): the panel with the
    fixture at its place (client y + 31 = logical), `dy` px lower; without its purple (the
    mystery box) when `rewards_purple` is False."""
    bx, by, bx2, by2 = atlas.MR_GEM_DIALOG_RECT
    band = np.empty((by2 - by, bx2 - bx, 3), np.uint8)
    band[:] = PARCHMENT
    full = np.repeat(np.repeat(REWARDS, 2, axis=0), 2, axis=1)
    top = 411 + dy - by
    band[top : top + full.shape[0], 740 - bx : 740 - bx + full.shape[1]] = full
    if not rewards_purple:
        band[gems.gem_mask(band)] = PARCHMENT
    return band


def _paint(band, x1, y1, x2, y2, colour):
    """Paint a logical rect of the band."""
    bx, by = atlas.MR_GEM_DIALOG_RECT[:2]
    band[y1 - by : y2 - by, x1 - bx : x2 - bx] = colour
    return band


class RewardsMap(FakeMap):
    """A free speed-up followed by the real Mission Rewards dialog."""

    def __init__(self, band, **kw):
        super().__init__(**kw)
        self.band = band

    def region_image(self, rect, anchor=None):
        bx, by, bx2, by2 = atlas.MR_GEM_DIALOG_RECT
        x1, y1, x2, y2 = rect
        inside = bx <= x1 and by <= y1 and x2 <= bx2 and y2 <= by2
        if EARLY in self.clicks and anchor == atlas.ANCHOR_CENTER and inside:
            return self.band[y1 - by : y2 - by, x1 - bx : x2 - bx]
        return super().region_image(rect, anchor)


def test_the_mystery_box_reward_is_no_gem():
    """World domination (2026-10-29/30): the purple reward made 0.3 % of the dialog gem
    purple; the bot closed it unconfirmed and, the second time in a row (the paw mission is
    purple too), turned free speed-ups off for the run with an important heartbeat (owner's
    bot 22:56, report G8N62Y). The Okay is found by its look and holds no gem: tapped."""
    band = _rewards_band()
    assert gems.gem_share(band) > gems.GEM_SHARE_MAX  # the old reading: a gem in the dialog
    g = RewardsMap(band)
    map_redeem._checks(g)  # one speed-up per pass, CHECKS_CAP passes: that many in a row
    assert g.clicks[-1] == (960, 633)  # the centre of the Okay found (MR_DIALOG_OK: 971, 628)
    assert g.clicks.count(EARLY) == g.clicks.count((960, 633)) == map_redeem.CHECKS_CAP
    assert not any("a gem showed" in line for line in g.lines)
    assert not g.vars.get(map_redeem.PAID_OFF) and not g.beats
    assert g.vars[map_redeem.GEM_SEEN] == 0


def _refused(band):
    g = RewardsMap(band)
    map_redeem._checks(g)
    return (
        g.clicks.count(EARLY) == 1
        and g.clicks[-1] == (atlas.MAP_POPUP_CLOSE.x, atlas.MAP_POPUP_CLOSE.y)
        and "Mission Check: a gem showed after a speed-up click: not confirmed" in g.lines
    )


def test_a_price_in_the_okay_row_is_never_tapped():
    """A gem icon in the Okay (523 px, as on the paid Speed up) is a price even when nothing
    else is purple: the old rule (0.002 of the whole dialog) would have tapped it."""
    band = _paint(_rewards_band(rewards_purple=False), 1040, 615, 1063, 638, GEM)
    assert gems.gem_share(band) < gems.GEM_SHARE_MAX
    assert _refused(band)
    assert _refused(_paint(_rewards_band(), 1040, 615, 1063, 638, GEM))  # with the box too


def test_other_dialogs_fall_back_to_the_old_rule():
    """Only the Rewards dialog's own Okay is tapped. A green button under it merges into one
    box too big; a second one beside it is a choice; the generic one-button box puts its OK
    28 px lower. Each falls back to the old rule (a gem anywhere: not confirmed)."""
    rect, centre = atlas.MR_GEM_DIALOG_RECT, atlas.ANCHOR_CENTER
    cases = {
        "under": (_paint(_rewards_band(), 600, 690, 860, 750, GREEN), 1),
        "beside": (_paint(_rewards_band(), 1130, 600, 1350, 660, GREEN), 2),
        "lower": (_rewards_band(dy=28), 1),
    }
    for name, (band, n_boxes) in cases.items():
        g = RewardsMap(band)
        g.clicks.append(EARLY)  # the band is served after the speed-up click
        assert len(buttons.green_boxes(g, rect, anchor=centre)) == n_boxes, name
        assert map_redeem._rewards_dialog(g) == ("unknown", None), name
        assert _refused(band), name


def test_a_paid_map_reset_happens_once_a_visit_whatever_the_safety_cap(tmp_path):
    """MapReset (spend gems on resets, opt-in) looped without end with SafetyCap 0."""
    g = FakeMap(early_gem=True)
    g.map_state_path = str(tmp_path / "MapStartState.ini")
    g.MapReset = "1"
    resets = []
    real_found = g.found

    def found(probe):
        if probe is atlas.MR_RESET_AVAILABLE:
            return True  # shown again after every reset
        return real_found(probe)

    g.found = found
    g.move_to = lambda p: resets.append((p.x, p.y)) if p is atlas.MR_RESET_BUTTON else None
    map_redeem.map_redeem(g)
    assert len(resets) == 1
    assert "MapRedeem: one paid map reset this visit" in g.lines


def test_a_popup_neither_brown_nor_orange_is_closed():
    """The else-branch used to leave the popup open (AHK); the next map points could land on
    its paid Speed up or its Cancel."""
    g = FakeMap()
    g.found = lambda probe: False
    map_redeem._checks(g)
    close = (atlas.MAP_POPUP_CLOSE.x, atlas.MAP_POPUP_CLOSE.y)
    assert g.clicks[-1] == close
    assert g.diagnostics == ["mission-dialog-unknown.png"]


def test_the_in_progress_popup_is_captured_once_a_run():
    """Game 9.1.3a's in-progress popup (red Cancel, paid Speed up) has no 1:1 capture yet."""
    g = FakeMap()
    g.found = lambda probe: probe is atlas.MR_MORE_THAN_3_MIN
    map_redeem._checks(g)
    map_redeem._checks(g)  # the next visit of the run
    close = (atlas.MAP_POPUP_CLOSE.x, atlas.MAP_POPUP_CLOSE.y)
    assert g.clicks.count(close) == 2
    assert g.diagnostics == ["mission-in-progress.png"]
    assert "Mission Check: Mission has more than 3 minutes remaining" in g.lines
