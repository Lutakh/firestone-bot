"""Import of settings.ini from another bot folder: detection, search, copy without overwrite."""

import os

from firestone_bot import userfiles


def _write_settings(folder, encoding="utf-16"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "settings.ini"), "w", encoding=encoding) as f:
        f.write("[CommonOptions]\nEvents=1\n")


def test_looks_like_bot_settings(tmp_path):
    _write_settings(tmp_path / "a")
    _write_settings(tmp_path / "b", "utf-8")
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "settings.ini").write_text("[Other]\nx=1\n")
    assert userfiles.looks_like_bot_settings(str(tmp_path / "a" / "settings.ini"))
    assert userfiles.looks_like_bot_settings(str(tmp_path / "b" / "settings.ini"))
    assert not userfiles.looks_like_bot_settings(str(tmp_path / "c" / "settings.ini"))
    assert not userfiles.looks_like_bot_settings(str(tmp_path / "missing.ini"))


def test_find_candidates_skips_base_and_orders_newest_first(tmp_path):
    base = tmp_path / "new" / "FirestoneBot"
    base.mkdir(parents=True)
    _write_settings(tmp_path / "old1")
    _write_settings(tmp_path / "old2" / "deeper")
    _write_settings(tmp_path / "old1" / "_internal")  # skipped folder
    _write_settings(base)  # the install itself never counts
    os.utime(tmp_path / "old1" / "settings.ini", (1_000, 1_000))
    os.utime(tmp_path / "old2" / "deeper" / "settings.ini", (2_000, 2_000))
    found = userfiles.find_candidates(str(base), roots=[str(tmp_path)])
    assert [c.folder for c in found] == [
        str(tmp_path / "old2" / "deeper"),
        str(tmp_path / "old1"),
    ]
    assert "2000-01-01" not in found[0].label  # label uses local time of the mtime, no crash


def test_import_user_files_never_overwrites(tmp_path):
    src, base = tmp_path / "src", tmp_path / "base"
    _write_settings(src)
    (src / "gui_state.json").write_text("{}")
    base.mkdir()
    (base / "gui_state.json").write_text('{"mine": 1}')
    copied, skipped = userfiles.import_user_files(str(src), str(base))
    assert copied == ["settings.ini"] and skipped == ["gui_state.json"]
    assert (base / "gui_state.json").read_text() == '{"mine": 1}'
    assert (src / "settings.ini").exists()
