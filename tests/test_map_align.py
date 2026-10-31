"""World-map alignment: landmark search, the map's scale, the map found again after a search
beyond its edge left it dragged down, and the bundled reference file."""

import json
import os

import numpy as np
import pytest

from firestone_bot.features import map_align
from firestone_bot.platform import capture
from firestone_bot.vision import atlas


def test_landmark_reference_is_bundled_and_consistent():
    with open(map_align.LANDMARK_PATH, encoding="utf-8") as f:
        d = json.load(f)
    refs = d.get("refs", [d])
    for r in refs:
        assert len(r["gray"]) == r["w"] * r["h"]
        assert r["rect"][2] > r["rect"][0] and r["rect"][3] > r["rect"][1]
    assert all(isinstance(r["gray"], np.ndarray) for r in map_align.load_landmark())


def test_best_match_finds_the_shift():
    rng = np.random.default_rng(1)
    scene = rng.random((80, 120)) * 255
    ref = scene[30:50, 40:70].copy()
    c, dx, dy = map_align.best_match(scene, ref)
    assert (dx, dy) == (40, 30) and c > 0.99


def test_data_files_are_listed_for_pyinstaller():
    root = os.path.join(os.path.dirname(map_align.LANDMARK_PATH), "..", "..")
    with open(os.path.join(root, "firestone-bot.spec"), encoding="utf-8") as f:
        assert 'collect_data_files("firestone_bot")' in f.read()


class _Game:
    """align_map's view of the game: the landmark offsets it reads, the drags it makes."""

    def __init__(self, offsets, client=(1920, 1080)):
        from firestone_bot.platform.window import Rect
        from firestone_bot.vision.viewport import Viewport

        self.offsets = list(offsets)
        self.vp = Viewport(Rect(0, 0, *client))
        self.vars = {}
        self.drags = []
        self.lines = []
        self.map_open = True  # the map's own X shows (DIALOG_CLOSE_X)

    def _viewport(self):
        return self.vp

    def found(self, probe, variation=None):
        return probe is atlas.DIALOG_CLOSE_X and self.map_open

    def status(self, text):
        self.lines.append(text)

    def drag(self, x1, y1, x2, y2, anchor=None):
        self.drags.append((x2 - x1, y2 - y1))

    def sleep(self, ms):
        pass

    def save_diagnostic(self, name):
        self.lines.append(name)


def _align(monkeypatch, g, scores=None):
    """align_map with the landmark read from `g.offsets`, each reference scoring `scores`."""

    def offset(game, landmark, out=None):
        if out is not None:
            out.update(scores or {})
        return game.offsets.pop(0)

    monkeypatch.setattr(map_align, "zoom_knob_x", lambda game: None)
    monkeypatch.setattr(map_align, "load_landmark", list)
    monkeypatch.setattr(map_align, "landmark_offset", offset)
    return map_align.align_map(g)


def test_an_offset_too_short_to_drag_is_left_alone(monkeypatch):
    """Report ANHNX9 (1920x1080, 2026-10-25): the map sat (-4, -8) off, the 9.6 px drag was
    ignored by the game and the alignment was given up for the whole run."""
    g = _Game([(0.79, -4, -8)])
    assert _align(monkeypatch, g) is True
    assert g.drags == [] and not g.vars.get("map_align_off")


def test_a_real_offset_is_still_dragged_back(monkeypatch):
    g = _Game([(0.9, -30, 12), (0.9, 0, 0)], client=(1920, 1009))
    assert _align(monkeypatch, g) is True
    assert g.drags == [(30, -12)]


def test_a_map_in_place_is_left_alone_quietly(monkeypatch):
    g = _Game([(0.97, 0, 0)], client=(1920, 1009))
    assert _align(monkeypatch, g) is True
    assert g.drags == [] and g.lines == []


