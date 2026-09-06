"""Read a small number drawn in the game's UI font (account level on the avatar, guild level).

The bot has no OCR dependency: the game draws numbers in one bold rounded font, white with a
dark outline, so a number is read by template matching. Glyphs are isolated as runs of
columns holding bright pixels, each glyph is resampled to a fixed cell (GLYPH_W x GLYPH_H) and
compared with the ten digit templates (normalised correlation). The resampling makes the
reader independent of the font size, hence of the screen resolution. Templates are built
once from a reference capture by tools/digit_templates.py and stored in digit_templates.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

GLYPH_W = 12
GLYPH_H = 20
BRIGHT = 190  # min R, G and B of a "white" pixel (outlined white digits on any background)
MIN_SCORE = 0.62  # correlation below this: the glyph is not a digit we know
TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "digit_templates.json")


@dataclass
class Glyph:
    x0: int
    x1: int  # exclusive
    y0: int
    y1: int  # exclusive
    cell: np.ndarray  # GLYPH_H x GLYPH_W float32, 0..1

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def bright_mask(img_bgr: np.ndarray) -> np.ndarray:
    px = img_bgr[:, :, :3]
    return (px[:, :, 0] >= BRIGHT) & (px[:, :, 1] >= BRIGHT) & (px[:, :, 2] >= BRIGHT)


def resample(mask: np.ndarray, w: int = GLYPH_W, h: int = GLYPH_H) -> np.ndarray:
    """Area-average a boolean glyph mask into an h x w float cell (no scipy needed)."""
    src_h, src_w = mask.shape
    ys = np.linspace(0, src_h, h + 1)
    xs = np.linspace(0, src_w, w + 1)
    out = np.zeros((h, w), dtype=np.float32)
    m = mask.astype(np.float32)
    for j in range(h):
        y0, y1 = int(ys[j]), max(int(ys[j]) + 1, int(np.ceil(ys[j + 1])))
        row = m[y0:y1]
        for i in range(w):
            x0, x1 = int(xs[i]), max(int(xs[i]) + 1, int(np.ceil(xs[i + 1])))
            out[j, i] = row[:, x0:x1].mean()
    return out


def segment(img_bgr: np.ndarray, min_gap: int = 1) -> list[Glyph]:
    """Glyphs left to right: runs of columns with bright pixels, trimmed vertically."""
    mask = bright_mask(img_bgr)
    cols = mask.any(axis=0)
    glyphs: list[Glyph] = []
    x = 0
    w = cols.shape[0]
    while x < w:
        if not cols[x]:
            x += 1
            continue
        x0 = x
        while x < w and (cols[x] or (min_gap > 1 and cols[x : x + min_gap].any())):
            x += 1
        x1 = x
        y0, y1 = _main_row_run(mask[:, x0:x1].any(axis=1))
        glyphs.append(Glyph(x0, x1, y0, y1, resample(mask[y0:y1, x0:x1])))
    return glyphs


def _main_row_run(rows: np.ndarray) -> tuple[int, int]:
    """Longest run of consecutive rows holding pixels: the glyph body, without bright
    specks above or below it (a badge border, a stray highlight)."""
    best = (0, 0)
    y = 0
    n = rows.shape[0]
    while y < n:
        if not rows[y]:
            y += 1
            continue
        y0 = y
        while y < n and rows[y]:
            y += 1
        if y - y0 > best[1] - best[0]:
            best = (y0, y)
    return best


def digit_glyphs(glyphs: list[Glyph]) -> list[Glyph]:
    """Drop punctuation and lowercase letters: anything under 75 % of the tallest glyph."""
    if not glyphs:
        return []
    tallest = max(g.height for g in glyphs)
    return [g for g in glyphs if g.height >= 0.75 * tallest and g.x1 - g.x0 >= 2]


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d > 0 else 0.0


class DigitReader:
    def __init__(self, templates: dict[str, list[np.ndarray]] | None = None) -> None:
        self.templates = templates if templates is not None else load_templates()

    def classify(self, cell: np.ndarray) -> tuple[str, float]:
        best, score = "", -1.0
        for digit, cells in self.templates.items():
            for t in cells:
                c = correlation(cell, t)
                if c > score:
                    best, score = digit, c
        return best, score

    def read(self, img_bgr: np.ndarray, last_word: bool = False) -> int | None:
        """The number in the image, None when no glyph is a confident digit. With
        `last_word` only the glyphs after the last word gap are read ("Guild level 24")."""
        glyphs = digit_glyphs(segment(img_bgr))
        if last_word:
            glyphs = words(glyphs)[-1] if glyphs else []
        text = ""
        for g in glyphs:
            digit, score = self.classify(g.cell)
            if score < MIN_SCORE:
                return None
            text += digit
        return int(text) if text else None


def words(glyphs: list[Glyph]) -> list[list[Glyph]]:
    """Split glyphs at gaps wider than half the median glyph width (a space)."""
    if not glyphs:
        return []
    widths = sorted(g.x1 - g.x0 for g in glyphs)
    gap_min = max(3, widths[len(widths) // 2] * 0.5)
    out: list[list[Glyph]] = [[glyphs[0]]]
    for prev, g in pairwise(glyphs):
        if g.x0 - prev.x1 >= gap_min:
            out.append([])
        out[-1].append(g)
    return out


def load_templates(path: str = TEMPLATES_PATH) -> dict[str, list[np.ndarray]]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        d: [np.array(c, dtype=np.float32).reshape(GLYPH_H, GLYPH_W) for c in cells]
        for d, cells in raw.items()
    }


def save_templates(templates: dict[str, list[np.ndarray]], path: str = TEMPLATES_PATH) -> None:
    raw = {
        d: [[round(float(v), 3) for v in c.ravel()] for c in cells]
        for d, cells in templates.items()
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f)
