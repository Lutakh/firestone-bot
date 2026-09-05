"""Atlas integrity: every point/probe lies inside the reference screen, colours are 24-bit."""

from firestone_bot.vision import atlas
from firestone_bot.vision.atlas import Point, Probe


def _walk(obj, seen=None):
    seen = seen if seen is not None else set()
    if id(obj) in seen or isinstance(obj, type):
        return
    seen.add(id(obj))
    if isinstance(obj, (Point, Probe)):
        yield obj
    elif isinstance(obj, (tuple, list)):
        for x in obj:
            yield from _walk(x, seen)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from _walk(x, seen)
    elif hasattr(obj, "__dataclass_fields__"):
        for f in obj.__dataclass_fields__:
            yield from _walk(getattr(obj, f), seen)


def _entries():
    for name in dir(atlas):
        if name.startswith("_"):
            continue
        yield from _walk(getattr(atlas, name))


def test_entries_inside_reference_screen():
    items = list(_entries())
    assert len(items) > 150
    for it in items:
        if isinstance(it, Point):
            assert 0 <= it.x < 1920 and 0 <= it.y < 1080, it
        else:
            p = it.normalized()
            assert 0 <= p.x1 <= p.x2 < 1920, it
            assert 0 <= p.y1 <= p.y2 < 1080, it
            assert 0 <= p.color <= 0xFFFFFF and 0 <= p.variation <= 32, it


def test_probe_names_unique():
    names = [p.name for p in _entries() if isinstance(p, Probe) and p.name]
    dupes = {n for n in names if names.count(n) > 1}
    # rows 2-4 of the exotic upgrade grid share probes on purpose
    assert dupes <= {"exu_rNs1", "exu_rNs2", "exu_rNs3"}, dupes


def test_map_mission_groups_cover_priorities():
    assert set(atlas.MAP_MISSION_GROUPS) == {"2 Squad", "War", "Medium", "Short", "Leftover"}
    assert sum(len(v) for v in atlas.MAP_MISSION_GROUPS.values()) == 77