def test_once_given_up_the_alignment_leaves_the_map_alone(monkeypatch):
    """A drag that does not move the landmark turns the alignment off for the run (the
    reference is off for that client, a user 2026-09-08): the later visits drag nothing (the
    landmark is still read, for the map's scale)."""
    g = _Game([(0.9, 30, 0), (0.9, 30, 0)], client=(1920, 1009))
    assert _align(monkeypatch, g) is False
    assert g.drags == [(-30, 0)] and g.vars["map_align_off"]
    assert "map-align-stuck.png" in g.lines
    g.offsets = [(0.95, 30, 0)]
    assert _align(monkeypatch, g) is False
    assert g.drags == [(-30, 0)] and g.offsets == []


FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _scores(name):
    """Each reference's correlation in a landmark search area (map_align._gray_logical's grey
    image at the references' scale, near search, from a capture of the map)."""
    big = np.load(os.path.join(FIX, f"{name}.npy")).astype(float)
    return {r["name"]: map_align.best_match(big, r["gray"])[0] for r in map_align.load_landmark()}


def test_the_landmark_tells_a_fitted_map():
    """Report ANHNX9 (game started fullscreen at 1920x1080): the map is drawn at the reference
    client's pixel scale, 1009/1080 of the canvas's; the Mac reference matches it."""
    scores = _scores("map-landmark-area-1920x1080-fitted")
    assert scores["mac-original"] > 0.7 and scores["win32-1920x1009"] < 0.4
    assert map_align.map_scale(scores) == map_align.FITTED_SCALE


def test_the_landmark_tells_a_canvas_scaled_map():
    """The owner's 1920x1009 client (2026-10-27): the Windows reference wins, scale 1."""
    scores = _scores("map-landmark-area-1920x1009")
    assert scores["win32-1920x1009"] > 0.85 and scores["mac-original"] < 0.3
    assert map_align.map_scale(scores) == 1.0


def test_an_unclear_landmark_decides_nothing():
    assert map_align.map_scale({"mac-original": 0.30, "win32-1920x1009": 0.10}) is None
    assert map_align.map_scale({"mac-original": 0.55, "win32-1920x1009": 0.45}) is None
    assert map_align.map_scale({}) is None
    assert map_align.map_scale({"mac-original": 0.2, "win32-1920x1009": 0.9}) == 1.0


@pytest.mark.parametrize(
    ("name", "ref", "offset", "scale"),
    [
        # report ANHNX9, the game started fullscreen at 1920x1080: the map fitted to the
        # width, 1009/1080 of a canvas-scaled one, and the landmark (-4, -8) off
        ("map-landmark-area-1920x1080-fitted", "mac-original", (-4, -8), map_align.FITTED_SCALE),
        # the owner's 1920x1009 client (2026-10-27): a canvas-scaled map, in place
        ("map-landmark-area-1920x1009", "win32-1920x1009", (0, 0), 1.0),
    ],
)
def test_landmark_offset_finds_and_scores_every_reference(monkeypatch, name, ref, offset, scale):
    """The game sizes the map when it starts: each size has its own reference (the other one
    does not match it), found where MEASUREMENTS (2026-10-28) has it, and the scores come
    from landmark_offset itself (near search on the fixture areas: map_align._gray_logical's
    grey image at the references' scale, cut from captures of the map)."""
    big = np.load(os.path.join(FIX, f"{name}.npy")).astype(float)
    landmark = map_align.load_landmark()
    monkeypatch.setattr(map_align, "_gray_logical", lambda g, rect, s: big)
    scores = {}
    c, dx, dy = map_align.landmark_offset(None, landmark, scores)
    assert set(scores) == {r["name"] for r in landmark} and c == max(scores.values())
    assert scores[ref] == c > 0.75 and (dx, dy) == offset
    assert all(v < map_align.MIN_CORRELATION for other, v in scores.items() if other != ref)
    assert map_align.map_scale(scores) == scale


