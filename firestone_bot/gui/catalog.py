"""GUI catalog: choice lists, option metadata and validators. Tk-free so tests can import it.

`OPTIONS` describes every editable settings key (label, help line, control kind and, when
relevant, the choice list). `READ_ONLY_KEYS` are the runtime counters shown but never bound.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from firestone_bot.runner import END_OF_CYCLE_DELAYS
from firestone_bot.settings import SETTINGS_MAP

GEAR_CHOICES = [
    "Exclude All",
    "Don't Exclude Any",
    "Epic and Higher",
    "Legendary and Higher",
    "Mythic and Higher",
    "Titan",
]
JEWEL_CHOICES = [
    "Exclude All",
    "Don't Exclude Any",
    "Diamond and Higher",
    "Opal and Higher",
    "Emerald and Higher",
    "Platinum",
]
CELESTIAL_CHOICES = [
    "Exclude All",
    "Don't Exclude Any",
    "Solar and Higher",
    "Nebula and Higher",
    "Cosmic and Higher",
    "Galaxy",
]
PRIORITY_CHOICES = ["2 Squad", "War", "Medium", "Short", "Leftover"]
WM_NONE = "Don't Upgrade WM's"
WM_CHOICES = [WM_NONE] + [
    f"Upgrade {n}"
    for n in (
        "Aegis",
        "Cloudfist",
        "Curator",
        "Earthshatterer",
        "FireCracker",  # sic, as in Gui.ahk
        "Fortress",
        "Goliath",
        "Harvester",
        "Hunter",
        "Judgement",
        "Sentinel",
        "Talos",
        "Thunderclap",
    )
]
WM_MODE_CHOICES = ["Blueprints Only", "Level Only", "Level and Blueprints"]
BLUEPRINT_CHOICES = [
    "Upgrade All",
    "Damage Only",
    "Health Only",
    "Armor Only",
    "Damage and Health",
    "Damage and Armor",
    "Health and Armor",
]
DELAY_CHOICES = list(END_OF_CYCLE_DELAYS)  # "0", "30", ... "600"
DELAY_DISPLAY = {
    "0": "none",
    "30": "30 s",
    "60": "1 min",
    "90": "1 min 30",
    "120": "2 min",
    "300": "5 min",
    "600": "10 min",
}
RESTART_HOURS = ["6", "12", "18", "24"]
RESTART_DISPLAY = {h: f"{h} h" for h in RESTART_HOURS}
GUARDIAN_LEVELS = ["1", "2", "3", "4"]
GUARDIAN_DISPLAY = {n: f"Level {n}" for n in GUARDIAN_LEVELS}
CHAOS_GUARDIAN_CHOICES = ["1", "2", "3", "4"]
SELL_KEYS = ["SellScrolls", "SellNoGold", "SellAll", "SellNone"]
# features/exotic_merchant.py checks the flags in this order when several are set.
SELL_PRECEDENCE = ["SellAll", "SellNoGold", "SellScrolls", "SellNone"]
SELL_LABELS = [
    "Sell only exotic scrolls",
    "Sell everything except gold items",
    "Sell all exotic items",
    "Sell nothing",
]
PRIORITY_KEYS = [f"Priority{i}" for i in range(1, 6)]
HERO_TARGET_KEYS = ["UpgradeSpecial", "UpgradeGuardian"] + [f"UpgradeH{i}" for i in range(1, 6)]
TREE_GROUPS: dict[str, list[str]] = {
    "Attributes & heroes": [
        "AttDmg",
        "AttHp",
        "AttArm",
        "Energy",
        "Mana",
        "Rage",
        "Miner",
        "MainAtt",
    ],
    "Specializations": ["Battle", "Prest", "Fire", "Gold", "Level", "Guard", "Fist", "Prec"],
    "Classes": ["Magic", "Tank", "Damage", "Heal"],
}
TREE_KEYS = [k for keys in TREE_GROUPS.values() for k in keys]

READ_ONLY_KEYS = {
    "TokenCountDaily",
    "LastTokenReset",
    "ArenaDoneDaily",
    "ChaosCountDaily",
    "LastChaosReset",
    "ChaosBooksDaily",
    "CrystalCountDaily",
    "ScarabCountDaily",
    "ClientID",
}

# Switches shown as "ON = the bot does it" although the ini key means "skip"/"don't".
INVERTED_KEYS = {
    "NoHero",
    "NoGuild",
    "NoEng",
    "Alch",
    "Research",
    "SkipOracle",
    "Beer",
    "Scarab",
    "Pickaxes",
    "Dust",
    "DragonBlood",
}

# Control kinds: switch, check, choice, seg, num, text, radio, ordered.
KINDS = {"switch", "check", "choice", "seg", "num", "text", "radio", "ordered"}


@dataclass(frozen=True)
class Option:
    label: str
    help: str
    kind: str
    values: tuple[str, ...] = ()
    display: dict[str, str] = field(default_factory=dict)
    zero_means: str | None = None
    pattern: str | None = None
    warn: bool = False  # help line in WARN colour (spends resources / kills the game)


def _inv(key: str) -> str:
    return f"settings.ini: {key}=0 when on."


OPTIONS: dict[str, Option] = {
    # -- Main screen ---------------------------------------------------------------------
    "Events": Option(
        "Claim basic events", "Collects the event rewards shown on the main screen.", "switch"
    ),
    "Quests": Option(
        "Claim quests", "Claims completed quests, then returns to the main screen.", "switch"
    ),
    "Mail": Option("Check mail", "Opens the mailbox and claims everything.", "switch"),
    "Shop": Option(
        "Daily check-in and free gift",
        "The shop is always visited to detect the daily reset; this also claims the check-in "
        "reward and the free gift.",
        "switch",
    ),
    "Chests": Option(
        "Open chests", "Opens gear, jewel and celestial chests from the bag.", "switch"
    ),
    "GearChestExclude": Option(
        "Keep gear chests",
        "Chests of this rarity and above stay closed (Exclude All = open none, "
        "Don't Exclude Any = open everything).",
        "choice",
        tuple(GEAR_CHOICES),
    ),
    "JewelChestExclude": Option(
        "Keep jewel chests",
        "Chests of this rarity and above stay closed (Exclude All = open none, "
        "Don't Exclude Any = open everything).",
        "choice",
        tuple(JEWEL_CHOICES),
    ),
    "CelestialChestExclude": Option(
        "Keep celestial chests",
        "Chests of this rarity and above stay closed (Exclude All = open none, "
        "Don't Exclude Any = open everything).",
        "choice",
        tuple(CELESTIAL_CHOICES),
    ),
    "BlessingChests": Option(
        "Open blessing chests even when chests are off",
        "Only used when Open chests is OFF and Upgrade blessings (Town > Oracle) is ON.",
        "switch",
    ),
    "NoHero": Option(
        "Upgrade heroes",
        "Runs after the map, at the end of every cycle. " + _inv("NoHero"),
        "switch",
    ),
    "NextMilestone": Option(
        "Upgrade to the next milestone",
        "Uses the milestone button instead of single levels.",
        "switch",
    ),
    "UpgradeSpecial": Option("Special upgrade", "Hero panel row.", "check"),
    "UpgradeGuardian": Option("Guardian", "Hero panel row.", "check"),
    "UpgradeH1": Option("Hero slot 1", "Hero panel row.", "check"),
    "UpgradeH2": Option("Hero slot 2", "Hero panel row.", "check"),
    "UpgradeH3": Option("Hero slot 3", "Hero panel row.", "check"),
    "UpgradeH4": Option("Hero slot 4", "Hero panel row.", "check"),
    "UpgradeH5": Option("Hero slot 5", "Hero panel row.", "check"),
    # -- Town ------------------------------------------------------------------------------
    "GuardianTrain": Option(
        "Training level",
        "Which training option is selected (the bot presses Right N-1 times). A legacy value "
        "such as 'Vermilion' behaves like Level 1 and is kept until you pick one.",
        "seg",
        tuple(GUARDIAN_LEVELS),
        GUARDIAN_DISPLAY,
    ),
    "ChaosGuardianOrder": Option(
        "Chaos-rift upgrade order",
        "Roster order used when spending chaos-rift rewards on the guardian chaos tab "
        "(e.g. 3,1,2,4). Only used when Guild > Chaos rift is on.",
        "ordered",
        tuple(CHAOS_GUARDIAN_CHOICES),
        {n: f"Guardian {n}" for n in CHAOS_GUARDIAN_CHOICES},
    ),
    "Token": Option(
        "Use tavern tokens", "Spends the free tavern tokens (artifact rolls) each visit.", "switch"
    ),
    "MaxTokens": Option(
        "Tokens per day", "Daily cap; resets with the daily shop.", "num", zero_means="0 = no limit"
    ),
    "Beer": Option("Claim beer", _inv("Beer"), "switch"),
    "Scarab": Option("Play the scarab game", _inv("Scarab"), "switch"),
    "MaxScarab": Option(
        "Scarab plays per day", "Free-token plays only.", "num", zero_means="0 = no limit"
    ),
    "SkipOracle": Option(
        "Visit the oracle", "Claims ready rituals. " + _inv("SkipOracle"), "switch"
    ),
    "Bless": Option(
        "Upgrade blessings",
        "Also opens the celestial chests it needs when 'Open chests' is off "
        "(Main screen > Chests).",
        "switch",
    ),
    "DailyOracle": Option("Claim the daily oracle", "Once-a-day oracle reward.", "switch"),
    "NoEng": Option(
        "Visit the engineer",
        "Claims the engineer reward and upgrades war machines if configured. " + _inv("NoEng"),
        "switch",
    ),
    "SellEx": Option(
        "Open the exotic merchant",
        "Master switch for selling and buying exotic items.",
        "switch",
    ),
    "SellScrolls": Option(SELL_LABELS[0], "Selling strategy (radio).", "radio"),
    "SellNoGold": Option(SELL_LABELS[1], "Selling strategy (radio).", "radio"),
    "SellAll": Option(SELL_LABELS[2], "Selling strategy (radio).", "radio"),
    "SellNone": Option(SELL_LABELS[3], "Selling strategy (radio).", "radio"),
    "ExoticUpgrades": Option(
        "Buy exotic upgrades", "Spends exotic coins on the merchant's upgrades.", "switch"
    ),
    "BuyEx": Option("Buy exotic chests", "Buys the merchant's exotic chests.", "switch"),
    "PVP": Option(
        "Fight arena battles",
        "Five battles per game day, retried every 6 h until 'done today' is set.",
        "switch",
    ),
    "Alch": Option("Run alchemy", _inv("Alch"), "switch"),
    "DragonBlood": Option("Use dragon blood", _inv("DragonBlood"), "switch"),
    "Dust": Option("Use dust", _inv("Dust"), "switch"),
    "Coin": Option("Use exotic coins", "Spends exotic coins in the alchemist.", "switch"),
    "Research": Option(
        "Start research",
        "Starts the next research when a slot is free. " + _inv("Research"),
        "switch",
    ),
    # -- Guild & tree ----------------------------------------------------------------------
    "NoGuild": Option(
        "Visit the guild", "Everything below is skipped when off. " + _inv("NoGuild"), "switch"
    ),
    "GNotif": Option(
        "Clear guild notifications", "Opens the guild tabs that show a badge.", "switch"
    ),
    "Pickaxes": Option("Claim pickaxes", _inv("Pickaxes"), "switch"),
    "Crystal": Option(
        "Spend pickaxes on the arcane crystal",
        "Uses the claimed pickaxes on the crystal.",
        "switch",
    ),
    "MaxCrystals": Option(
        "Crystal hits per day",
        "Pickaxes spent on the arcane crystal per game day, all in one visit; the crystal is "
        "then skipped until the daily reset.",
        "num",
        zero_means="0 = no limit",
    ),
    "Awaken": Option("Awaken heroes", "Uses the guild's awakening panel.", "switch"),
    "Chaos": Option(
        "Hit the chaos rift (free tokens only)",
        "Hits only while the free blue token shows; never spends paid tokens. Rewards are then "
        "spent on the guardians (Town > Guardian order).",
        "switch",
    ),
    "MaxChaos": Option(
        "Chaos hits per day", "Free-token hits only.", "num", zero_means="0 = no limit"
    ),
    # --- per-action switches (section [Actions], Python-only, default ON) ---
    "GuardianVisit": Option(
        "Visit the guardians (Magic quarter)",
        "Master switch of the guardian visit: evolve, training and chaos-rift upgrades below.",
        "switch",
    ),
    "GuardianEvolve": Option("Evolve the guardian", "When the evolve tab shows its dot.", "switch"),
    "GuardianTraining": Option(
        "Train the guardian", "Uses the training level chosen below.", "switch"
    ),
    "GuardianChaosUpgrades": Option(
        "Spend chaos-rift rewards on the guardians",
        "Third tab of the guardian screen, in the order below; also right after the chaos hits.",
        "switch",
    ),
    "TavernBeerTokens": Option(
        "Buy tavern tokens with beer",
        "Clicks the token shop's beer offer when affordable.",
        "switch",
    ),
    "CraftArtifact": Option(
        "Craft an artifact", "After the tavern tokens, when the craft button is green.", "switch"
    ),
    "ScarabTokenClaim": Option(
        "Claim the Pharaoh's token", "Scarab game notification in the tavern.", "switch"
    ),
    "Rituals": Option("Claim the rituals", "Oracle rituals tab when its dot shows.", "switch"),
    "EngineerTools": Option(
        "Claim the engineer's tools", "Green claim button at the engineer.", "switch"
    ),
    "AlchCollect": Option(
        "Collect finished experiments",
        "Collects completed and free-to-complete experiments before starting new ones.",
        "switch",
    ),
    "GuildExpedition": Option(
        "Start the guild expedition",
        "When the expeditions dot shows on the guild screen.",
        "switch",
    ),
    "MapMissions": Option(
        "Run the map missions",
        "Master switch of the whole map visit: mission claims, troop dispatch (priority order "
        "below), campaign and liberation.",
        "switch",
    ),
    "Campaign": Option("Claim the campaign", "Campaign rewards after the map missions.", "switch"),
    "MailDelete": Option("Delete read mail", "After claiming the attachments.", "switch"),
    "OracleGifts": Option("Open Oracle's gifts", "From the bag, after the chests.", "switch"),
    "MysteryBoxes": Option("Open mystery boxes", "From the bag, after the chests.", "switch"),
    "ChaosBooks": Option(
        "Buy the chaos rift books",
        "Once a day, after the hits: opens the rift Shop when it shows a notification and buys "
        "Tome of power books while the price button stays green.",
        "switch",
    ),
    "PTree": Option("Upgrade the personal tree", "Buys the checked upgrades each visit.", "switch"),
    "AttDmg": Option("Attribute Damage", "Personal tree upgrade.", "check"),
    "AttHp": Option("Attribute Health", "Personal tree upgrade.", "check"),
    "AttArm": Option("Attribute Armor", "Personal tree upgrade.", "check"),
    "Energy": Option("Energy Heroes", "Personal tree upgrade.", "check"),
    "Mana": Option("Mana Heroes", "Personal tree upgrade.", "check"),
    "Rage": Option("Rage Heroes", "Personal tree upgrade.", "check"),
    "Miner": Option("Miner", "Personal tree upgrade.", "check"),
    "MainAtt": Option("All Main Attributes", "Personal tree upgrade.", "check"),
    "Battle": Option("Battle Cry", "Personal tree upgrade.", "check"),
    "Prest": Option("Prestigious", "Personal tree upgrade.", "check"),
    "Fire": Option("Firestone Effect", "Personal tree upgrade.", "check"),
    "Gold": Option("Raining Gold", "Personal tree upgrade.", "check"),
    "Level": Option("Hero Level Up Cost", "Personal tree upgrade.", "check"),
    "Guard": Option("Guardian", "Personal tree upgrade.", "check"),
    "Fist": Option("Fist Fight", "Personal tree upgrade.", "check"),
    "Prec": Option("Precision", "Personal tree upgrade.", "check"),
    "Magic": Option("Magic Spells", "Personal tree upgrade.", "check"),
    "Tank": Option("Tank Specialization", "Personal tree upgrade.", "check"),
    "Damage": Option("Damage Specialization", "Personal tree upgrade.", "check"),
    "Heal": Option("Healer Specialization", "Personal tree upgrade.", "check"),
    # -- Missions & war machines -----------------------------------------------------------
    "Priority1": Option(
        "1st", "Mission category filled first.", "ordered", tuple(PRIORITY_CHOICES)
    ),
    "Priority2": Option("2nd", "Mission category.", "ordered", tuple(PRIORITY_CHOICES)),
    "Priority3": Option("3rd", "Mission category.", "ordered", tuple(PRIORITY_CHOICES)),
    "Priority4": Option("4th", "Mission category.", "ordered", tuple(PRIORITY_CHOICES)),
    "Priority5": Option("5th", "Mission category filled last.", "ordered", tuple(PRIORITY_CHOICES)),
    "MapReset": Option(
        "⚠ Reset the map cooldown with gems",
        "Spends gems whenever the mission reset is on cooldown.",
        "switch",
        warn=True,
    ),
    "Liberation": Option("Run liberation missions", "Campaign liberation missions.", "switch"),
    "DungeonQuest": Option(
        "Run dungeon missions",
        "Runs the dungeon missions of the campaign.",
        "switch",
    ),
    "UpgradeWM": Option(
        "War machine",
        "'Don't Upgrade WM's' disables the two rows below.",
        "choice",
        tuple(WM_CHOICES),
    ),
    "WMOptions": Option(
        "What to upgrade", "Levels, blueprints or both.", "seg", tuple(WM_MODE_CHOICES)
    ),
    "Blueprints": Option(
        "Blueprint priority",
        "Which stats get blueprint upgrades.",
        "choice",
        tuple(BLUEPRINT_CHOICES),
    ),
    "Talents450": Option(
        "Talents 0-450 points",
        "Kept for settings.ini compatibility with the AutoHotkey bot; the port has no talent "
        "logic.",
        "choice",
    ),
    "Talents800": Option(
        "Talents 500+ points",
        "Kept for settings.ini compatibility with the AutoHotkey bot; the port has no talent "
        "logic.",
        "choice",
    ),
    # -- Advanced --------------------------------------------------------------------------
    "Delay": Option(
        "Pause after each cycle",
        "Parks the mouse and waits before the next cycle.",
        "choice",
        tuple(DELAY_CHOICES),
        DELAY_DISPLAY,
    ),
    "SafetyCap": Option(
        "Safety cap on unbounded loops",
        "Some loops wait forever for a screen change (arena, liberation, hero upgrades, "
        "main-menu finder); N stops them after N iterations.",
        "num",
        zero_means="0 = off (AHK behaviour)",
    ),
    "RestartGame": Option(
        "Restart the game periodically",
        "Kills and relaunches the game every N hours.",
        "switch",
        warn=True,
    ),
    "RestartGameTime": Option(
        "Every", "Restart interval.", "seg", tuple(RESTART_HOURS), RESTART_DISPLAY
    ),
    "RestartGameTest": Option(
        "⚠ Restart once at the next start",
        "Runs the restart routine at the beginning of the first cycle (to test it).",
        "switch",
        warn=True,
    ),
    "DisableWarning": Option(
        "Dismiss the Steam warning", "Closes the Steam warning pop-up if it appears.", "switch"
    ),
    "EnableHeartbeat": Option(
        "Send heartbeats to the maintainer's log server",
        "Off by default. Sends progress messages (feature names, start/stop) only when on AND a "
        "Discord ID is set.",
        "switch",
    ),
    "DiscordID": Option("Discord ID", "Your numeric Discord user ID.", "text", pattern=r"^\d*$"),
}

READ_ONLY_LABELS = {
    "TokenCountDaily": "Tokens used today",
    "ChaosCountDaily": "Chaos hits today",
    "CrystalCountDaily": "Crystal hits today",
    "ScarabCountDaily": "Scarab plays today",
    "ArenaDoneDaily": "Arena done today",
    "LastTokenReset": "Last reset (tokens)",
    "LastChaosReset": "Last reset (chaos)",
    "ClientID": "Client ID",
}

ALL_KEYS = set(SETTINGS_MAP) | {"SafetyCap"}


# -- validators and formatters -----------------------------------------------------------------
def is_permutation(values: list[str], choices: list[str] | tuple[str, ...]) -> bool:
    return sorted(v.strip() for v in values) == sorted(choices)


def parse_order(text: str, choices: list[str] | tuple[str, ...], sep: str = ",") -> list[str]:
    """Split a comma list; returns [] when it is not a permutation of `choices`."""
    values = [v.strip() for v in text.split(sep)] if text.strip() else []
    return values if is_permutation(values, choices) else []


def format_ahk_stamp(stamp: str, empty: str = "never") -> str:
    """AHK YYYYMMDDHH24MISS -> 'YYYY-MM-DD HH:MM' (`empty` when blank or unparsable)."""
    stamp = (stamp or "").strip()
    if not stamp:
        return empty
    try:
        return datetime.strptime(stamp, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M")  # noqa: DTZ007
    except ValueError:
        return empty


def matches(pattern: str | None, value: str) -> bool:
    return pattern is None or re.fullmatch(pattern, value) is not None


# What the bot does with a value that is not one of the choices (features/open_chests.py:
# an unknown chest setting falls into the first label, i.e. opens every chest of the group).
UNKNOWN_EFFECT: dict[str, str] = {
    "GearChestExclude": "Don't Exclude Any",
    "JewelChestExclude": "Don't Exclude Any",
    "CelestialChestExclude": "Don't Exclude Any",
}


def unknown_note(key: str, value: str) -> tuple[str, str]:
    """(kind, text) shown in the help line when settings.ini holds an unknown value."""
    effect = UNKNOWN_EFFECT.get(key)
    text = f"settings.ini has {value!r}: not one of the choices"
    if effect == "Don't Exclude Any":
        text += f"; the bot treats it as '{effect}' (opens everything)"
    elif effect:
        text += f"; the bot treats it as '{effect}'"
    return ("warn", text + ". Pick one to replace it.")
