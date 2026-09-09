"""Source coverage, real automation gates and native list/detail settings writes."""

from collections import Counter

import pytest

from firestone_bot.gui.automation_catalog import (
    AUTOMATIONS,
    CATEGORIES,
    GROUPS_BY_ID,
    WORKSHOP_GROUPS,
    disabled_reason,
    group_status,
    matches_group,
    setting_on,
)
from firestone_bot.gui.catalog import INVERTED_KEYS, OPTIONS, PRIORITY_KEYS, SELL_KEYS, WM_NONE
from firestone_bot.progress import Progress
from firestone_bot.settings import Settings


def settings(**values):
    model = Settings(path="unused-settings.ini", loaded=True)
    for key, value in values.items():
        model.set(key, str(value))
    return model


def enabled(model, group_id, key, progress=None):
    return disabled_reason(model, GROUPS_BY_ID[group_id], key, progress) is None


def test_catalog_places_every_current_option_once():
    counts = Counter(key for group in (*AUTOMATIONS, *WORKSHOP_GROUPS) for key in group.keys)
    assert set(counts) == set(OPTIONS)
    assert set(counts.values()) == {1}
    assert len(GROUPS_BY_ID) == len(AUTOMATIONS) + len(WORKSHOP_GROUPS)
    assert {group.category for group in AUTOMATIONS} == set(CATEGORIES) - {"All"}
    for group in (*AUTOMATIONS, *WORKSHOP_GROUPS):
        assert group.summary and group.title
        assert group.master is None or group.master in group.keys
        assert set(group.independent) <= set(group.keys)
        assert set(group.parents) <= set(OPTIONS)


def test_search_matches_setting_names_labels_and_all_query_words():
    engineer = GROUPS_BY_ID["engineer"]
    assert matches_group(engineer, "Blueprints", "Develop")
    assert matches_group(engineer, "war engineer")
    assert not matches_group(engineer, "Blueprints", "Trade")
    assert not matches_group(engineer, "war alchemy")
    assert matches_group(GROUPS_BY_ID["chests"], "Keep jewel chests")
    assert matches_group(GROUPS_BY_ID["tree"], "PTree")


@pytest.mark.parametrize("key", sorted(INVERTED_KEYS))
def test_inverted_options_have_positive_enabled_meaning(key):
    model = settings(**{key: "0"})
    assert setting_on(model, key)
    model.set(key, "1")
    assert not setting_on(model, key)


def test_chest_controls_follow_independent_gifts_and_blessing_paths():
    model = settings(Chests=0, Bless=1, BlessingChests=1)
    assert not enabled(model, "chests", "GearChestExclude")
    assert not enabled(model, "chests", "JewelChestExclude")
    for key in ("OracleGifts", "MysteryBoxes", "BlessingChests", "CelestialChestExclude"):
        assert enabled(model, "chests", key)
    model.set("Chests", "1")
    assert not enabled(model, "chests", "BlessingChests")
    assert enabled(model, "chests", "CelestialChestExclude")
    model.set("Bless", "0")
    assert not enabled(model, "chests", "CelestialChestExclude")
    assert enabled(model, "chests", "OracleGifts")


def test_oracle_blessing_bag_option_survives_oracle_switch_and_level_lock():
    model = settings(SkipOracle=1, Bless=1)
    progress = Progress(account_level=12)
    assert enabled(model, "oracle", "Bless", progress)
    assert not enabled(model, "oracle", "Rituals", progress)
    assert group_status(model, GROUPS_BY_ID["oracle"], progress) == "Partly enabled"


def test_guardian_order_can_run_through_either_real_path():
    model = settings(GuardianVisit=0, NoGuild=0, Chaos=1, GuardianChaosUpgrades=1)
    assert enabled(model, "guardians", "ChaosGuardianOrder")
    model.set("NoGuild", "1")
    assert not enabled(model, "guardians", "ChaosGuardianOrder")
    model.set("GuardianVisit", "1")
    assert enabled(model, "guardians", "ChaosGuardianOrder")
    model.set("GuardianChaosUpgrades", "0")
    assert not enabled(model, "guardians", "ChaosGuardianOrder")
    model.set("GuardianTraining", "0")
    assert not enabled(model, "guardians", "GuardianTrain")


