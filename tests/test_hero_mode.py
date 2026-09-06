"""Mode-button label reader of the hero upgrades (column profile in logical units)."""

import numpy as np

from firestone_bot.features import hero_upgrade as hu


class _G:
    def __init__(self, img):
        self.img = img

    def region_image(self, rect):
        return self.img


def _label(width_px, text_cols, rows=(30, 50)):
    """Blue image with a white 'word' spanning text_cols on the last line, and 'Upgrade' above."""
    img = np.zeros((70, width_px, 3), dtype=np.uint8)
    img[:, :, 0] = 255  # blue
    img[5:20, 40:200] = 255  # first line (ignored)
    img[rows[0] : rows[1], text_cols[0] : text_cols[1]] = 255
    return img


def test_signature_uses_the_last_line_in_logical_units():
    # a 180 logical px rect captured at 2 px per logical px
    sig = hu._mode_signature(_G(_label(360, (120, 240))), (0, 0, 180, 70), light_text=True)
    extent, profile = sig
    assert extent == (60, 119)
    assert len(profile) == 18 and abs(profile.sum() - 1.0) < 1e-6
    assert profile[:6].sum() == 0 and profile[12:].sum() == 0


def test_signature_is_the_same_at_another_scale():
    a = hu._mode_signature(_G(_label(360, (120, 240))), (0, 0, 180, 70), light_text=True)
    b = hu._mode_signature(_G(_label(180, (60, 120))), (0, 0, 180, 70), light_text=True)
    assert a[0] == b[0]
    assert np.abs(a[1] - b[1]).sum() < 0.02


def test_reference_resampling_keeps_bins_and_mass():
    ref = ((30, 211), [0.0, 0.1, 0.2, 0.3, 0.2, 0.1, 0.1, 0.0])  # 8 buckets of 10 px = 80 px
    extent, profile = hu._ref_signature(ref, 240)
    assert len(profile) == 24 and abs(profile.sum() - 1.0) < 1e-6
    assert extent == (90, 633)  # scaled by 240 / 80