def test_an_unclear_read_keeps_the_scale_measured_before(monkeypatch):
    """Review 2026-10-28: the map dragged 40 px off under the missions panel read mac 0.376
    against 0.303; the fitted scale of the visits before stays."""
    g = _Game([(0.376, -40, 0), (0.79, -4, -8)])
    g.vars[map_align.SCALE_KEY] = map_align.FITTED_SCALE
    _align(monkeypatch, g, {"mac-original": 0.376, "win32-1920x1009": 0.303})
    assert g.vars[map_align.SCALE_KEY] == map_align.FITTED_SCALE and g.lines[-1].startswith(
        "Map: moved by"
    )


def test_the_scale_is_measured_while_the_alignment_is_off(monkeypatch):
    """A relaunched game may start at another size: the scale is read even once the
    alignment was given up for the run."""
    g = _Game([(0.95, 30, 0)], client=(1920, 1009))
    g.vars["map_align_off"] = True
    g.vars[map_align.SCALE_KEY] = map_align.FITTED_SCALE
    assert _align(monkeypatch, g, {"mac-original": 0.22, "win32-1920x1009": 0.95}) is False
    assert g.vars[map_align.SCALE_KEY] == 1.0 and g.drags == []


def test_a_short_offset_is_measured_in_screen_px(monkeypatch):
    """960x540 (half the canvas): 18 logical px are 9.6 screen px, 20 are 10.7."""
    g = _Game([(0.9, 0, 18)], client=(960, 540))
    assert _align(monkeypatch, g) is True and g.drags == []
    g = _Game([(0.9, 0, 20), (0.9, 0, 0)], client=(960, 540))
    assert _align(monkeypatch, g) is True and g.drags == [(0, -20)]


def test_the_scale_is_kept_for_the_missions_and_said_once(monkeypatch):
    fitted = {"mac-original": 0.79, "win32-1920x1009": 0.33}
    g = _Game([(0.79, -4, -8)])
    _align(monkeypatch, g, fitted)
    assert g.vars[map_align.SCALE_KEY] == map_align.FITTED_SCALE
    assert sum("of the reference scale" in s for s in g.lines) == 1
    g.offsets = [(0.79, -4, -8)]
    _align(monkeypatch, g, fitted)
    assert sum("of the reference scale" in s for s in g.lines) == 1
    # a popup over the landmark: nothing measured, the scale stays (the map dragged up to
    # look for it, then back)
    g.offsets = [(0.1, 0, 0), (0.1, 0, 0)]
    assert _align(monkeypatch, g, {"mac-original": 0.1}) is False
    assert g.vars[map_align.SCALE_KEY] == map_align.FITTED_SCALE


def test_the_reference_client_says_nothing_about_the_scale(monkeypatch):
    g = _Game([(0.97, 0, 0)], client=(1920, 1009))
    _align(monkeypatch, g, {"mac-original": 0.22, "win32-1920x1009": 0.97})
    assert g.vars[map_align.SCALE_KEY] == 1.0 and g.lines == []


# --- the scale the map is drawn at: the labels' size and the switch to the fixed points ----
@pytest.mark.parametrize(
    ("client", "scale", "drawn"),
    [
        ((1920, 1009), None, 1.0),  # the reference client, before any measure
        ((1920, 1009), 1.0, 1.0),  # the owner's: canvas-scaled
        ((1920, 1080), map_align.FITTED_SCALE, 1.0),  # report ANHNX9: fitted at 16:9
        ((1920, 1080), 1.0, 1.070),  # canvas-scaled at 16:9 (a window maximised later)
        ((2560, 1080), 1.0, 1.070),  # 21:9: 1.386 by the detection area's stretched width
        ((1366, 768), map_align.FITTED_SCALE, 0.711),  # a game started at 1366x768
        ((1366, 768), 1.0, 0.761),  # the owner's window resized to 1366x768
        ((1280, 720), 1.0, 0.714),  # the same at 1280x720 (MEASUREMENTS 4.6)
        ((1280, 720), map_align.FITTED_SCALE, 0.667),  # a game started at 1280x720
    ],
)
def test_the_scale_the_map_is_drawn_at(client, scale, drawn):
    """The client's canvas scale against the reference times the map's logical scale the
    landmark measured (the client's alone before the first measure): exactly 1.0 on the
    reference client (the owner's detection unchanged) and on a map fitted at 1920x1080."""
    g = _Game([], client=client)
    if scale is not None:
        g.vars[map_align.SCALE_KEY] = scale
    assert map_align.drawn_scale(g) == drawn


