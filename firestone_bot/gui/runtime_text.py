"""Human-readable game age and the runner's restart clock, without game side effects."""

from __future__ import annotations

import math


def _number(value) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError):
        return None


def elapsed_text(seconds: float) -> str:
    hours, rest = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


def runtime_text(snapshot: dict, now: float) -> tuple[str, str]:
    """Tick between five-second observations; stop extrapolating a stale reading."""
    if not snapshot:
        return "Not checked", "Restart timing: not checked"
    observed = _number(snapshot.get("observed_at"))
    since = max(0, now - observed) if observed is not None else 0
    stale = since > 15
    advance = 0 if stale else since
    age = _number(snapshot.get("game_uptime_s"))
    uptime = (
        elapsed_text(age + advance)
        if age is not None
        else "Not running"
        if snapshot.get("game_running") is False
        else "Unavailable"
    )
    if stale:
        return uptime, "Last observation is stale; waiting for a fresh game-time check."
    if not snapshot.get("restart_enabled"):
        return uptime, "Scheduled restart: off"
    if snapshot.get("restart_test"):
        return uptime, "Restart once at the next cycle check."
    interval = _number(snapshot.get("restart_interval_s"))
    if interval is None:
        return uptime, "Restart interval: unavailable"
    if interval == 0:
        return uptime, "Scheduled restart: interval disabled"
    threshold = f"{interval / 3600:g} h"
    elapsed = _number(snapshot.get("restart_elapsed_s"))
    source = snapshot.get("restart_source")
    if elapsed is None or source not in ("game", "bot"):
        return uptime, f"Restart at {threshold}: waiting for a readable clock."
    elapsed += advance
    if source == "bot":
        state = "threshold reached" if elapsed >= interval else f"limit {threshold}"
        return uptime, f"Bot fallback timer: {elapsed_text(elapsed)} · {state}"
    if elapsed >= interval:
        return uptime, f"Game age reached {threshold}; restart at the next cycle check."
    return uptime, f"Restart at {threshold} of game time · {elapsed_text(interval - elapsed)} left"
