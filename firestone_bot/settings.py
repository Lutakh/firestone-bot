"""settings.ini compatibility layer.

Same sections and keys as `Gui.ahk` (SettingsMap). The file may be UTF-16 LE with BOM (AHK
default on the example) or UTF-8; it is written back in the encoding it was read with. Values
are kept as strings like AHK; `Settings.flag(name)` gives the boolean view used by the runtime.

The object is LIVE: the GUI writes into it on every change and feature modules read it at
call time, mirroring the AHK `GuiControlGet` behaviour.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field

# name -> (section, default). Order matters for writing.
SETTINGS_MAP: dict[str, tuple[str, str]] = {
    # --- Common Options ---
    "Token": ("CommonOptions", "0"),
    "SellEx": ("CommonOptions", "1"),
    "SellScrolls": ("CommonOptions", "0"),
    "SellNoGold": ("CommonOptions", "0"),
    "SellAll": ("CommonOptions", "1"),
    "SellNone": ("CommonOptions", "0"),
    "ExoticUpgrades": ("CommonOptions", "1"),
    "BuyEx": ("CommonOptions", "1"),
    "Chests": ("CommonOptions", "0"),
    "GearChestExclude": ("CommonOptions", "Titan"),
    "JewelChestExclude": ("CommonOptions", "Platinum"),
    "CelestialChestExclude": ("CommonOptions", "Galaxy"),
    "Bless": ("CommonOptions", "1"),
    "BlessingChests": ("CommonOptions", "1"),
    "Delay": ("CommonOptions", "0"),
    "Quests": ("CommonOptions", "0"),
    "Events": ("CommonOptions", "0"),
    "Mail": ("CommonOptions", "1"),
    "Awaken": ("CommonOptions", "0"),
    "Crystal": ("CommonOptions", "1"),
    "Chaos": ("CommonOptions", "1"),
    "PTree": ("CommonOptions", "0"),
    "GuardianTrain": ("CommonOptions", "Vermilion"),
    # daily counters (Python port, see daily.py)
    "MaxTokens": ("CommonOptions", "0"),
    "TokenCountDaily": ("CommonOptions", "0"),
    "LastTokenReset": ("CommonOptions", ""),
    "ArenaDoneDaily": ("CommonOptions", "0"),
    "MaxChaos": ("CommonOptions", "10"),
    "ChaosCountDaily": ("CommonOptions", "0"),
    "LastChaosReset": ("CommonOptions", ""),
    "ChaosGuardianOrder": ("CommonOptions", "1,2,3,4"),
    "ChaosBooks": ("CommonOptions", "1"),
    "ChaosBooksDaily": ("CommonOptions", "0"),
    "MaxScarab": ("CommonOptions", "10"),
    "ScarabCountDaily": ("CommonOptions", "0"),
    "UpgradeSpecial": ("HeroOptions", "1"),
    "UpgradeGuardian": ("HeroOptions", "1"),
    "UpgradeH1": ("HeroOptions", "1"),
    "UpgradeH2": ("HeroOptions", "1"),
    "UpgradeH3": ("HeroOptions", "1"),
    "UpgradeH4": ("HeroOptions", "1"),
    "UpgradeH5": ("HeroOptions", "1"),
    # --- Mission Priority ---
    "Priority1": ("MissionPriority", "2 Squad"),
    "Priority2": ("MissionPriority", "War"),
    "Priority3": ("MissionPriority", "Medium"),
    "Priority4": ("MissionPriority", "Short"),
    "Priority5": ("MissionPriority", "Leftover"),
    "MapReset": ("MissionPriority", "0"),
    # --- QoL/Rare Options ---
    "Beer": ("QoL/RareOptions", "0"),
    "Scarab": ("QoL/RareOptions", "0"),
    "NoGuild": ("QoL/RareOptions", "0"),
    "NoEng": ("QoL/RareOptions", "0"),
    "Pickaxes": ("QoL/RareOptions", "0"),
    "GNotif": ("QoL/RareOptions", "0"),
    "Alch": ("QoL/RareOptions", "0"),
    "Dust": ("QoL/RareOptions", "0"),
    "DragonBlood": ("QoL/RareOptions", "0"),
    "Coin": ("QoL/RareOptions", "0"),
    "Research": ("QoL/RareOptions", "0"),
    "SkipOracle": ("QoL/RareOptions", "0"),
    "NoHero": ("QoL/RareOptions", "0"),
    "NextMilestone": ("QoL/RareOptions", "0"),
    "DisableWarning": ("QoL/RareOptions", "1"),
    # --- Other Options ---
    "Shop": ("OtherOptions", "0"),
    "DailyOracle": ("OtherOptions", "1"),
    "PVP": ("OtherOptions", "1"),
    "Liberation": ("OtherOptions", "1"),
    "UpgradeWM": ("OtherOptions", "Don't Upgrade WM's"),
    "WMOptions": ("OtherOptions", "Level and Blueprints"),
    "Blueprints": ("OtherOptions", "Damage and Health"),
    "Talents450": ("OtherOptions", "Don't Upgrade Talents (0-450 Talent Points)"),
    "Talents800": ("OtherOptions", "Don't Upgrade Talents (500+ Talent Points)"),
    "RestartGame": ("OtherOptions", "0"),
    "RestartGameTest": ("OtherOptions", "0"),
    "RestartGameTime": ("OtherOptions", "24"),
    # --- SettingsNoGui ---
    "DungeonQuest": ("SettingsNoGui", "0"),
    "DiscordID": ("SettingsNoGui", ""),
    "EnableHeartbeat": ("SettingsNoGui", "0"),
    "ClientID": ("SettingsNoGui", ""),
    # --- Personal Tree ---
    "AttDmg": ("PersonalTree", "0"),
    "AttHp": ("PersonalTree", "0"),
    "AttArm": ("PersonalTree", "0"),
    "Energy": ("PersonalTree", "0"),
    "Mana": ("PersonalTree", "0"),
    "Rage": ("PersonalTree", "0"),
    "Miner": ("PersonalTree", "0"),
    "Battle": ("PersonalTree", "0"),
    "MainAtt": ("PersonalTree", "0"),
    "Prest": ("PersonalTree", "0"),
    "Fire": ("PersonalTree", "0"),
    "Gold": ("PersonalTree", "0"),
    "Level": ("PersonalTree", "0"),
    "Guard": ("PersonalTree", "0"),
    "Fist": ("PersonalTree", "0"),
    "Prec": ("PersonalTree", "0"),
    "Magic": ("PersonalTree", "0"),
    "Tank": ("PersonalTree", "0"),
    "Damage": ("PersonalTree", "0"),
    "Heal": ("PersonalTree", "0"),
}

# Python-only additions (never written unless changed from default).
EXTRA_SETTINGS: dict[str, tuple[str, str]] = {
    "SafetyCap": ("PythonOptions", "0"),  # optional cap on unbounded loops (plan 3.2)
}

ENCODINGS = ("utf-16", "utf-8-sig")


def _read_text(path: str) -> tuple[str, str]:
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    return raw.decode("utf-8-sig"), "utf-8-sig"


def _parser() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, delimiters=("=",), strict=False)
    cp.optionxform = str  # keep key case, like AHK
    return cp


@dataclass
class Settings:
    path: str = "settings.ini"
    values: dict[str, str] = field(default_factory=dict)
    extra: dict[str, dict[str, str]] = field(default_factory=dict)  # unknown keys, preserved
    encoding: str = "utf-16"

    def __post_init__(self) -> None:
        for k, (_, d) in {**SETTINGS_MAP, **EXTRA_SETTINGS}.items():
            self.values.setdefault(k, d)

    # -- access ------------------------------------------------------------------------
    def get(self, name: str) -> str:
        return self.values[name]

    def set(self, name: str, value: str | int | bool) -> None:
        if isinstance(value, bool):
            value = "1" if value else "0"
        self.values[name] = str(value)

    def flag(self, name: str) -> bool:
        """AHK `If (Checked = 1)` semantics."""
        return self.values.get(name, "0").strip() == "1"

    def __getattr__(self, name: str) -> str:
        values = self.__dict__.get("values")
        if values is not None and name in values:
            return values[name]
        raise AttributeError(name)

    # -- persistence -------------------------------------------------------------------
    @classmethod
    def load(cls, path: str = "settings.ini") -> Settings:
        s = cls(path=path)
        if not os.path.exists(path):
            return s
        text, s.encoding = _read_text(path)
        cp = _parser()
        cp.read_string(text)
        known = {**SETTINGS_MAP, **EXTRA_SETTINGS}
        for section in cp.sections():
            for key, value in cp.items(section):
                if key in known and known[key][0] == section:
                    s.values[key] = value
                else:
                    s.extra.setdefault(section, {})[key] = value
        return s

    def save(self, path: str | None = None) -> None:
        path = path or self.path
        cp = _parser()
        for k, (section, default) in {**SETTINGS_MAP, **EXTRA_SETTINGS}.items():
            if k in EXTRA_SETTINGS and self.values[k] == default:
                continue
            if not cp.has_section(section):
                cp.add_section(section)
            cp.set(section, k, self.values[k])
        for section, items in self.extra.items():
            if not cp.has_section(section):
                cp.add_section(section)
            for k, v in items.items():
                cp.set(section, k, v)
        lines = []
        for section in cp.sections():
            lines.append(f"[{section}]")
            lines.extend(f"{k}={v}" for k, v in cp.items(section))
        data = "\n".join(lines) + "\n"
        # Write-then-rename: a reader (or a crash mid-write) never sees a torn settings.ini.
        tmp = path + ".tmp"
        with open(tmp, "w", encoding=self.encoding, newline="\r\n") as f:
            f.write(data)
        os.replace(tmp, path)
