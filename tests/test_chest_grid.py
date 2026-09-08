"""The new-style chest grid classifier (vision/chest_grid.py)."""

import numpy as np

from firestone_bot.vision import chest_grid, chest_refs


def _upsampled(name: str, size: int = 96) -> np.ndarray:
    ref = np.array(chest_refs.REFS[name]).reshape(chest_refs.THUMB, chest_refs.THUMB, 3)
    f = size // chest_refs.THUMB
    return np.kron(ref, np.ones((f, f, 1)))


def test_references_are_distinct():
    names = [n for n in chest_refs.REFS if n != "_empty"]
    for a in names:
        ta = chest_grid.thumbnail(_upsampled(a))
        others = [
            chest_grid.distance(ta, chest_grid.thumbnail(_upsampled(b))) for b in names if b != a
        ]
        assert chest_grid.distance(ta, chest_grid.thumbnail(_upsampled(a))) < 0.5
        assert min(others) > 15


def test_classify_matches_the_icon_with_noise_and_at_another_scale():
    rng = np.random.default_rng(1)
    for name in chest_refs.REFS:
        img = _upsampled(name, 120) + rng.normal(0, 4, (120, 120, 3))
        got, d, second = chest_grid.classify_thumbnails([chest_grid.thumbnail(img)])
        assert got == name, (name, got, d, second)


def test_classify_rejects_a_plain_colour():
    img = np.full((96, 96, 3), 120.0)
    got, _d, _second = chest_grid.classify_thumbnails([chest_grid.thumbnail(img)])
    assert got is None


def test_known_names_cover_the_owned_chests():
    for name in (
        "Common",
        "Uncommon",
        "Rare",
        "Epic",
        "Legendary",
        "Mythic",
        "Wooden",
        "Iron",
        "Golden",
        "Diamond",
        "Opal",
        "Emerald",
        "Comet",
    ):
        assert chest_grid.known(name)
    assert not chest_grid.known("Titan")


def test_bag_plan_opens_gifts_and_boxes_without_chests():
    from firestone_bot.features.open_chests import bag_plan

    class S:
        def __init__(self, **on):
            self.on = on

        def flag(self, key):
            return bool(self.on.get(key))

    assert bag_plan(S()) == (False, False, False, False)
    assert bag_plan(S(MysteryBoxes=1)) == (False, False, True, False)
    assert bag_plan(S(OracleGifts=1, Chests=1)) == (True, True, False, False)
    assert bag_plan(S(Bless=1)) == (False, False, False, False)
    assert bag_plan(S(Bless=1, BlessingChests=1)) == (False, False, False, True)
    assert bag_plan(S(Bless=1, Chests=1)) == (True, False, False, True)
