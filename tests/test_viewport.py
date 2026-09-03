"""Viewport maths against the 4.2 measurements (docs/MEASUREMENTS.md)."""

import pytest

from firestone_bot.platform.window import Rect
from firestone_bot.vision.atlas import REF, Probe
from firestone_bot.vision.viewport import Viewport

# Gold coin icon centre measured on the captures, in client pixels.
COIN_REF = (1594.5, 47.5)  # 1920x1009 (reference)
COIN_MEASURED = {
    (1280, 720): (1047.5, 34.0),
    (960, 540): (786.0, 25.0),
    (1600, 1000): (1310.0, 42.5),
    (1280, 673): (1064.0, 31.5),
    (1920, 1080): (1572.0, 51.0),
}
COIN_LOGICAL = (COIN_REF[0] + REF.x, COIN_REF[1] + REF.y)


def test_identity_on_reference_setup():
    vp = Viewport(Rect(0, 31, 1920, 1009))
    assert vp.rel_scale == pytest.approx(1.0)
    assert vp.to_screen(1851, 84) == (1851, 84)
    assert vp.to_logical(56, 777) == (56, 777)


def test_windows11_offset():
    vp = Viewport(Rect(0, 23, 1920, 1009))
    assert vp.to_screen(1851, 84) == (1851, 76)
    assert vp.to_logical(1851, 76) == (1851, 84)


@pytest.mark.parametrize("size", list(COIN_MEASURED))
def test_coin_prediction_matches_measurement(size):
    w, h = size
    vp = Viewport(Rect(8, 31, w, h))
    sx, sy = vp.to_screen_f(*COIN_LOGICAL, anchor=(1.0, 0.0))
    mx, my = COIN_MEASURED[size]
    assert abs(sx - 8 - mx) <= 2.5, (sx - 8, mx)
    assert abs(sy - 31 - my) <= 2.5, (sy - 31, my)


@pytest.mark.parametrize("k", [0.5, 2 / 3, 1.5])
def test_same_aspect_is_anchor_independent(k):
    w, h = round(1920 * k), round(1009 * k)
    vp = Viewport(Rect(100, 50, w, h))
    for x, y in [(56, 777), (1851, 84), (960, 500), (1175, 996)]:
        results = {vp.to_screen(x, y, anchor=(ax, ay)) for ax in (0, 0.5, 1) for ay in (0, 0.5, 1)}
        xs = {r[0] for r in results}
        ys = {r[1] for r in results}
        assert max(xs) - min(xs) <= 1 and max(ys) - min(ys) <= 1, results


def test_roundtrip():
    vp = Viewport(Rect(8, 31, 1280, 720))
    for x, y in [(56, 777), (1851, 84), (960, 500), (1175, 996)]:
        sx, sy = vp.to_screen(x, y)
        lx, ly = vp.to_logical(sx, sy)
        assert abs(lx - x) <= 1 and abs(ly - y) <= 1


def test_probe_rect_inclusive_and_grown():
    vp = Viewport(Rect(0, 31, 1920, 1009))
    p = Probe(1187, 1012, 1175, 996, 0x542710, 10)  # inverted corners on purpose
    r = vp.probe_rect_screen(p, grow=1)
    assert (r.x, r.y, r.w, r.h) == (1174, 995, 15, 19)


def test_probe_rect_scales_down():
    vp = Viewport(Rect(0, 0, 960, 504))  # half of the reference client, same aspect
    r = vp.probe_rect_screen(Probe(1260, 780, 1334, 835, 0x0AA008), grow=0)
    assert r.w == pytest.approx(75 * 0.5, abs=1.5)
    assert r.h == pytest.approx(56 * 0.5, abs=1.5)
