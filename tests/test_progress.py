"""Feature gating by account / guild level, and the digit reader's building blocks."""

import numpy as np

from firestone_bot import progress
from firestone_bot.vision import digits


def test_locked_reason_by_account_and_guild_level(tmp_path):
    p = progress.Progress.load(str(tmp_path / "progress.json"))
    assert p.locked_reason("engineer") is None  # unknown level never gates
    p.set_account_level(36)
    assert "account level 50" in p.locked_reason("engineer")
    assert "account level 200" in p.locked_reason("oracle")
    assert p.locked_reason("unknown_feature") is None
    p.set_account_level(50)
    assert p.locked_reason("engineer") is None
    assert p.locked_reason("guild_crystal") is None  # guild level unknown
    p.set_guild_level(3)
    assert "guild level 5" in p.locked_reason("guild_crystal")
    p.set_guild_level(24)
    assert p.locked_reason("guild_crystal") is None
    assert not p.need_guild_check()
    assert p.need_account_check()
    p.set_account_level(200)
    assert not p.need_account_check()
    # persisted and reloaded
    q = progress.Progress.load(str(tmp_path / "progress.json"))
    assert (q.account_level, q.guild_level) == (200, 24)
    q.set_account_level(None)  # unreadable: previous value kept
    assert q.account_level == 200


def test_templates_are_self_consistent():
    reader = digits.DigitReader()
    assert set(reader.templates) == set("0123456789")
    for digit, cells in reader.templates.items():
        for cell in cells:
            assert reader.classify(cell)[0] == digit


def test_segment_words_and_row_run():
    # two 4x6 L-shaped glyphs separated by a 6 px gap, plus a bright speck above the first
    img = np.zeros((12, 20, 3), dtype=np.uint8)
    for x0 in (1, 11):
        img[4:10, x0 : x0 + 2] = 255
        img[8:10, x0 : x0 + 4] = 255
    img[0, 2] = 255
    glyphs = digits.segment(img)
    assert [(g.x0, g.x1, g.y0, g.y1) for g in glyphs] == [(1, 5, 4, 10), (11, 15, 4, 10)]
    assert [len(w) for w in digits.words(glyphs)] == [1, 1]
    assert digits.DigitReader({"7": [glyphs[0].cell]}).read(img) == 77
    assert digits.DigitReader({"7": [glyphs[0].cell]}).read(img, last_word=True) == 7
    assert digits.DigitReader({"7": [np.zeros((20, 12), np.float32)]}).read(img) is None


def test_locked_short_forms():
    from firestone_bot.progress import Progress

    p = Progress()
    p.account_level, p.guild_level = 37, 4
    assert p.locked_short("guild_chaos") == "level 100"
    assert p.locked_short("guild_crystal") == "level 50"
    p.account_level = 60
    assert p.locked_short("guild_crystal") == "guild level 5"
    assert p.locked_short("arena") is None
