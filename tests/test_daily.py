"""Daily counters: token limit, arena flag, reset, persistence."""

from firestone_bot import daily
from firestone_bot.settings import Settings


def test_token_limit_and_reset(tmp_path):
    s = Settings(path=str(tmp_path / "settings.ini"))
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
    s = Settings(path=str(tmp_path / "settings.ini"))
    assert daily.chaos_left(s) == 10  # default MaxChaos
    for _ in range(10):
        daily.note_chaos_hit(s)
    assert daily.chaos_left(s) == 0
    daily.mark_daily_reset(s)
    assert daily.chaos_left(s) == 10 and s.get("LastChaosReset") == s.get("LastTokenReset")
    s.set("MaxChaos", 0)
    assert daily.chaos_left(s) is None