def test_guild_and_campaign_dependencies_do_not_erase_children():
    model = settings(NoGuild=1, Chaos=1, ChaosBooks=1, MapMissions=1, Campaign=1, Liberation=0)
    before = dict(model.values)
    for group, key in (("chaos", "ChaosBooks"), ("tree", "PTree"), ("awakening", "Awaken")):
        assert not enabled(model, group, key)
    assert not enabled(model, "campaign", "DungeonQuest")
    assert model.values == before
    model.set("Liberation", "1")
    assert enabled(model, "campaign", "DungeonQuest")
    model.set("MapMissions", "0")
    assert not enabled(model, "campaign", "Campaign")


def test_scarab_claim_and_artifact_crafting_are_independent_of_play():
    model = settings(Beer=1, Scarab=1, Token=0)
    assert enabled(model, "scarab", "ScarabTokenClaim")
    assert not enabled(model, "scarab", "MaxScarab")
    assert not enabled(model, "tavern", "CraftArtifact")
    model.set("Beer", "0")
    assert enabled(model, "tavern", "CraftArtifact")
    assert not enabled(model, "tavern", "MaxTokens")


def test_engineer_and_map_controls_follow_execution_modes():
    model = settings(NoEng=0, UpgradeWM=WM_NONE, MapMissions=1, MapMode="detect")
    assert not enabled(model, "engineer", "WMOptions")
    model.set("UpgradeWM", "Upgrade Aegis")
    model.set("WMOptions", "Level Only")
    assert enabled(model, "engineer", "WMOptions")
    assert not enabled(model, "engineer", "Blueprints")
    model.set("WMOptions", "Blueprints Only")
    assert enabled(model, "engineer", "Blueprints")
    assert all(not enabled(model, "map", key) for key in PRIORITY_KEYS)
    model.set("MapMode", "coordinates")
    assert all(enabled(model, "map", key) for key in PRIORITY_KEYS)


def test_known_level_locks_preserve_configuration_and_unknown_levels_do_not_gate():
    model = settings(Crystal=1, NoGuild=0, MaxCrystals=17)
    before = dict(model.values)
    assert not enabled(model, "crystal", "MaxCrystals", Progress(account_level=49, guild_level=5))
    assert not enabled(model, "crystal", "MaxCrystals", Progress(account_level=200, guild_level=4))
    assert enabled(model, "crystal", "MaxCrystals", Progress())
    assert model.values == before
    assert not enabled(model, "merchant", "BuyEx", Progress(account_level=64))
    assert enabled(model, "merchant", "SellEx", Progress(account_level=64))


def test_compatibility_is_read_only_and_restart_test_requires_restarts():
    model = settings(RestartGame=0)
    assert not enabled(model, "restart", "RestartGameTime")
    assert not enabled(model, "restart", "RestartGameTest")
    model.set("RestartGame", "1")
    assert enabled(model, "restart", "RestartGameTest")
    assert not enabled(model, "compatibility", "Talents450")
    assert not enabled(model, "compatibility", "Talents800")


def test_map_key_only_applies_when_keyboard_opening_can_be_used():
    model = settings(MapOpen="icon", InterfaceStyle="new")
    assert not enabled(model, "map", "MapHotkey")
    model.set("MapOpen", "hotkey")
    assert enabled(model, "map", "MapHotkey")
    model.set("MapOpen", "auto")
    assert not enabled(model, "map", "MapHotkey")
    model.set("InterfaceStyle", "classic")
    assert enabled(model, "map", "MapHotkey")


