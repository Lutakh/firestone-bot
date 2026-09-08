"""Overview counts must respect legacy inverted settings and live configuration."""

from firestone_bot.gui.routines import ROUTINES, Routine, enabled_count
from firestone_bot.settings import Settings


def test_inverted_switches_and_regular_switches(tmp_path):
    settings = Settings(path=str(tmp_path / "settings.ini"))
    routine = Routine("main", "Heroes", "", ("NoHero", "Chests"))
    settings.set("NoHero", "0")
    settings.set("Chests", "1")
    assert enabled_count(settings, routine) == 2
    settings.set("NoHero", "1")
    assert enabled_count(settings, routine) == 1
    settings.set("Chests", "0")
    assert enabled_count(settings, routine) == 0


def test_routine_shortcuts_use_real_settings_and_pages(tmp_path):
    from firestone_bot.gui.catalog import OPTIONS
    from firestone_bot.gui.pages import PAGE_ORDER

    settings = Settings(path=str(tmp_path / "settings.ini"))
    for routine in ROUTINES:
        assert routine.page in PAGE_ORDER
        assert all(key in OPTIONS for key in routine.switches)
        assert 0 <= enabled_count(settings, routine) <= len(routine.switches)
