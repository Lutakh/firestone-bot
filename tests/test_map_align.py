"""World-map alignment: landmark search and the bundled reference file."""

import json
import os

import numpy as np

from firestone_bot.features import map_align


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

    def _viewport(self):
        return self.vp

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


def test_landmark_offset_scores_every_reference(monkeypatch):
    """The scores come from landmark_offset itself (near search on the fixture areas)."""
    landmark = map_align.load_landmark()
    for name, want in (
        ("map-landmark-area-1920x1080-fitted", map_align.FITTED_SCALE),
        ("map-landmark-area-1920x1009", 1.0),
    ):
        big = np.load(os.path.join(FIX, f"{name}.npy")).astype(float)
        monkeypatch.setattr(map_align, "_gray_logical", lambda g, rect, s, big=big: big)
        scores = {}
        c, _, _ = map_align.landmark_offset(None, landmark, scores)
        assert set(scores) == {r["name"] for r in landmark} and c == max(scores.values())
        assert map_align.map_scale(scores) == want


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
    # a popup over the landmark: nothing measured, the scale stays
    g.offsets = [(0.1, 0, 0)]
    assert _align(monkeypatch, g, {"mac-original": 0.1}) is False
    assert g.vars[map_align.SCALE_KEY] == map_align.FITTED_SCALE


def test_the_reference_client_says_nothing_about_the_scale(monkeypatch):
    g = _Game([(0.97, 0, 0)], client=(1920, 1009))
    _align(monkeypatch, g, {"mac-original": 0.22, "win32-1920x1009": 0.97})
    assert g.vars[map_align.SCALE_KEY] == 1.0 and g.lines == []
