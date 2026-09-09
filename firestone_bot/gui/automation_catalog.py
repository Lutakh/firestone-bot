"""Source-backed navigation and dependency rules for the automation editors.

Only presentation is grouped here. The runner keeps its existing execution sequence and
Settings remains the authority for saved values, including inverted and legacy options.
"""

from __future__ import annotations

from dataclasses import dataclass

from firestone_bot.gui.catalog import INVERTED_KEYS, OPTIONS, PRIORITY_KEYS, WM_NONE
from firestone_bot.progress import Progress
from firestone_bot.settings import Settings


@dataclass(frozen=True)
class AutomationGroup:
    id: str
    title: str
    category: str
    context: str
    summary: str
    keys: tuple[str, ...]
    master: str | None = None
    parents: tuple[str, ...] = ()
    independent: tuple[str, ...] = ()
    legacy: bool = False
    feature: str | None = None


CATEGORIES = ("All", "Collect", "Develop", "Expeditions", "Trade")

AUTOMATIONS: tuple[AutomationGroup, ...] = (
    AutomationGroup(
        id="daily_rewards",
        title="Events & rewards",
        category="Collect",
        context="Main screen",
        summary="Claim available event, battle pass, quest, daily check-in and free shop rewards.",
        keys=("Events", "BattlePass", "Quests", "Shop"),
    ),
    AutomationGroup(
        id="mail",
        title="Mailbox",
        category="Collect",
        context="Main screen",
        summary="Collect mailbox rewards and choose whether to delete read mail.",
        keys=("Mail", "MailDelete"),
        master="Mail",
    ),
    AutomationGroup(
        id="chests",
        title="Chests & gifts",
        category="Collect",
        context="Main screen",
        summary="Choose chest exclusions and control oracle gifts, mystery boxes and celestial chests.",
        keys=(
            "Chests",
            "GearChestExclude",
            "JewelChestExclude",
            "CelestialChestExclude",
            "BlessingChests",
            "OracleGifts",
            "MysteryBoxes",
        ),
        master="Chests",
        independent=("BlessingChests", "CelestialChestExclude", "OracleGifts", "MysteryBoxes"),
    ),
    AutomationGroup(
        id="heroes",
        title="Hero upgrades",
        category="Develop",
        context="End of cycle",
        summary="Choose the heroes and special targets to upgrade, with optional milestone upgrades.",
        keys=(
            "NoHero",
            "NextMilestone",
            "UpgradeSpecial",
            "UpgradeGuardian",
            "UpgradeH1",
            "UpgradeH2",
            "UpgradeH3",
            "UpgradeH4",
            "UpgradeH5",
        ),
        master="NoHero",
    ),
    AutomationGroup(
        id="guardians",
        title="Guardian training",
        category="Develop",
        context="Town",
        summary="Train and evolve guardians, and choose the order for spending chaos-rift rewards.",
        keys=(
            "GuardianVisit",
            "GuardianEvolve",
            "GuardianTraining",
            "GuardianTrain",
            "GuardianChaosUpgrades",
            "ChaosGuardianOrder",
        ),
        master="GuardianVisit",
        independent=("GuardianChaosUpgrades", "ChaosGuardianOrder"),
    ),
    AutomationGroup(
        id="oracle",
        title="Oracle & blessings",
        category="Develop",
        context="Town",
        summary="Collect oracle rewards, perform rituals and upgrade blessings.",
        keys=("SkipOracle", "Rituals", "Bless", "DailyOracle"),
        master="SkipOracle",
        independent=("Bless",),
        feature="oracle",
    ),
    AutomationGroup(
        id="engineer",
        title="Engineer & war machines",
        category="Develop",
        context="Town",
        summary="Collect tools and configure upgrades for a selected war machine.",
        keys=("NoEng", "EngineerTools", "UpgradeWM", "WMOptions", "Blueprints"),
        master="NoEng",
        feature="engineer",
    ),
    AutomationGroup(
        id="alchemy",
        title="Alchemy",
        category="Develop",
        context="Town",
        summary="Collect completed experiments and choose which resources to spend on new ones.",
        keys=("Alch", "AlchCollect", "DragonBlood", "Dust", "Coin"),
        master="Alch",
        feature="alchemist",
    ),
    AutomationGroup(
        id="research",
        title="Research",
        category="Develop",
        context="Town",
        summary="Start the next research when a research slot is available.",
        keys=("Research",),
        master="Research",
    ),
    AutomationGroup(
        id="awakening",
        title="Hero awakening",
        category="Develop",
        context="Guild",
        summary="Enable hero awakening during guild visits when the feature is unlocked.",
        keys=("Awaken",),
        master="Awaken",
        parents=("NoGuild",),
        feature="guild_awaken",
    ),
    AutomationGroup(
        id="tree",
        title="Personal tree",
        category="Develop",
        context="Guild",
        summary="Choose which personal tree attributes, specializations and classes to upgrade.",
        keys=(
            "PTree",
            "AttDmg",
            "AttHp",
            "AttArm",
            "Energy",
            "Mana",
            "Rage",
            "Miner",
            "MainAtt",
            "Battle",
            "Prest",
            "Fire",
            "Gold",
            "Level",
            "Guard",
            "Fist",
            "Prec",
            "Magic",
            "Tank",
            "Damage",
            "Heal",
        ),
        master="PTree",
        parents=("NoGuild",),
    ),
    AutomationGroup(
        id="map",
        title="Map missions",
        category="Expeditions",
        context="World map",
        summary="Claim and dispatch missions. Choose fixed coordinates or detection from screen icons.",
        keys=(
            "MapMissions",
            "MapOpen",
            "MapHotkey",
            "MapMode",
            "Priority1",
            "Priority2",
            "Priority3",
            "Priority4",
            "Priority5",
            "MapReset",
        ),
        master="MapMissions",
    ),
    AutomationGroup(
        id="campaign",
        title="Campaign",
        category="Expeditions",
        context="World map",
        summary="Collect campaign rewards and control liberation and dungeon missions.",
        keys=("Campaign", "Liberation", "DungeonQuest"),
        master="Campaign",
        parents=("MapMissions",),
    ),
    AutomationGroup(
        id="guild",
        title="Guild visits",
        category="Expeditions",
        context="Guild",
        summary="Control the guild visit, expeditions, notifications and pickaxe collection.",
        keys=("NoGuild", "GuildExpedition", "GNotif", "Pickaxes"),
        master="NoGuild",
    ),
    AutomationGroup(
        id="chaos",
        title="Chaos rift",
        category="Expeditions",
        context="Guild",
        summary="Use free chaos tokens, set a daily hit limit and choose whether to buy books.",
        keys=("Chaos", "MaxChaos", "ChaosBooks"),
        master="Chaos",
        parents=("NoGuild",),
        feature="guild_chaos",
    ),
    AutomationGroup(
        id="crystal",
        title="Arcane crystal",
        category="Expeditions",
        context="Guild",
        summary="Spend pickaxes on the arcane crystal, up to your daily limit.",
        keys=("Crystal", "MaxCrystals"),
        master="Crystal",
        parents=("NoGuild",),
        feature="guild_crystal",
    ),
    AutomationGroup(
        id="arena",
        title="Arena battles",
        category="Expeditions",
        context="Town",
        summary="Run the five daily arena battles through the existing arena routine.",
        keys=("PVP",),
        master="PVP",
        feature="arena",
    ),
    AutomationGroup(
        id="scarab",
        title="Scarab game",
        category="Expeditions",
        context="Tavern",
        summary="Claim Pharaoh tokens and choose a daily limit for scarab plays.",
        keys=("ScarabTokenClaim", "Scarab", "MaxScarab"),
        master="Scarab",
        independent=("ScarabTokenClaim",),
        feature="scarab",
    ),
    AutomationGroup(
        id="tavern",
        title="Tavern & artifacts",
        category="Trade",
        context="Tavern",
        summary="Exchange beer for tokens, play tokens and craft artifacts.",
        keys=("Beer", "TavernBeerTokens", "Token", "MaxTokens", "CraftArtifact"),
        master="Beer",
    ),
    AutomationGroup(
        id="merchant",
        title="Exotic merchant",
        category="Trade",
        context="Town",
        summary="Choose a selling strategy, exotic upgrades and chest purchases.",
        keys=(
            "SellEx",
            "SellScrolls",
            "SellNoGold",
            "SellAll",
            "SellNone",
            "ExoticUpgrades",
            "BuyEx",
        ),
        master="SellEx",
    ),
)

