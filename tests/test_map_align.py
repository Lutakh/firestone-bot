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
