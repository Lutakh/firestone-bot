"""Game-time text distinguishes measured age, restart fallback and unavailable readings."""

import pytest

from firestone_bot.gui.runtime_text import elapsed_text, runtime_text


def snapshot(**overrides):
    return {
        "game_uptime_s": 3600.0,
        "game_running": True,
        "restart_elapsed_s": 3600.0,
        "restart_interval_s": 6 * 3600.0,
        "restart_enabled": True,
        "restart_source": "game",
        "restart_test": False,
        "observed_at": 100.0,
        **overrides,
    }


def test_game_age_and_time_left_tick_between_process_observations():
    assert runtime_text(snapshot(), 105.0) == (
        "01h 00m 05s",
        "Restart at 6 h of game time · 04h 59m 55s left",
    )


def test_real_zero_uptime_is_not_treated_as_unknown():
    assert runtime_text(snapshot(game_uptime_s=0.0, restart_elapsed_s=0.0), 100.0) == (
        "00h 00m 00s",
        "Restart at 6 h of game time · 06h 00m 00s left",
    )


@pytest.mark.parametrize(
    "game_running, age", [(False, "Not running"), (True, "Unavailable"), (None, "Unavailable")]
)
def test_unknown_age_does_not_fabricate_game_time(game_running, age):
    result = runtime_text(
        snapshot(
            game_uptime_s=None,
            game_running=game_running,
            restart_elapsed_s=None,
            restart_source="unavailable",
        ),
        105.0,
    )
    assert result == (age, "Restart at 6 h: waiting for a readable clock.")


def test_bot_fallback_ticks_without_becoming_the_displayed_game_age():
    assert runtime_text(
        snapshot(game_uptime_s=None, restart_elapsed_s=3700.0, restart_source="bot"), 105.0
    ) == ("Unavailable", "Bot fallback timer: 01h 01m 45s · limit 6 h")


def test_bot_fallback_reports_the_actual_threshold():
    assert runtime_text(
        snapshot(
            game_uptime_s=None,
            restart_elapsed_s=3595.0,
            restart_interval_s=3600.0,
            restart_source="bot",
        ),
        105.0,
    ) == ("Unavailable", "Bot fallback timer: 01h 00m 00s · threshold reached")


def test_disabled_restart_takes_priority_over_a_saved_test_flag():
    assert runtime_text(snapshot(restart_enabled=False, restart_test=True), 100.0) == (
        "01h 00m 00s",
        "Scheduled restart: off",
    )


def test_one_shot_restart_works_even_with_the_periodic_interval_disabled():
    assert runtime_text(snapshot(restart_test=True, restart_interval_s=0.0), 100.0) == (
        "01h 00m 00s",
        "Restart once at the next cycle check.",
    )


def test_zero_interval_disables_periodic_restart():
    assert runtime_text(snapshot(restart_interval_s=0.0), 100.0) == (
        "01h 00m 00s",
        "Scheduled restart: interval disabled",
    )


def test_game_threshold_is_reported_at_the_next_cycle_check():
    reading = snapshot(game_uptime_s=6 * 3600 - 1, restart_elapsed_s=6 * 3600 - 1)
    assert runtime_text(reading, 100.0)[1].endswith("00h 00m 01s left")
    assert runtime_text(reading, 101.0) == (
        "06h 00m 00s",
        "Game age reached 6 h; restart at the next cycle check.",
    )


def test_stale_reading_stops_extrapolating_and_marks_timing_stale():
    assert runtime_text(snapshot(), 115.0)[0] == "01h 00m 15s"
    assert runtime_text(snapshot(), 116.0) == (
        "01h 00m 00s",
        "Last observation is stale; waiting for a fresh game-time check.",
    )


@pytest.mark.parametrize("invalid", [None, "invalid", -1, float("nan"), float("inf")])
def test_invalid_intervals_remain_unavailable(invalid):
    assert (
        runtime_text(snapshot(restart_interval_s=invalid), 100.0)[1]
        == "Restart interval: unavailable"
    )


@pytest.mark.parametrize("invalid", [None, "invalid", -1, float("nan"), float("inf")])
def test_invalid_clocks_remain_unavailable(invalid):
    assert runtime_text(snapshot(game_uptime_s=invalid, restart_elapsed_s=invalid), 100.0) == (
        "Unavailable",
        "Restart at 6 h: waiting for a readable clock.",
    )


def test_unknown_clock_source_is_not_labelled_as_measured_game_time():
    assert runtime_text(snapshot(restart_source="unknown"), 100.0)[1] == (
        "Restart at 6 h: waiting for a readable clock."
    )


def test_missing_observation_time_does_not_advance_an_old_clock():
    assert runtime_text(snapshot(observed_at=None), 100_000.0)[0] == "01h 00m 00s"


def test_missing_snapshot_and_long_duration_format():
    assert runtime_text({}, 100.0) == ("Not checked", "Restart timing: not checked")
    assert elapsed_text(100 * 3600 + 61.9) == "100h 01m 01s"