WORKSHOP_GROUPS: tuple[AutomationGroup, ...] = (
    AutomationGroup(
        id="session",
        title="Run behavior",
        category="Workshop",
        context="Application",
        summary="Set the pause between cycles, timing mode and the loop safety cap.",
        keys=("Delay", "Timing", "SafetyCap"),
    ),
    AutomationGroup(
        id="game",
        title="Game setup",
        category="Workshop",
        context="Application",
        summary="Choose the game platform and the in-game interface layout used by the bot.",
        keys=("GamePlatform", "InterfaceStyle", "DisableWarning"),
    ),
    AutomationGroup(
        id="restart",
        title="Game restart",
        category="Workshop",
        context="Application",
        summary="Configure periodic game restarts and the restart test option.",
        keys=("RestartGame", "RestartGameTime", "RestartGameTest"),
        master="RestartGame",
    ),
    AutomationGroup(
        id="interruption",
        title="Input & notifications",
        category="Workshop",
        context="Application",
        summary="Control mouse interruption, notification dismissal and the status overlay.",
        keys=("MouseGuard", "CloseNotifications", "Overlay"),
    ),
    AutomationGroup(
        id="heartbeat",
        title="Heartbeat",
        category="Workshop",
        context="Application",
        summary="Configure the existing heartbeat and its Discord identifier.",
        keys=("EnableHeartbeat", "DiscordID"),
        master="EnableHeartbeat",
    ),
    AutomationGroup(
        id="compatibility",
        title="Compatibility",
        category="Workshop",
        context="Application",
        summary="Legacy talent choices retained by the settings format.",
        keys=("Talents450", "Talents800"),
        legacy=True,
    ),
)

