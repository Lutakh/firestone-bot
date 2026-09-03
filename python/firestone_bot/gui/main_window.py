"""tkinter/ttk settings window: the five tabs of Gui.ahk plus a Status panel on Home.

Every control is bound to a tk variable whose trace writes straight into the live Settings
object, so feature modules see changes immediately (AHK GuiControlGet semantics).
"""

from __future__ import annotations

import queue
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from firestone_bot import __version__
from firestone_bot.settings import Settings

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
WM_CHOICES = ["Don't Upgrade WM's"] + [
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

HOME_TEXT = """SYSTEM & GAME SETTINGS:
- Use the Steam or Epic version (the browser version is not supported yet).
- Reference setup: 1920x1080 monitor, 100 % DPI, game windowed and maximized, taskbar at the
  bottom. Other window sizes with the same aspect are supported; see the Status panel.
- Game Settings (top right): NOT fullscreen. Game language: English.

GAMEPLAY SETTINGS:
- Adventure button style: Mobile or PC (NOT the new Adventure style).
- Activate "Confirmation for purchase with jewels" (safety).

BOT USAGE:
- Exit hotkey: Windows key + Esc.
- Check all tabs and activate ONLY what you need.
- DO NOT move or zoom the map. Leave it as it is on login. If moved, restart the game.

TROUBLESHOOTING:
- If missions are not found: make sure the system language and fonts are English."""


class MainWindow:
    def __init__(
        self,
        settings: Settings,
        *,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_dry_run: Callable[[], None],
        on_self_test: Callable[[], dict[str, str]],
        on_exit: Callable[[], None],
    ) -> None:
        self.settings = settings
        self.on_start, self.on_stop, self.on_dry_run = on_start, on_stop, on_dry_run
        self.on_self_test, self.on_exit = on_self_test, on_exit
        self.vars: dict[str, tk.StringVar] = {}
        self.status_queue: queue.Queue[str] = queue.Queue()

        self.root = tk.Tk()
        self.root.title(f"Firestone Bot {__version__} (Python)")
        self.root.geometry("980x780")
        self.root.protocol("WM_DELETE_WINDOW", self._exit)
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)
        self._build_home(nb)
        self._build_general(nb)
        self._build_guild(nb)
        self._build_war_machines(nb)
        self._build_settings_tab(nb)
        self.root.after(200, self._poll_status)

    # -- variable binding ---------------------------------------------------------------
    def _var(self, name: str) -> tk.StringVar:
        if name not in self.vars:
            v = tk.StringVar(value=self.settings.get(name))
            v.trace_add("write", lambda *_: self.settings.set(name, v.get()))
            self.vars[name] = v
        return self.vars[name]

    def _check(self, parent, name: str, text: str, **grid) -> ttk.Checkbutton:
        cb = ttk.Checkbutton(parent, text=text, variable=self._var(name), onvalue="1", offvalue="0")
        cb.grid(sticky="w", padx=8, pady=2, **grid)
        return cb

    def _combo(self, parent, name: str, label: str, values: list[str], **grid) -> None:
        f = ttk.Frame(parent)
        f.grid(sticky="w", padx=8, pady=2, **grid)
        ttk.Label(f, text=label).pack(side="left")
        ttk.Combobox(
            f, textvariable=self._var(name), values=values, state="readonly", width=28
        ).pack(side="left", padx=6)

    def _group(self, parent, text: str, **grid) -> ttk.LabelFrame:
        g = ttk.LabelFrame(parent, text=text)
        g.grid(sticky="nsew", padx=8, pady=6, **grid)
        return g

    # -- tabs -----------------------------------------------------------------------------
    def _build_home(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Home")
        ttk.Label(tab, text=f"FIRESTONE BOT {__version__}", font=("Segoe UI", 16, "bold")).pack(
            pady=8
        )
        txt = tk.Text(tab, height=17, wrap="word", font=("Segoe UI", 9))
        txt.insert("1.0", HOME_TEXT)
        txt.configure(state="disabled")
        txt.pack(fill="x", padx=16)

        status = ttk.LabelFrame(tab, text="Status")
        status.pack(fill="x", padx=16, pady=8)
        self.status_labels: dict[str, ttk.Label] = {}
        for i, key in enumerate(
            ("window", "platform", "client", "scale", "dpi", "capture", "input", "bot")
        ):
            ttk.Label(status, text=key.capitalize() + ":").grid(
                row=i // 2, column=(i % 2) * 2, sticky="e", padx=6
            )
            lbl = ttk.Label(status, text="-", width=48)
            lbl.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w")
            self.status_labels[key] = lbl
        self.activity = ttk.Label(tab, text="Idle", relief="sunken", anchor="w")
        self.activity.pack(fill="x", padx=16)

        btns = ttk.Frame(tab)
        btns.pack(pady=12)
        ttk.Button(btns, text="SELF-TEST", command=self._self_test).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="DRY RUN (no input)", command=self.on_dry_run).grid(
            row=0, column=1, padx=6
        )
        ttk.Button(btns, text="SAVE SETTINGS", command=self._save).grid(row=0, column=2, padx=6)
        ttk.Button(btns, text="START BOT", command=self.on_start).grid(row=0, column=3, padx=6)
        ttk.Button(btns, text="STOP BOT", command=self.on_stop).grid(row=0, column=4, padx=6)
        ttk.Button(btns, text="EXIT", command=self._exit).grid(row=0, column=5, padx=6)

    def _build_general(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="General Options")
        for c in range(3):
            tab.columnconfigure(c, weight=1)

        g = self._group(tab, "Selling & Exotic Merchant", row=0, column=0)
        self._check(g, "SellEx", "Open Exotic Merchant (Master)")
        self._check(g, "ExoticUpgrades", "Buy Exotic Upgrades")
        self._check(g, "BuyEx", "Buy Exotic Chests")
        ttk.Label(g, text="Selling Strategy:").grid(sticky="w", padx=8, pady=(8, 2))
        self.sell_mode = tk.StringVar(value=self._current_sell_mode())
        for name, text in (
            ("SellScrolls", "1. Sell ONLY Exotic Scrolls"),
            ("SellNoGold", "2. Sell All But Gold Items"),
            ("SellAll", "3. Sell All Exotic Items"),
            ("SellNone", "4. Sell Nothing"),
        ):
            ttk.Radiobutton(g, text=text, value=name, variable=self.sell_mode).grid(
                sticky="w", padx=8, pady=2
            )
        self.sell_mode.trace_add("write", lambda *_: self._apply_sell_mode())

        g = self._group(tab, "Other Automation", row=1, column=0)
        self._check(g, "NoEng", "Skip Engineer")
        self._check(g, "Research", "Skip Research")
        self._check(g, "DisableWarning", "Disable Steam Warning")
        self._check(g, "RestartGame", "Restart Game")
        self._check(g, "RestartGameTest", "Try the game restart at the beginning")
        self._combo(g, "RestartGameTime", "Restart Game Every X Hours:", ["6", "12", "18", "24"])
        self._combo(g, "GuardianTrain", "Train Guardian:", ["1", "2", "3", "4"])

        g = self._group(tab, "Chests & Rewards", row=0, column=1)
        self._check(g, "Chests", "Open Chests (General)")
        self._combo(g, "GearChestExclude", "Exclude Gear Chests:", GEAR_CHOICES)
        self._combo(g, "JewelChestExclude", "Exclude Jewel Chests:", JEWEL_CHOICES)
        self._combo(g, "CelestialChestExclude", "Exclude Celestial Chests:", CELESTIAL_CHOICES)
        g = self._group(tab, "Oracle", row=1, column=1)
        self._check(g, "Bless", "Upgrade Blessings")
        self._check(g, "BlessingChests", "Open Chests")
        self._check(g, "DailyOracle", "Claim Daily Oracle")
        self._check(g, "SkipOracle", "Skip Oracle")
        g = self._group(tab, "Alchemy", row=2, column=1)
        self._check(g, "Alch", "Skip Alchemy")
        self._check(g, "DragonBlood", "Don't Use DragonBlood in Alchemy")
        self._check(g, "Dust", "Don't Use Dust in Alchemy")
        self._check(g, "Coin", "Use Exotic Coins in Alchemy")
        g = self._group(tab, "Hero Upgrades", row=3, column=1)
        self._check(g, "NoHero", "Don't Upgrade Heroes (Master)")
        self._check(g, "NextMilestone", "Set upgrade to Next Milestone")
        self._check(g, "UpgradeSpecial", "Special Upgrade")
        self._check(g, "UpgradeGuardian", "Guardian")
        for i in range(1, 6):
            self._check(g, f"UpgradeH{i}", f"Hero {i}")

        g = self._group(tab, "Daily Routine", row=0, column=2)
        self._check(g, "Mail", "Check Mail")
        self._check(g, "Quests", "Claim Quests")
        self._check(g, "Events", "Claim Basic Events")
        self._check(g, "Chaos", "Participate in Chaos Rift")
        self._check(g, "Shop", "Free Gift & Check-In")
        self._combo(g, "Delay", "End of Cycle Delay (Sec):", ["0", "30", "60", "90", "120"])
        g = self._group(tab, "Tavern / Scarab", row=1, column=2)
        self._check(g, "Token", "Use Tavern Tokens / Artifacts")
        self._check(g, "Beer", "Skip Claiming Beer")
        self._check(g, "Scarab", "Skip Using Scarab Token")
        g = self._group(tab, "Mission Priority Order", row=2, column=2, rowspan=2)
        for i, label in enumerate(("1st:", "2nd:", "3rd:", "4th:", "5th:"), start=1):
            self._combo(g, f"Priority{i}", label, PRIORITY_CHOICES)
        self._check(g, "MapReset", "Reset map cooldown with gems")

    def _build_guild(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Guild & Personal Tree")
        for c in range(3):
            tab.columnconfigure(c, weight=1)
        g = self._group(tab, "Guild Options", row=0, column=0, columnspan=3)
        self._check(g, "NoGuild", "Skip Guild Functions", row=0, column=0)
        self._check(g, "GNotif", "Clear Guild Notifications", row=1, column=0)
        self._check(g, "Pickaxes", "Skip Claiming Pickaxes", row=0, column=1)
        self._check(g, "Crystal", "Spend Pickaxes (Crystal)", row=1, column=1)
        self._check(g, "Awaken", "Awaken Heroes", row=0, column=2)
        self._check(
            tab, "PTree", "> ENABLE PERSONAL TREE UPGRADES <", row=1, column=0, columnspan=3
        )
        g = self._group(tab, "Attributes & Heroes", row=2, column=0)
        for name, text in (
            ("AttDmg", "Attribute Damage"),
            ("AttHp", "Attribute Health"),
            ("AttArm", "Attribute Armor"),
            ("Energy", "Energy Heroes"),
            ("Mana", "Mana Heroes"),
            ("Rage", "Rage Heroes"),
            ("Miner", "Miner"),
            ("MainAtt", "All Main Attributes"),
        ):
            self._check(g, name, text)
        g = self._group(tab, "Specializations", row=2, column=1)
        for name, text in (
            ("Battle", "Battle Cry"),
            ("Prest", "Prestigious"),
            ("Fire", "Firestone Effect"),
            ("Gold", "Raining Gold"),
            ("Level", "Hero Level Up Cost"),
            ("Guard", "Guardian"),
            ("Fist", "Fist Fight"),
            ("Prec", "Precision"),
        ):
            self._check(g, name, text)
        g = self._group(tab, "Classes", row=2, column=2)
        for name, text in (
            ("Magic", "Magic Spells"),
            ("Tank", "Tank Specialization"),
            ("Damage", "Damage Specialization"),
            ("Heal", "Healer Specialization"),
        ):
            self._check(g, name, text)

    def _build_war_machines(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="War Machines")
        g = self._group(tab, "Battle & Miscellaneous", row=0, column=0)
        self._check(g, "PVP", "Complete Arena Battles", row=0, column=0)
        self._check(g, "Liberation", "Complete Liberation Missions", row=0, column=1)
        self._check(g, "DungeonQuest", "Complete Dungeon Missions", row=0, column=2)
        g = self._group(tab, "War Machines & Talents", row=1, column=0)
        self._combo(g, "UpgradeWM", "War Machine to Upgrade:", WM_CHOICES)
        self._combo(g, "WMOptions", "Upgrade Mode:", WM_MODE_CHOICES)
        self._combo(g, "Blueprints", "Blueprint Priority:", BLUEPRINT_CHOICES)
        self._combo(g, "Talents450", "Talent Options (Legacy):", [self.settings.get("Talents450")])
        self._combo(g, "Talents800", "", [self.settings.get("Talents800")])

    def _build_settings_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Settings")
        g = self._group(tab, "Discord Configuration", row=0, column=0)
        f = ttk.Frame(g)
        f.grid(sticky="w", padx=8, pady=8)
        ttk.Label(f, text="Discord ID:").pack(side="left")
        ttk.Entry(f, textvariable=self._var("DiscordID"), width=32).pack(side="left", padx=6)
        g = self._group(tab, "Python port options", row=1, column=0)
        self._check(g, "EnableHeartbeat", "Send heartbeats to the log server (opt-in)")
        f = ttk.Frame(g)
        f.grid(sticky="w", padx=8, pady=4)
        ttk.Label(f, text="Safety cap on unbounded loops (0 = off, AHK behaviour):").pack(
            side="left"
        )
        ttk.Entry(f, textvariable=self._var("SafetyCap"), width=6).pack(side="left", padx=6)

    # -- sell mode radios (four AHK 1/0 variables) --------------------------------------
    def _current_sell_mode(self) -> str:
        for name in ("SellScrolls", "SellNoGold", "SellAll", "SellNone"):
            if self.settings.flag(name):
                return name
        return ""

    def _apply_sell_mode(self) -> None:
        chosen = self.sell_mode.get()
        for name in ("SellScrolls", "SellNoGold", "SellAll", "SellNone"):
            self.settings.set(name, name == chosen)

    # -- actions ----------------------------------------------------------------------------
    def _save(self) -> None:
        self.settings.save()
        messagebox.showinfo("Saved", "Settings have been saved successfully!")

    def _self_test(self) -> None:
        for key, value in self.on_self_test().items():
            if key in self.status_labels:
                self.status_labels[key].configure(text=value)

    def _exit(self) -> None:
        self.on_exit()
        self.root.destroy()

    # -- status from the worker thread ----------------------------------------------------
    def post_status(self, text: str) -> None:
        self.status_queue.put(text)

    def _poll_status(self) -> None:
        try:
            while True:
                self.activity.configure(text=self.status_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(200, self._poll_status)

    def set_bot_state(self, text: str) -> None:
        self.status_labels["bot"].configure(text=text)

    def run(self) -> None:
        self.root.mainloop()
