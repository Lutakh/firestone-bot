"""The main cycle: literal port of MainScript() in firestone-bot.ahk.

Runs in a worker thread; the GUI (or the CLI) owns the stop event. Timers (arena every 6 h,
game restart every RestartGameTime hours) and the end-of-cycle delay are reproduced as-is.
"""

from __future__ import annotations

import logging
import threading
import time

from firestone_bot import daily
from firestone_bot.features import (
    alchemist,
    arena,
    big_close,
    check_mail,
    claim_beer,
    claim_engineer,
    claim_events,
    claim_rituals,
    exotic_merchant,
    go_map,
    guardian,
    guild,
    hero_upgrade,
    main_menu,
    map_redeem,
    open_chests,
    open_town,
    quests,
    research,
    restart_game_routine,
    scarab,
    scarab_token,
    shop,
)
from firestone_bot.features.heartbeat import send_heartbeat
from firestone_bot.game import BotStopped, Game
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas

log = logging.getLogger("firestone_bot.runner")

END_OF_CYCLE_DELAYS = {"0": 0, "30": 30, "60": 60, "90": 90, "120": 120, "300": 300, "600": 600}


def _ms() -> int:
    return int(time.monotonic() * 1000)


class Runner:
    def __init__(self, settings: Settings, game: Game) -> None:
        self.settings = settings
        self.g = game
        self.stop_event = game.stop_event
        self.thread: threading.Thread | None = None
        self.cycles = 0
        self.max_cycles = 0  # 0 = forever (AHK); tools set 1 for a single dry-run cycle
        game.heartbeat_cb = self._heartbeat

    # -- lifecycle ------------------------------------------------------------------------
    def _heartbeat(self, msg: str, is_stop: bool, important: bool) -> None:
        send_heartbeat(self.settings, msg, is_stop, important)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="firestone-bot", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    @property
    def running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def _run(self) -> None:
        try:
            self.main_script()
        except BotStopped:
            self.g.status("Stopped")
        except Exception:
            log.exception("cycle crashed")
            self.g.status("Crashed, see log")

    # -- MainScript() -----------------------------------------------------------------------
    def main_script(self) -> None:
        g, s = self.g, self.settings
        last_arena = 0
        last_restart = _ms()
        restart_ms = float(s.get("RestartGameTime") or 0) * 3600000
        while True:  # loop:
            if s.flag("RestartGame") and (
                s.flag("RestartGameTest") or _ms() - last_restart >= restart_ms
            ):
                g.heartbeat("Initiating 24h Game Restart", important=True)
                restart_game_routine.restart_game_routine(g)
                last_restart = _ms()
            g.focus()
            # do main screen sections
            g.heartbeat("Starting Bot", important=True)
            g.toast("Main Menu Check", "Checking to ensure we are on main screen at loop start", 2)
            main_menu.main_menu(g)
            g.focus()
            if s.flag("Events"):
                claim_events.claim_events(g)
            if s.flag("Quests"):
                g.heartbeat("ClaimQuests")
                quests.claim_quests(g)
            g.toast(
                "Main Menu Check",
                "Checking to ensure we are on main screen after claiming quests",
                2,
            )
            main_menu.main_menu(g)
            g.focus()
            # always: the shop visit also detects the daily reset (free mystery box)
            g.heartbeat("Shop")
            shop.shop(g)
            if s.flag("Mail"):
                g.heartbeat("CheckMail")
                check_mail.check_mail(g)
            if s.flag("Chests"):
                g.heartbeat("OpenChests")
                open_chests.open_chests(g)
            elif s.flag("Bless"):
                g.heartbeat("OpenBlessChests")
                open_chests.open_bless_chests(g)
            # start town section
            open_town.open_town(g)
            g.heartbeat("Guardian")
            guardian.guardian(g)
            g.heartbeat("ClaimBeer")
            claim_beer.claim_beer(g)
            g.heartbeat("ScarabToken")
            scarab_token.scarab_token(g)
            g.heartbeat("Scarab")
            scarab.scarab(g)
            if not s.flag("SkipOracle"):
                g.heartbeat("ClaimRituals")
                claim_rituals.claim_rituals(g)
            # Engineer:
            if not s.flag("NoEng"):
                g.heartbeat("ClaimEngineer")
                claim_engineer.claim_engineer(g)
            # ExoticSection:
            if s.flag("SellEx"):
                g.heartbeat("ExoticMerchant")
                exotic_merchant.exotic_merchant(g)
            if s.flag("PVP") and not daily.arena_done(s):
                now = _ms()
                if last_arena <= 0 or now - last_arena >= 6 * 60 * 60 * 1000:
                    g.heartbeat("Arena")
                    arena.arena(g)
                    last_arena = now
            if not s.flag("Alch"):
                g.heartbeat("Alchemist")
                alchemist.alchemist(g)
            # ResearchStart:
            if not s.flag("Research"):
                g.heartbeat("GoResearch")
                research.go_research(g)
            # FinishTown:
            big_close.big_close(g)
            if not s.flag("NoGuild"):
                guild.guild(g)
            # MapStartUp:
            go_map.go_map(g)
            g.heartbeat("MapRedeem")
            map_redeem.map_redeem(g)
            # UpgradeHero:
            if not s.flag("NoHero"):
                g.heartbeat("HeroUpgrade")
                hero_upgrade.hero_upgrade(g)
            # EndingMouseMove:
            g.heartbeat("Delay ending bot")
            self.cycles += 1
            if self.max_cycles and self.cycles >= self.max_cycles:
                g.status(f"Cycle {self.cycles} done (max cycles reached)")
                return
            delay = END_OF_CYCLE_DELAYS.get(s.get("Delay").strip())
            if delay is None:
                # AHK: no matching branch, MainScript() returns and the bot silently stops.
                g.status(f"Delay setting {s.get('Delay')!r} not recognised; bot stopped")
                return
            if delay:
                g.move_to(atlas.END_OF_CYCLE_PARK)
                g.status(f"Cycle {self.cycles} done, waiting {delay} s")
                g.sleep(delay * 1000)
            else:
                g.status(f"Cycle {self.cycles} done")
