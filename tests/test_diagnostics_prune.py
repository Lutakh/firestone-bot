"""Diagnostics captures: 3 of a kind, 60 in all, and now no older than 7 days and no more
than 50 MB in all (the owner's folder held 85 MB, 2026-10-22)."""

from __future__ import annotations

import os
import time

from firestone_bot.game import prune_diagnostics


def _capture(folder, name, age_days=0.0, size=10):
    path = folder / name
    path.write_bytes(b"x" * size)
    t = time.time() - age_days * 86400
    os.utime(path, (t, t))
    return path


def test_captures_older_than_seven_days_go(tmp_path):
    old = _capture(tmp_path, "20261001-120000-town-open.png", age_days=8)
    recent = _capture(tmp_path, "20261020-120000-town-open.png", age_days=2)
    prune_diagnostics(str(tmp_path))
    assert not old.exists() and recent.exists()


def test_the_newest_captures_are_kept_within_the_size_cap(tmp_path):
    files = [
        _capture(tmp_path, f"20261022-12000{i}-kind{i}.png", age_days=i / 100, size=400)
        for i in range(5)
    ]
    prune_diagnostics(str(tmp_path), max_bytes=1000)
    assert [p.exists() for p in files] == [True, True, False, False, False]


def test_the_file_just_written_is_never_deleted(tmp_path):
    big = _capture(tmp_path, "20261022-120000-big.png", size=2000)
    prune_diagnostics(str(tmp_path), spare=str(big), max_bytes=1000)
    assert big.exists()
