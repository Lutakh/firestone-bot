"""The alchemist's free Speed up is told from the paid one by the gem icon."""

import numpy as np

from firestone_bot.features.alchemist import free_to_complete
from firestone_bot.vision import atlas
from firestone_bot.vision.probes import color_rgb


class FakeGame:
    def __init__(self, img):
        self.img = img

    def region_image(self, rect):
        return self.img


def _button(orange: bool, gem: bool):
    img = np.zeros((70, 185, 3), dtype=np.uint8)
    img[:, :] = (200, 93, 102)  # BGR of the blue panel behind an idle slot
    if orange:
        r, g, b = color_rgb(atlas.ORANGE_1)
        img[10:65, :] = (b, g, r)
    if gem:
        img[30:52, 50:72] = (0x9D, 0x00, 0x9F)  # measured gem purple 0x9F009D (BGR)
    return img


def test_paid_speed_up_is_never_free():
    slot = atlas.ALCHEMY_SLOTS[1]
    assert free_to_complete(FakeGame(_button(orange=True, gem=True)), slot) is False


def test_free_speed_up_and_idle_slot():
    slot = atlas.ALCHEMY_SLOTS[1]
    assert free_to_complete(FakeGame(_button(orange=True, gem=False)), slot) is True
    assert free_to_complete(FakeGame(_button(orange=False, gem=False)), slot) is False