def test_native_editors_write_live_settings_cache_views_and_release_observers(tmp_path):
    """No game input is connected: exercise real controls with an isolated settings file."""
    import tkinter as tk
    from types import SimpleNamespace

    ctk = pytest.importorskip("customtkinter")
    from firestone_bot.gui import theme
    from firestone_bot.gui.binding import Binder
    from firestone_bot.gui.context import PageContext
    from firestone_bot.gui.pages.automations import AutomationsPage

    theme.set_skin("Fieldbook")
    try:
        root = ctk.CTk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    root.geometry("1280x850")
    errors = []
    root.report_callback_exception = lambda *exc: errors.append(exc)
    model = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
    binder = Binder(model, root, lambda *_: None, save_delay_ms=60000)
    ticks = []

    def register_tick(callback):
        ticks.append(callback)
        return lambda: ticks.remove(callback) if callback in ticks else None

    ctx = PageContext(
        settings=model,
        binder=binder,
        callbacks={},
        show_page=lambda *_: None,
        base_dir=str(tmp_path),
        register_tick=register_tick,
        root=root,
        window=SimpleNamespace(gui_state={}),
    )
    page = None
    try:
        page = AutomationsPage(root, ctx)
        page.pack(fill="both", expand=True)
        root.update()
        alchemy = page.editors["alchemy"]
        alchemy.rows["Alch"].control.widget.deselect()
        root.update()
        assert model.get("Alch") == "1"
        assert alchemy.rows["Coin"].control.widget.cget("state") == "disabled"
        alchemy.rows["Alch"].control.widget.select()
        root.update()
        assert model.get("Alch") == "0"
        assert alchemy.rows["Coin"].control.widget.cget("state") == "normal"
        page.open_group("guardians")
        root.update()
        guardian = page.editors["guardians"]
        assert model.get("GuardianTrain") == "Vermilion"
        assert guardian.rows["GuardianTrain"].control.widget.get() == "(unknown) Vermilion"
        page.open_group("merchant")
        radio = page.editors["merchant"].composites["selling"][0].control
        radio.var.set("SellNoGold")
        radio._changed()
        assert {key: model.get(key) for key in SELL_KEYS} == {
            "SellScrolls": "0",
            "SellNoGold": "1",
            "SellAll": "0",
            "SellNone": "0",
        }
        page.open_group("map")
        ordered = page.editors["map"].composites["priority"][0]
        before = [model.get(key) for key in PRIORITY_KEYS]
        ordered._move(0, 1)
        assert [model.get(key) for key in PRIORITY_KEYS] == [before[1], before[0], *before[2:]]
        binder.var("MapMode").set("detect")
        root.update()
        assert all(button.cget("state") == "disabled" for button in ordered.buttons)
        assert page.editors["map"].reset_order_button.cget("state") == "disabled"
        page.query.set("no matching setting")
        root.update()
        assert not errors, [(kind.__name__, str(error)) for kind, error, _ in errors]
        assert page.empty_label.winfo_ismapped()
        page.open_group("alchemy")
        root.update()
        assert page.selected == "alchemy" and page.query.get() == ""
        trace_counts = {key: len(var.trace_info()) for key, (var, _) in binder._vars.items()}
        for _ in range(3):
            page.open_group("merchant")
            page.open_group("alchemy")
        assert page.editors["alchemy"] is alchemy
        assert trace_counts == {
            key: len(var.trace_info()) for key, (var, _) in binder._vars.items()
        }
        # At the supported compact window size the settings remain inside the inspector.
        root.geometry("980x780")
        root.update()
        for group in AUTOMATIONS:
            page.open_group(group.id)
            root.update()
            editor = page.editors[group.id]
            canvas = page.inspector._parent_canvas
            right_edge = canvas.winfo_rootx() + canvas.winfo_width()
            for row in editor.rows.values():
                control = row.control_widget
                assert control.winfo_rootx() + control.winfo_width() <= right_edge, group.id
        root.update()
        assert len(page.editors) == len(AUTOMATIONS)
        assert binder.keys() == {key for group in AUTOMATIONS for key in group.keys}
        assert not errors
        search_query = page.query
        page.destroy()
        page = None
        binder.release_view()
        assert not search_query.trace_info()
        assert not ticks and not binder._reload_hooks
        assert all(len(var.trace_info()) == 1 for var, _ in binder._vars.values())
        binder.var("MapMode").set("coordinates")
        binder.flush()
        binder.reload()
        root.update()
        assert model.get("MapMode") == "coordinates"
        assert not errors
    finally:
        if page is not None:
            page.destroy()
        binder.flush()
        root.destroy()
