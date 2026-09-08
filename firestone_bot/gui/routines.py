"""Overview shortcuts and truthful summaries of the saved routine configuration."""

from dataclasses import dataclass

from firestone_bot.gui.catalog import INVERTED_KEYS


@dataclass(frozen=True)
class Routine:
    page: str
    title: str
    description: str
    switches: tuple[str, ...]


ROUTINES = (
    Routine(
        "town",
        "Town",
        "Guardians, tavern and alchemy",
        (
            "GuardianVisit",
            "Token",
            "Beer",
            "Scarab",
            "SkipOracle",
            "NoEng",
            "SellEx",
            "PVP",
            "Alch",
            "Research",
        ),
    ),
    Routine(
        "guild", "Guild & tree", "Chaos rift, expeditions and personal tree", ("NoGuild", "PTree")
    ),
    Routine(
        "missions",
        "Missions",
        "Map missions and war machines",
        ("MapMissions", "Liberation", "DungeonQuest"),
    ),
    Routine(
        "main",
        "Heroes & chests",
        "Rewards, chest opening and hero upgrades",
        ("Events", "BattlePass", "Quests", "Mail", "Shop", "Chests", "NoHero"),
    ),
)


def enabled_count(settings, routine: Routine) -> int:
    """Count configured top-level switches, not live or completed game actions."""
    return sum(
        not settings.flag(key) if key in INVERTED_KEYS else settings.flag(key)
        for key in routine.switches
    )
