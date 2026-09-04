"""Wires settings, GUI, game context and runner together."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

from firestone_bot.game import Game
from firestone_bot.gui.main_window import MainWindow
from firestone_bot.platform import capture, process
from firestone_bot.platform.dpi import set_dpi_aware
from firestone_bot.platform.window import GameWindowNotFound, find_game_window
from firestone_bot.runner import Runner
from firestone_bot.settings import Settings
from firestone_bot.vision.viewport import Viewport

log = logging.getLogger("firestone_bot.app")


def base_dir() -> str:
    """Directory holding settings.ini: next to the exe when frozen, else the cwd."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


class App:
    def __init__(self) -> None:
        self.dpi_mode = set_dpi_aware()
        self.base = base_dir()
        self.settings = Settings.load(os.path.join(self.base, "settings.ini"))
        self.game = Game(self.settings, status_cb=self._status)
        self.game.map_state_path = os.path.join(self.base, "MapStartState.ini")
        self.runner = Runner(self.settings, self.game)
        self.window = MainWindow(
            self.settings,
            on_start=self.start,
            on_stop=self.stop,
            on_dry_run=self.dry_run,
            on_self_test=self.self_test,
            on_exit=self.exit,
            is_running=lambda: self.runner.running,
            base_dir=self.base,
        )
        self._hotkey_listener = None
        self._exit_heartbeat: threading.Thread | None = None
        # Screenshot / test helpers: open the GUI on a given page or appearance.
        if page := os.environ.get("FIRESTONE_GUI_PAGE"):
            self.window.show_page(page)
        if look := os.environ.get("FIRESTONE_GUI_APPEARANCE"):
            self.window.set_appearance(look)

    # -- callbacks --------------------------------------------------------------------------
    def _status(self, text: str) -> None:
        self.window.post_status(text)

    def start(self) -> None:
        if self.runner.running:
            return
        self.game.dry_run = False
        self.runner.start()
        self.window.set_bot_state("running")

    def dry_run(self) -> None:
        if self.runner.running:
            return
        self.game.dry_run = True
        self.runner.start()
        self.window.set_bot_state("dry run (no input)")

    def stop(self) -> None:
        self.runner.stop()
        self.window.set_bot_state("stopping...")

    def exit(self) -> None:
        """Called on the Tk thread from the window's exit path, before settings are flushed:
        stop the runner and wait briefly so the bot thread's own settings.save() is over."""
        self.runner.stop()
        # Blocking urlopen (10 s timeout): keep it off the UI thread, joined after mainloop.
        self._exit_heartbeat = threading.Thread(
            target=lambda: self.game.heartbeat("Exit Bot", is_stop=True, important=True),
            name="exit-heartbeat",
            daemon=True,
        )
        self._exit_heartbeat.start()
        t = self.runner.thread
        if t and t.is_alive():
            t.join(timeout=3)
        if self._hotkey_listener:
            self._hotkey_listener.stop()

    def self_test(self) -> dict[str, str]:
        out = {"dpi": self.dpi_mode}
        try:
            win = find_game_window()
        except GameWindowNotFound as e:
            out.update(window=f"not found ({e})", platform="-", client="-", scale="-", capture="-")
            return out
        vp = Viewport(win.client)
        out["window"] = f"'{win.title}' pid {win.pid}" + (" maximized" if win.maximized else "")
        out["platform"] = process.detect_platform(win.exe)
        out["client"] = f"{win.client.w}x{win.client.h} at ({win.client.x},{win.client.y})"
        aspect_ok = abs(win.client.w / win.client.h - 1920 / 1009) < 0.01
        out["scale"] = (
            f"{vp.rel_scale:.3f} (canvas {vp.scale:.3f}), aspect {'OK' if aspect_ok else 'differs from reference: anchors in use'}"
        )
        t0 = time.perf_counter()
        try:
            img = capture.grab(win.client)
            out["capture"] = (
                f"OK {img.shape[1]}x{img.shape[0]} in {1000 * (time.perf_counter() - t0):.0f} ms"
            )
        except Exception as e:  # noqa: BLE001
            out["capture"] = f"FAILED: {e}"
        out["input"] = "pynput SendInput (move test happens in the dry run trace)"
        return out

    # -- Win+Esc exit hotkey (AHK ~*#$Esc) ---------------------------------------------------
    def _install_hotkey(self) -> None:
        try:
            from pynput import keyboard
        except Exception:  # noqa: BLE001
            return
        pressed: set = set()

        def on_press(key):
            pressed.add(key)
            if key == keyboard.Key.esc and (
                keyboard.Key.cmd in pressed
                or keyboard.Key.cmd_l in pressed
                or keyboard.Key.cmd_r in pressed
            ):
                self.window.request_exit()

        def on_release(key):
            pressed.discard(key)

        self._hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def run(self) -> None:
        self._install_hotkey()
        self.window.run()
        if self._exit_heartbeat is not None:
            self._exit_heartbeat.join(timeout=2)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(base_dir(), "firestone-bot.log"), encoding="utf-8")
        ],
    )
    App().run()
    return 0
