"""Launcher search reaches the real settings, actions and information destinations."""

import pytest

from firestone_bot.gui.catalog import OPTIONS, READ_ONLY_KEYS
from firestone_bot.gui.help_text import HOME_SECTIONS
from firestone_bot.gui.search_catalog import SEARCH_TARGETS, TARGETS_BY_ID, search_launcher


def test_every_editable_and_read_only_setting_is_searchable_by_key():
    for key in set(OPTIONS) | READ_ONLY_KEYS:
        results = search_launcher(key, limit=None)
        assert any(result.key == key for result in results), key


def test_destinations_have_unique_stable_ids():
    ids = [target.id for target in SEARCH_TARGETS]
    assert len(ids) == len(set(ids)) == len(TARGETS_BY_ID)
    assert all(target.id and TARGETS_BY_ID[target.id] is target for target in SEARCH_TARGETS)


@pytest.mark.parametrize("query", ["update", "UPDATE", "  uPdÀtE  ", "launcher update"])
def test_update_search_leads_to_the_real_update_check(query):
    result = search_launcher(query)[0]
    assert (result.page, result.section, result.key) == ("workshop", "files", "check_update")


@pytest.mark.parametrize(
    "query, destination",
    [
        ("migrate", ("workshop", "files", "import")),
        ("autoscroll", ("journal", "toolbar", "follow")),
        ("Ctrl+S", ("workshop", "files", "save")),
        ("retro", ("camp", "navigation", "skin")),
        ("game runtime", ("camp", "environment", "game_uptime")),
    ],
)
def test_aliases_find_their_destination(query, destination):
    result = search_launcher(query)[0]
    assert (result.page, result.section, result.key) == destination


def test_multiword_search_is_case_insensitive_and_requires_every_word():
    results = search_launcher("  GUARDIAN   evolve  ", limit=None)
    assert results == search_launcher("guardian evolve", limit=None)
    assert results[0].key == "GuardianEvolve"
    assert all(result in search_launcher("guardian", limit=None) for result in results)
    assert all(result in search_launcher("evolve", limit=None) for result in results)
    assert search_launcher("guardian nevermatchingword") == []


@pytest.mark.parametrize("query", ["", "   ", "!?", "nevermatchingword"])
def test_empty_or_unmatched_search_has_no_destinations(query):
    assert search_launcher(query) == []


def test_full_results_are_available_without_the_default_limit():
    full = search_launcher("game", limit=None)
    assert len(full) > 30
    assert search_launcher("game") == full[:30]
    assert search_launcher("game", limit=2) == full[:2]
    assert search_launcher("game", limit=0) == []
    assert search_launcher("game", limit=-1) == []


def test_read_only_platform_and_each_help_topic_have_real_destinations():
    platform = search_launcher("LastPlatform")[0]
    assert (platform.page, platform.section, platform.key) == ("workshop", "game", "LastPlatform")
    for title, _ in HOME_SECTIONS:
        results = search_launcher(title, limit=None)
        assert any(
            result.title == title
            and result.page == "workshop"
            and result.section == "help"
            and result.id.startswith("help:")
            for result in results
        ), title