# --- a map left dragged down by a search beyond its edge (review of 8558a26, F2) ------------
SCROLL = atlas.MAP_DETECT_SCROLL


def test_a_map_left_down_is_dragged_up_and_aligned(monkeypatch):
    """The landmark under the bottom HUD (a search beyond the north edge cut short before its
    drag back): the map is dragged up by the search's drag and the landmark found in place."""
    g = _Game([(0.24, 0, 0), (0.95, 0, 0)], client=(1920, 1009))
    assert _align(monkeypatch, g) is True
    assert g.drags == [(0, -SCROLL)] and map_align.RECOVERY_OFF not in g.vars
    assert g.lines[0].startswith("Map: landmark not found (correlation 0.24), dragging the map up")


def test_the_drag_up_on_a_map_in_place_is_dragged_back(monkeypatch):
    """The landmark missed with the map in place (something over it for one read): the drag
    up finds it that much higher, within the wide search, and the alignment drags it back."""
    g = _Game([(0.24, 0, 0), (0.9, 0, -SCROLL), (0.95, 0, 0)], client=(1920, 1009))
    assert _align(monkeypatch, g) is True
    assert g.drags == [(0, -SCROLL), (0, SCROLL)]


def test_a_landmark_still_not_found_is_left_and_not_looked_for_again(monkeypatch):
    """A popup or a panel over the title: the drag up is undone, the map left as is, and the
    next alignments of the run do not drag (a client no reference matches would bounce the
    map at every alignment) until a search beyond the edge may have left the map down."""
    g = _Game([(0.1, 30, 0), (0.12, 0, 0)])
    assert _align(monkeypatch, g) is False
    assert g.drags == [(0, -SCROLL), (0, SCROLL)] and g.vars[map_align.RECOVERY_OFF]
    assert g.lines[-1] == "Map: landmark not found (correlation 0.12), map left as is"
    g.offsets = [(0.1, 30, 0)]
    assert _align(monkeypatch, g) is False
    assert g.drags == [(0, -SCROLL), (0, SCROLL)]
    assert g.lines[-1] == "Map: landmark not found (correlation 0.10), map left as is"
    g.vars.pop(map_align.RECOVERY_OFF)  # map_start: a drag back may have been lost
    g.offsets = [(0.1, 0, 0), (0.95, 0, 0)]
    assert _align(monkeypatch, g) is True
    assert g.drags[2:] == [(0, -SCROLL)]


def test_no_drag_when_the_map_did_not_open(monkeypatch):
    """go_map gave up (the map did not appear: the main screen behind): no drag up on another
    screen, said, and the look higher kept for a visit that has the map (review of c515703;
    the owner's log 2026-10-31 05:20)."""
    g = _Game([(0.18, 0, 0)], client=(1920, 1009))
    g.map_open = False
    assert _align(monkeypatch, g) is False
    assert g.drags == [] and map_align.RECOVERY_OFF not in g.vars
    assert g.lines == ["Map: the map is not open, alignment skipped"]
    g.map_open = True
    g.offsets = [(0.24, 0, 0), (0.95, 0, 0)]
    assert _align(monkeypatch, g) is True
    assert g.drags == [(0, -SCROLL)]


