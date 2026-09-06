"""Digit segmentation: a bright speck outside the glyph body must not widen the glyph."""

import numpy as np

from firestone_bot.vision import digits


def _image(with_glint: bool) -> np.ndarray:
    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[5:30, 10:22] = 255  # a glyph body (12 columns)
    if with_glint:
        for i in range(10):  # a diagonal glint under and right of the glyph, touching its columns
            img[33 + i // 3, 20 + i] = 255
    return img


def test_glyph_columns_follow_the_body_rows():
    plain = digits.segment(_image(False))
    glint = digits.segment(_image(True))
    assert [(g.x0, g.x1, g.y0, g.y1) for g in plain] == [(10, 22, 5, 30)]
    assert [(g.x0, g.x1, g.y0, g.y1) for g in glint] == [(10, 22, 5, 30)]
    assert np.array_equal(plain[0].cell, glint[0].cell)
