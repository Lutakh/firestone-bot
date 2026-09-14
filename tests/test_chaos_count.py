"""A chaos hit is counted only when the game took the click (the green button greyed)."""

from firestone_bot.features import chaos
from firestone_bot.vision import atlas


class FakeGame:
    def __init__(self, greys: bool):
        self.greys = greys
        self.asked = []

    def wait_gone(self, probe, timeout_ms):
        self.asked.append((probe.name, timeout_ms))
        return self.greys


def test_hit_counts_only_when_the_button_greys():
    g = FakeGame(greys=True)
    assert chaos._hit_taken(g) is True
    assert g.asked == [(atlas.CHAOS_HIT_READY.name, chaos.HIT_TAKEN_MS)]
    assert chaos._hit_taken(FakeGame(greys=False)) is False