GROUPS_BY_ID = {group.id: group for group in (*AUTOMATIONS, *WORKSHOP_GROUPS)}


def setting_on(settings: Settings, key: str) -> bool:
    """Positive UI meaning of a switch, regardless of the historical INI key name."""
    return not settings.flag(key) if key in INVERTED_KEYS else settings.flag(key)


def matches_group(group: AutomationGroup, query: str, category: str = "All") -> bool:
    if category != "All" and group.category != category:
        return False
    text = " ".join(
        (
            group.title,
            group.summary,
            group.context,
            *group.keys,
            *(OPTIONS[key].label for key in group.keys),
        )
    ).casefold()
    return all(word in text for word in query.casefold().split())


def disabled_reason(
    settings: Settings,
    group: AutomationGroup,
    key: str,
    progress: Progress | None = None,
) -> str | None:
    """Why a control currently has no effect; never changes a stored option.

    The two guardian-upgrade paths and the independent bag/oracle options deliberately
    do not use a simple parent/master hierarchy. Their rules mirror runner.py and bag_plan.
    Unknown account levels do not gate settings, just as they do not gate the runner.
    """
    if group.legacy:
        return "Kept for settings compatibility; the Python bot does not use this option."

    def on(name: str) -> bool:
        return setting_on(settings, name)

    if progress:
        feature = group.feature
        if key == "BuyEx":
            feature = "emblem_chests"
        if group.id == "oracle" and key == "Bless":
            feature = None  # still controls the main-screen celestial chest visit
        if feature and (reason := progress.locked_reason(feature)):
            return f"Locked: {reason}. Your saved choice is retained."
    for parent in group.parents:
        if not on(parent):
            return f"Turn on {OPTIONS[parent].label.lower()} to use this option."
    if key in ("GuardianChaosUpgrades", "ChaosGuardianOrder"):
        guardian_path = on("GuardianVisit")
        chaos_path = on("NoGuild") and on("Chaos")
        if progress and progress.locked_reason("guild_chaos"):
            chaos_path = False
        if not (guardian_path or chaos_path):
            return "Enable guardian visits or guild chaos-rift hits to spend these rewards."
        if key == "ChaosGuardianOrder" and not on("GuardianChaosUpgrades"):
            return "Turn on spending chaos-rift rewards to use the upgrade order."
        return None
    if (
        group.master
        and key != group.master
        and key not in group.independent
        and not on(group.master)
    ):
        return f"Turn on {OPTIONS[group.master].label.lower()} to use this option."
    if key == "GuardianTrain" and not on("GuardianTraining"):
        return "Turn on guardian training to choose which guardian is trained."
    if key == "MapHotkey" and (
        settings.get("MapOpen") == "icon"
        or (settings.get("MapOpen") == "auto" and settings.get("InterfaceStyle") == "new")
    ):
        return "The shortcut key is used only when the map is opened with the keyboard."
    if key in PRIORITY_KEYS and settings.get("MapMode") == "detect":
        return (
            "Detection mode reads visible mission icons; category priority uses coordinates mode."
        )
    if key == "DungeonQuest" and not on("Liberation"):
        return "Turn on liberation missions to include dungeon missions."
    if key in ("WMOptions", "Blueprints") and settings.get("UpgradeWM") == WM_NONE:
        return "Choose a war machine to configure its upgrades."
    if key == "Blueprints" and settings.get("WMOptions") == "Level Only":
        return "Blueprint choices are used when the upgrade mode includes blueprints."
    if key == "MaxTokens" and not on("Token"):
        return "Turn on tavern token play to use the daily limit."
    if key == "BlessingChests":
        if on("Chests"):
            return "This extra option is used only while Open chests is off."
        if not on("Bless"):
            return "Turn on Upgrade blessings in Oracle & blessings to open celestial chests."
    if key == "CelestialChestExclude" and not (
        on("Bless") and (on("Chests") or on("BlessingChests"))
    ):
        return "Celestial chests need Upgrade blessings and either chest-opening option."
    return None


def group_status(
    settings: Settings, group: AutomationGroup, progress: Progress | None = None
) -> str:
    """Configuration status, never a claim that an automation is currently running."""
    switches = [key for key in group.keys if OPTIONS[key].kind in ("switch", "check")]
    enabled = [
        key
        for key in switches
        if setting_on(settings, key) and disabled_reason(settings, group, key, progress) is None
    ]
    if group.feature and progress and progress.locked_reason(group.feature):
        return "Partly enabled" if enabled else "Locked"
    if group.master and setting_on(settings, group.master) and group.master in enabled:
        return "Enabled"
    if enabled:
        return "Partly enabled" if group.master else "Enabled"
    return "Off"
