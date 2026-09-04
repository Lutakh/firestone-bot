"""GUI catalog (Tk-free): key coverage, choice lists, validators, formatters."""

from firestone_bot.gui import catalog
from firestone_bot.gui.catalog import (
    BLUEPRINT_CHOICES,
    CELESTIAL_CHOICES,
    DELAY_CHOICES,
    GEAR_CHOICES,
    INVERTED_KEYS,
    JEWEL_CHOICES,
    KINDS,
    OPTIONS,
    PRIORITY_CHOICES,
    READ_ONLY_KEYS,
    WM_CHOICES,
    WM_MODE_CHOICES,
    format_ahk_stamp,
    is_permutation,
    parse_order,
)
from firestone_bot.runner import END_OF_CYCLE_DELAYS
from firestone_bot.settings import EXTRA_SETTINGS, SETTINGS_MAP


def test_every_key_is_editable_or_read_only():
    assert set(OPTIONS) | READ_ONLY_KEYS == set(SETTINGS_MAP) | set(EXTRA_SETTINGS)
    assert not set(OPTIONS) & READ_ONLY_KEYS
    assert len(OPTIONS) == 92 and len(READ_ONLY_KEYS) == 8


def test_options_have_label_help_and_kind():
    for key, opt in OPTIONS.items():
        assert opt.label.strip(), key
        assert opt.help.strip(), key
        assert opt.kind in KINDS, key
        if opt.kind in ("choice", "seg", "ordered") and key not in ("Talents450", "Talents800"):
            assert opt.values, key


def test_inverted_keys_are_switches():
    assert INVERTED_KEYS <= set(OPTIONS)
    for key in INVERTED_KEYS:
        assert OPTIONS[key].kind == "switch"
        assert f"{key}=0 when on" in OPTIONS[key].help


def test_choice_lists_match_gui_ahk():
    assert "Upgrade FireCracker" in WM_CHOICES and WM_CHOICES[0] == "Don't Upgrade WM's"
    assert len(WM_CHOICES) == 14
    assert GEAR_CHOICES[-1] == "Titan" and GEAR_CHOICES[:2] == ["Exclude All", "Don't Exclude Any"]
    assert JEWEL_CHOICES[-1] == "Platinum" and CELESTIAL_CHOICES[-1] == "Galaxy"
    assert PRIORITY_CHOICES == ["2 Squad", "War", "Medium", "Short", "Leftover"]
    assert WM_MODE_CHOICES == ["Blueprints Only", "Level Only", "Level and Blueprints"]
    assert "Health Only" in BLUEPRINT_CHOICES and "Armor Only" in BLUEPRINT_CHOICES
    assert DELAY_CHOICES == list(END_OF_CYCLE_DELAYS)
    for key, default in SETTINGS_MAP.items():
        opt = OPTIONS.get(key)
        # GuardianTrain: legacy 'Vermilion' default; ChaosGuardianOrder: comma list
        if opt and opt.values and key not in ("GuardianTrain", "ChaosGuardianOrder"):
            assert default[1] in opt.values, key


def test_order_validators():
    assert parse_order("3,1,2,4", catalog.CHAOS_GUARDIAN_CHOICES) == ["3", "1", "2", "4"]
    assert parse_order(" 1, 2,3,4 ", catalog.CHAOS_GUARDIAN_CHOICES) == ["1", "2", "3", "4"]
    assert parse_order("1,1,2,3", catalog.CHAOS_GUARDIAN_CHOICES) == []
    assert parse_order("1,2,3", catalog.CHAOS_GUARDIAN_CHOICES) == []
    assert parse_order("", catalog.CHAOS_GUARDIAN_CHOICES) == []
    assert is_permutation(["War", "2 Squad", "Leftover", "Short", "Medium"], PRIORITY_CHOICES)
    assert not is_permutation(["War", "War", "Leftover", "Short", "Medium"], PRIORITY_CHOICES)


def test_ahk_stamp_formatter():
    assert format_ahk_stamp("") == "never"
    assert format_ahk_stamp("garbage") == "never"
    assert format_ahk_stamp("20260904100312") == "2026-09-04 10:03"
    assert format_ahk_stamp("", "not detected yet") == "not detected yet"