class _LandmarkScene:
    """The owner's 1920x1009 client around the landmark: the grey area of
    map-landmark-area-1920x1009 (map_align's near search area at half size, cut from a capture
    of the map in place) drawn at full size on open sea and moved by the drags, under the
    bottom HUD (the "New missions in" box and the idle banner, client y 940 down), which the
    drags do not move. Logical (x, y), centre-anchored, is client (x, y - 31)."""

    W, H, HUD_TOP, SEA, HUD = 1920, 1009, 940, 76, 40

    def __init__(self, offset):
        area = np.load(os.path.join(FIX, "map-landmark-area-1920x1009.npy"))
        self.area = np.repeat(np.repeat(area, 2, axis=0), 2, axis=1)
        self.offset = offset  # logical px the map is dragged down

    def grab(self, r):
        img = np.full((self.H, self.W), self.SEA, np.uint8)
        x1, y1 = 310 - atlas.MAP_LANDMARK_SEARCH, 765 - atlas.MAP_LANDMARK_SEARCH - 31
        y1 += self.offset
        h, w = self.area.shape
        top, bottom = max(0, y1), min(self.H, y1 + h)
        if bottom > top:
            img[top:bottom, x1 : x1 + w] = self.area[top - y1 : bottom - y1]
        img[self.HUD_TOP :] = self.HUD
        out = np.zeros((r.h, r.w, 3), np.uint8)
        ys, ye = max(0, r.y), min(self.H, r.y + r.h)
        xs, xe = max(0, r.x), min(self.W, r.x + r.w)
        if ye > ys and xe > xs:
            out[ys - r.y : ye - r.y, xs - r.x : xe - r.x] = img[ys:ye, xs:xe, None]
        return out


class _SceneGame(_Game):
    def __init__(self, scene):
        super().__init__([], client=(1920, 1009))
        self.scene = scene

    def drag(self, x1, y1, x2, y2, anchor=None):
        super().drag(x1, y1, x2, y2, anchor)
        self.scene.offset += y2 - y1


def _scene_align(monkeypatch, offset):
    scene = _LandmarkScene(offset)
    g = _SceneGame(scene)
    monkeypatch.setattr(capture, "grab", scene.grab)
    monkeypatch.setattr(map_align, "zoom_knob_x", lambda game: None)
    # the Windows reference alone (the Mac one never matches this client): a quicker search
    windows = [r for r in map_align.load_landmark() if r["name"] == "win32-1920x1009"]
    monkeypatch.setattr(map_align, "load_landmark", lambda: windows)
    return g, scene, map_align.align_map(g)


def test_the_real_landmark_of_a_map_left_220_px_down_is_found_again(monkeypatch):
    """The real landmark (the owner's map): in place it is found where it is; dragged down by
    the search beyond the north edge it lies under the bottom HUD, out of the near and the
    wide searches, and the map would stay there for every later visit; dragged up once, the
    map is found in place and stays there."""
    g, scene, aligned = _scene_align(monkeypatch, 0)
    assert aligned is True and g.drags == [] and g.lines == []
    g, scene, aligned = _scene_align(monkeypatch, SCROLL)
    assert aligned is True and scene.offset == 0 and g.drags == [(0, -SCROLL)]
    assert g.vars[map_align.SCALE_KEY] == 1.0 and map_align.RECOVERY_OFF not in g.vars


def test_each_run_aligns_and_looks_higher_again():
    """Game.vars outlives a Stop, which now leaves a map dragged by a search beyond its edge:
    the runner drops the run's "alignment given up" and "looked higher in vain" when a run
    starts, so its first alignment looks for the map again (review of 3cba41f)."""
    from types import SimpleNamespace

    from firestone_bot import runner
    from firestone_bot.features import map_start
    from firestone_bot.settings import Settings

    keys = (map_align.ALIGN_OFF, map_align.RECOVERY_OFF, map_start.WAY_KEY)
    g = SimpleNamespace(front_guard=None, vars=dict.fromkeys(keys, True))
    r = runner.Runner.__new__(runner.Runner)
    r.g, r.settings = g, Settings()
    r._cycle = lambda: False
    r.main_script()
    assert not any(key in g.vars for key in keys)
