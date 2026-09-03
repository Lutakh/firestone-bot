"""pixel_search semantics on synthetic BGRA images (AHK PixelSearch, Fast RGB)."""

import numpy as np

from firestone_bot.platform.window import Rect
from firestone_bot.vision.probes import pixel_at, pixel_search_image, pixel_search_in


def img_filled(w, h, rgb):
    r, g, b = rgb
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, 0] = b
    img[:, :, 1] = g
    img[:, :, 2] = r
    img[:, :, 3] = 255
    return img


def test_first_hit_is_row_major():
    img = img_filled(10, 10, (0, 0, 0))
    img[5, 7, :3] = (8, 160, 10)  # BGR of 0x0AA008
    img[6, 1, :3] = (8, 160, 10)
    assert pixel_search_image(img, 0x0AA008, 0) == (7, 5)


def test_variation_is_per_channel():
    img = img_filled(4, 4, (0, 0, 0))
    img[2, 2, :3] = (8 + 3, 160 - 3, 10 + 3)
    assert pixel_search_image(img, 0x0AA008, 3) == (2, 2)
    assert pixel_search_image(img, 0x0AA008, 2) is None
    img[2, 2, :3] = (8, 160 + 4, 10)
    assert pixel_search_image(img, 0x0AA008, 3) is None


def test_search_in_rect_returns_screen_coords_and_clips():
    img = img_filled(100, 50, (0, 0, 0))
    img[40, 90, :3] = (0, 0, 244)  # 0xF40000
    origin = Rect(1000, 500, 100, 50)
    assert pixel_search_in(img, origin, Rect(1080, 530, 50, 50), 0xF40000, 3) == (1090, 540)
    assert pixel_search_in(img, origin, Rect(1000, 500, 80, 40), 0xF40000, 3) is None
    assert pixel_search_in(img, origin, Rect(2000, 900, 10, 10), 0xF40000, 3) is None


def test_pixel_at():
    img = img_filled(2, 2, (0x12, 0x34, 0x56))
    assert pixel_at(img, 1, 1) == 0x123456
