"""Daily counters: token limit, arena flag, reset, persistence, enlightenment budget."""

from firestone_bot import daily
from firestone_bot.settings import Settings


def test_token_limit_and_reset(tmp_path):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    assert daily.tokens_left(s) is None  # MaxTokens 0 = unlimited
    s.set("MaxTokens", 2)
    assert daily.tokens_left(s) == 2
    daily.note_token_used(s)
    daily.note_token_used(s)
    assert daily.tokens_left(s) == 0
    daily.note_arena_done(s)
    assert daily.arena_done(s)
    s2 = Settings.load(str(tmp_path / "settings.ini"))
    assert s2.get("TokenCountDaily") == "2" and daily.arena_done(s2)
    daily.mark_daily_reset(s2)
    assert daily.tokens_left(s2) == 2 and not daily.arena_done(s2)
    assert len(s2.get("LastTokenReset")) == 14


def test_bad_values_are_zero():
    s = Settings()
    s.set("TokenCountDaily", "abc")
    s.set("MaxTokens", "3")
    assert daily.tokens_left(s) == 3


def test_chaos_limit_and_reset(tmp_path):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    assert daily.chaos_left(s) == 10  # default MaxChaos
    for _ in range(10):
        daily.note_chaos_hit(s)
    assert daily.chaos_left(s) == 0
    daily.mark_daily_reset(s)
    assert daily.chaos_left(s) == 10 and s.get("LastChaosReset") == s.get("LastTokenReset")
    s.set("MaxChaos", 0)
    assert daily.chaos_left(s) is None


def test_scarab_limit_and_reset(tmp_path):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    assert daily.scarab_left(s) == 10
    daily.note_scarab_play(s)
    assert daily.scarab_left(s) == 9
    daily.mark_daily_reset(s)
    assert daily.scarab_left(s) == 10


def test_guardian_order_parsing():
    from firestone_bot.features.guardian_chaos import guardian_order

    class G:
        settings = Settings()

    g = G()
    g.settings.set("ChaosGuardianOrder", "3, 1,2;4,3,9")
    assert guardian_order(g) == [3, 1, 2, 4]
    g.settings.set("ChaosGuardianOrder", "")
    assert guardian_order(g) == [1, 2, 3, 4]


def test_crystal_limit_and_reset(tmp_path):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    assert daily.crystal_left(s) == 5
    daily.note_crystal_hit(s)
    assert daily.crystal_left(s) == 4
    daily.mark_daily_reset(s)
    assert daily.crystal_left(s) == 5


def _enlighten(tmp_path, **values):
    s = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    for k, v in values.items():
        s.set(k, v)
    return s


def test_enlightenment_is_off_by_default(tmp_path):
    s = _enlighten(tmp_path)
    assert not daily.enlighten_on(s) and not daily.enlighten_wanted(s)
    assert daily.enlighten_count_left(s) == 0
    assert daily.enlighten_dust_left(s) is None and daily.enlighten_reserve(s) == 0
    assert daily.enlightenments_allowed(s, 8015) == 0
    # the limits of a switched-off automation do not count
    s.set("MaxEnlightenDust", 1000)
    s.set("EnlightenDustReserve", 2000)
    assert daily.enlighten_dust_left(s) is None and daily.enlighten_reserve(s) == 0


def test_enlightenment_count_limit_and_the_event(tmp_path):
    s = _enlighten(tmp_path, GuardianEnlighten=1)
    assert daily.enlighten_count_left(s) == 3  # the default MaxEnlighten
    s.set("MaxEnlighten", 0)
    assert daily.enlighten_count_left(s) is None and daily.enlighten_wanted(s)
    s.set("MaxEnlighten", 7)
    s.set("EnlightenCountDaily", 2)
    assert daily.enlighten_count_left(s) == 5
    s.set("EventDecoratedHeroes", 1)
    s.set("MaxEnlighten", 2)
    assert daily.enlighten_limit(s) == 3  # raised to the event's challenge
    assert daily.event_enlighten_need(s) == 1 and daily.enlighten_count_left(s) == 1
    s.set("MaxEnlighten", 0)
    assert daily.enlighten_count_left(s) is None  # no limit stays no limit
    s.set("GuardianEnlighten", 0)
    assert daily.enlighten_count_left(s) == 1  # the event alone: exactly its need


def test_enlightenment_dust_cap_reserve_and_one_save_per_note(tmp_path):
    s = _enlighten(tmp_path, GuardianEnlighten=1, MaxEnlightenDust=1000, EnlightenDustReserve=2000)
    saves = []
    save = s.save
    s.save = lambda *a, **kw: saves.append(1) or save(*a, **kw)
    daily.note_enlighten(s, 20, 400)  # one x20 click
    assert len(saves) == 1
    assert s.get("EnlightenCountDaily") == "20" and s.get("EnlightenDustDaily") == "400"
    assert daily.enlighten_dust_left(s) == 600 and daily.enlighten_reserve(s) == 2000
    daily.note_enlighten(s, 30, 600)
    assert daily.enlighten_dust_left(s) == 0 and not daily.enlighten_wanted(s)
    s2 = Settings.load(str(tmp_path / "settings.ini"))
    assert s2.get("EnlightenDustDaily") == "1000" and s2.get("EnlightenCountDaily") == "50"
    daily.mark_daily_reset(s2)
    assert s2.get("EnlightenDustDaily") == "0" and s2.get("EnlightenCountDaily") == "0"
    assert daily.enlighten_dust_left(s2) == 1000


def test_enlightenment_planner():
    plan = daily.plan_enlightenments
    # dust, unit, event need, count left, dust left, reserve
    assert plan(8015, 20, 0, None, None, 0) == 400  # every limit 0: all the dust
    assert plan(2500, 20, 0, None, None, 2000) == 25  # the reserve
    assert plan(1990, 20, 0, None, None, 2000) == 0  # below the reserve
    assert plan(8015, 20, 0, None, 1000, 0) == 50  # the dust cap
    assert plan(8015, 20, 0, 7, None, 0) == 7  # the count
    assert plan(8015, 20, 0, 30, 500, 7800) == 10  # combined: the strictest wins
    assert plan(10, 20, 0, None, None, 0) == 0  # not even one
    # the event's need is made whatever the cap and the reserve say
    assert plan(2030, 20, 3, 3, None, 2000) == 3
    assert plan(8015, 20, 3, 30, 0, 0) == 3
    # an unreadable counter: the event blind at x1; the automation only under a count alone
    assert plan(None, 20, 3, None, None, 0) == 3
    assert plan(None, 20, 0, None, None, 0) == 0
    assert plan(None, 20, 0, 5, None, 0) == 5
    assert plan(None, 20, 0, 5, 1000, 0) == 0
    assert plan(None, 20, 0, 5, None, 2000) == 0
    assert plan(None, 20, 2, 5, None, 2000) == 2
